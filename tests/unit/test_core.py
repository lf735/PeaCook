from peacook.extract import textutil as tu
from peacook.resolve.values import UNKNOWN, Evaluator, Obj, ArrayVal, InstRef, sformatf


class _Ctx:
    enums = {"UVM_ACTIVE": 1, "UVM_PASSIVE": 0}

    def __init__(self, scope=None):
        self.scope = scope or {}

    def lookup(self, n):
        return self.scope.get(n, Evaluator.MISSING)

    def member(self, cur, n):
        return cur.fields.get(n, UNKNOWN) if isinstance(cur, Obj) else UNKNOWN

    def index(self, cur, i):
        return cur.items.get(i, UNKNOWN) if isinstance(cur, ArrayVal) else UNKNOWN

    def call(self, recv, n, args):
        if recv is None and n == "$sformatf":
            return sformatf(args[0], args[1:])
        if isinstance(recv, ArrayVal) and n == "size":
            return recv.size
        return UNKNOWN


def ev(s, **scope):
    return Evaluator(_Ctx(scope)).eval(s)


def test_split_args_respects_nesting_and_strings():
    assert tu.split_args('this, "a,b", f(x, y), {1,2}') == ['this', '"a,b"', 'f(x, y)', '{1,2}']


def test_config_ops_parsing():
    ops = tu.find_config_ops('uvm_config_db#(virtual apb_if)::set(null, "*", "vif", i0)')
    assert ops[0]["kind"] == "set" and ops[0]["type"] == "virtual apb_if" and ops[0]["field"] == '"vif"'


def test_override_forms():
    o = tu.find_overrides('set_inst_override_by_type("env.drv", a::get_type(), b::get_type())')[0]
    assert (o["scope"], o["orig"], o["over"], o["path"]) == ("inst", "a", "b", "env.drv")
    o = tu.find_overrides("a::type_id::set_type_override(b::get_type())")[0]
    assert (o["scope"], o["orig"], o["over"]) == ("type", "a", "b")


def test_evaluator_three_valued_logic():
    assert ev("1 == 1") is True
    assert ev("x == 2") is UNKNOWN
    assert ev("0 && x") is False          # court-circuit même avec inconnu
    assert ev("1 || x") is True
    assert ev("UVM_PASSIVE == UVM_ACTIVE") is False


def test_evaluator_objects_and_sformatf():
    cfg = Obj("c", {"n": 4, "mode": 1})
    assert ev("cfg.n > 3 && cfg.mode", cfg=cfg) is True
    assert ev('$sformatf("agt_%0d", i)', i=3) == "agt_3"
    assert ev('$sformatf("agt_%0d", i)') == "agt_*"
    arr = ArrayVal(5)
    assert ev("a.size()", a=arr) == 5
