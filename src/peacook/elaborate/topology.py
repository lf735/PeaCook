"""Élaboration de la topologie UVM d'un test par interprétation symbolique de new/build_phase/connect_phase.

Principe : toutes les branches sont parcourues. Une branche dont la condition est évaluée à faux est exécutée en
mode « fantôme » (act=False) : les instances sont créées mais marquées inactives (elles seront grisées dans les
schémas) et les effets de bord (config_db, overrides, affectations) ne sont pas appliqués.
"""
from __future__ import annotations

import re
from collections import namedtuple
from dataclasses import dataclass, field

from ..extract import textutil as tu
from ..extract.facts import Facts, PHASE_METHODS
from ..resolve import uvm_kb as kb
from ..resolve.types import TypeModel, base_name
from ..resolve.values import (UNKNOWN, ArrayVal, Evaluator, InstRef, Obj, glob_match, sformatf, truth)

St = namedtuple("St", "act unres guards")
MISSING = Evaluator.MISSING
PHASES_AFTER = [p for p in PHASE_METHODS if p not in ("build_phase", "connect_phase")]


@dataclass
class Inst:
    path: str
    name: str
    declared: str
    effective: str
    role: str
    parent: str | None
    active: bool = True
    unresolved: bool = False
    guards: list = field(default_factory=list)
    array: dict | None = None
    loc: str = ""
    children: list = field(default_factory=list)
    scope: dict = field(default_factory=dict)
    pending: list = field(default_factory=list)
    override: dict | None = None
    cls: str = ""


@dataclass
class Topology:
    test: str
    insts: dict = field(default_factory=dict)
    conns: list = field(default_factory=list)
    cfg_sets: list = field(default_factory=list)
    cfg_gets: list = field(default_factory=list)
    overrides: list = field(default_factory=list)
    applied_overrides: list = field(default_factory=list)
    links: list = field(default_factory=list)
    starts: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)


class Ctx:
    enums: dict

    def __init__(self, el: "Elaborator", inst: Inst):
        self.el, self.inst = el, inst
        self.enums = el.tm.enums

    def lookup(self, name):
        if name in self.inst.scope:
            v = self.inst.scope[name]
            return UNKNOWN if v is None else v
        return MISSING

    def member(self, cur, name):
        if isinstance(cur, Obj):
            return cur.fields.get(name, UNKNOWN)
        if isinstance(cur, InstRef):
            child = self.el.top.insts.get(cur.path)
            if child is not None:
                v = child.scope.get(name)
                if isinstance(v, (InstRef, Obj)):
                    return v
                p = f"{cur.path}.{name}"
                if p in self.el.top.insts:
                    return InstRef(p)
        return UNKNOWN

    def index(self, cur, idx):
        if isinstance(cur, ArrayVal):
            if idx is UNKNOWN:
                return cur.items.get("?", UNKNOWN)
            return cur.items.get(idx, UNKNOWN)
        return UNKNOWN

    def call(self, recv, name, args):
        if recv is None:
            if name == "get_is_active":
                return self.el.is_active(self.inst)
            if name == "$sformatf":
                return sformatf(args[0], args[1:]) if args else UNKNOWN
            if name in ("$bits", "$clog2") and args and isinstance(args[0], int):
                return max(args[0] - 1, 0).bit_length() if name == "$clog2" else UNKNOWN
            return UNKNOWN
        if isinstance(recv, ArrayVal) and name == "size":
            return recv.size
        return UNKNOWN


class Elaborator:
    def __init__(self, tm: TypeModel, facts: Facts, max_expand: int = 64):
        self.tm, self.f, self.max_expand = tm, facts, max_expand
        self.top: Topology = None  # type: ignore
        self._seq = 0

    # ------------------------------------------------------------------ API
    def run(self, test_cls: str, modules=None) -> Topology:
        self.top = Topology(test_cls)
        self._seq = 0
        if modules:
            self.run_top_modules(modules)
        root = Inst("uvm_test_top", "uvm_test_top", "uvm_test", test_cls, "test", None,
                    cls=test_cls, loc=self.f.classes[test_cls].loc if test_cls in self.f.classes else "")
        self.top.insts[root.path] = root
        self.elaborate(root)
        return self.top

    def run_top_modules(self, modules):
        for m in modules:
            pseudo = Inst("", "$root", "", "", "module", None, scope={})
            for op in m.ops:
                if op["op"] == "if":
                    self.exec_ops(pseudo, [op], St(True, False, ()), None)
                elif op["op"] == "cfg":
                    self.exec_ops(pseudo, [op], St(True, False, ()), None)

    # ------------------------------------------------------------ helpers
    def ev(self, inst: Inst, expr):
        return Evaluator(Ctx(self, inst)).eval(expr) if expr is not None else UNKNOWN

    def is_active(self, inst: Inst):
        v = inst.scope.get("is_active")
        if isinstance(v, int) and not isinstance(v, bool):
            return v
        e = self.cfg_lookup(inst.path, "is_active", None)
        if e is not None:
            return e["_val"] if isinstance(e["_val"], int) else UNKNOWN
        return 1

    def init_scope(self, cls_name: str) -> dict:
        scope: dict = {}
        for cn in reversed(self.tm.chain(cls_name)):
            c = self.f.classes.get(cn)
            if not c:
                continue
            dummy = Inst("", "", "", "", "", None)
            for mname, m in c.members.items():
                dims, init = m["dims"], m["init"]
                if dims:
                    mm = re.match(r"\[\s*(\d+)\s*\]", dims)
                    scope[mname] = ArrayVal(int(mm.group(1)) if mm else UNKNOWN)
                elif init:
                    v = self.ev(dummy, init)
                    scope[mname] = v
                else:
                    scope[mname] = None
        return scope

    def new_obj(self, type_name: str, loc: str) -> Obj:
        n, _ = self.tm.resolve(type_name)
        o = Obj(n, loc=loc)
        o.fields = {k: v for k, v in self.init_scope(n).items() if not isinstance(v, ArrayVal)}
        return o

    # -------------------------------------------------------- config_db
    def cfg_lookup(self, target_path: str, field_: str, type_: str | None):
        best, bkey = None, None
        for e in self.top.cfg_sets:
            if e["field"] != field_:
                continue
            if type_ and not self._types_compat(e["type"], type_):
                continue
            if not glob_match(e["pattern"], target_path):
                continue
            key = (e["depth"], -e["seq"])
            if bkey is None or key < bkey:
                best, bkey = e, key
        return best

    def _types_compat(self, a: str, b: str) -> bool:
        def norm(t):
            t = tu.squash(t or "")
            virt = t.startswith("virtual")
            return ("v:" if virt else "") + base_name(self.tm.resolve(t)[0] or t)
        return norm(a) == norm(b)

    def ctx_path(self, inst: Inst, ctx_expr: str):
        c = (ctx_expr or "").strip().replace("this.", "")
        if c in ("this", ""):
            return inst.path
        if c in ("null", "uvm_root::get()", "uvm_top", "uvm_root::get ()"):
            return ""
        r = self.resolve_ep(inst, c)
        if r and r[0] is not None and r[1] is None:
            return r[0]
        return None

    def do_cfg(self, inst: Inst, o: dict, st: St):
        field_ = self.ev(inst, o["field"])
        path = self.ev(inst, o["path"]) if o["path"] else ""
        if path is UNKNOWN:
            path = "*"
        if field_ is UNKNOWN or not isinstance(field_, str):
            field_ = tu.strip_quotes(o["field"])
        cpath = self.ctx_path(inst, o["ctx"])
        if cpath is None:
            self.top.diagnostics.append({"severity": "info", "code": "CFG_CTX_UNRESOLVED",
                                         "message": f"contexte config_db non résolu: {o['ctx']}", "loc": o["loc"]})
            return
        if o["kind"] == "set":
            if not st.act:
                return
            val = self.ev(inst, o["value"])
            if val is UNKNOWN:
                val_repr = tu.squash(o["value"] or "")
            elif isinstance(val, Obj):
                val_repr = f"{val.type}#{val.id}"
            elif isinstance(val, (InstRef, ArrayVal)):
                val_repr = str(val)
            else:
                val_repr = str(val)
            pattern = f"{cpath}.{path}" if (cpath and path) else (cpath or path)
            self._seq += 1
            self.top.cfg_sets.append({"seq": self._seq, "setter": inst.path, "setter_class": inst.cls,
                                      "pattern": pattern, "field": field_, "type": tu.squash(o["type"]),
                                      "value": val_repr, "_val": val, "depth": cpath.count(".") + 1 if cpath else 0,
                                      "loc": o["loc"], "db": o["db"]})
        else:
            target = f"{cpath}.{path}" if (cpath and path) else (cpath or path)
            e = self.cfg_lookup(target, field_, o["type"])
            if e is not None and o.get("value"):
                self.assign_lhs(inst, o["value"].replace("this.", ""), e["_val"], force=True)
            if st.act:
                self.top.cfg_gets.append({"getter": inst.path, "getter_class": inst.cls, "target": target,
                                          "field": field_, "type": tu.squash(o["type"]), "loc": o["loc"],
                                          "matched": (e["seq"] if e else None), "db": o["db"]})

    # ---------------------------------------------------- factory overrides
    def do_override(self, inst: Inst, o: dict, st: St):
        if not st.act:
            return
        orig = base_name(self.tm.resolve(o["orig"])[0] or o["orig"])
        over = base_name(self.tm.resolve(o["over"])[0] or o["over"])
        orig = self.tm.registered.get(orig, orig)
        over = self.tm.registered.get(over, over)
        path = o["path"] or ""
        if o["scope"] == "inst":
            ctx = (o["ctx"] or "").strip()
            if ctx == "this":
                path = f"{inst.path}.{path}" if path else inst.path
        self._seq += 1
        self.top.overrides.append({"seq": self._seq, "scope": o["scope"], "orig": orig, "over": over, "path": path,
                                   "by": inst.path, "loc": o["loc"]})

    def effective_type(self, declared: str, path: str):
        cur_full = declared
        cur = base_name(self.tm.resolve(declared)[0] or declared)
        cur = self.tm.registered.get(cur, cur)
        hit = None
        for ov in reversed(self.top.overrides):
            if ov["scope"] == "inst" and ov["orig"] == cur and glob_match(ov["path"], path):
                hit = ov
                break
        if hit is None:
            for ov in reversed(self.top.overrides):
                if ov["scope"] == "type" and ov["orig"] == cur:
                    hit = ov
                    break
        if hit:
            return hit["over"], hit
        return cur_full, None

    # ------------------------------------------------------ path resolution
    @staticmethod
    def _segments(text: str) -> list[str]:
        segs, depth, cur = [], 0, []
        for ch in text:
            if ch in "([":
                depth += 1
            elif ch in ")]":
                depth -= 1
            if ch == "." and depth == 0:
                segs.append("".join(cur))
                cur = []
            else:
                cur.append(ch)
        segs.append("".join(cur))
        return [s.strip() for s in segs if s.strip()]

    def resolve_ep(self, inst: Inst, text: str):
        """-> (chemin d'instance, port|None) ou None."""
        text = text.strip().replace("this.", "")
        segs = self._segments(text)
        if not segs:
            return None
        ctx = Ctx(self, inst)
        m = re.match(r"^(\w+)\s*(?:\[(.*)\])?$", segs[0])
        if not m:
            return None
        name, idx = m.group(1), m.group(2)
        if name in inst.scope:
            val = inst.scope[name]
            if idx is not None:
                val = ctx.index(val, self.ev(inst, idx))
            if isinstance(val, InstRef):
                path, rest = val.path, segs[1:]
            elif idx is None and name in self.tm.ports(inst.effective):
                path, rest = inst.path, segs
            else:
                return None
        else:
            path, rest = inst.path, segs
        while rest:
            m = re.match(r"^(\w+)\s*(?:\[(.*)\])?$", rest[0])
            if not m:
                return None
            nm, idx = m.group(1), m.group(2)
            child = self.top.insts.get(path)
            v = child.scope.get(nm) if child else None
            if idx is not None and v is not None:
                v = ctx.index(v, self.ev(inst, idx))
            if isinstance(v, InstRef):
                path, rest = v.path, rest[1:]
                continue
            if f"{path}.{nm}" in self.top.insts:
                path, rest = f"{path}.{nm}", rest[1:]
                continue
            break
        return path, (".".join(rest) if rest else None)

    # ------------------------------------------------------- assignments
    def assign_lhs(self, inst: Inst, lhs: str, value, force=False):
        segs = self._segments(lhs.replace("this.", ""))
        if not segs:
            return
        m = re.match(r"^(\w+)\s*(?:\[(.*)\])?$", segs[0])
        if not m:
            return
        name, idx = m.group(1), m.group(2)
        ctx = Ctx(self, inst)
        if len(segs) == 1:
            if idx is not None:
                arr = inst.scope.get(name)
                if not isinstance(arr, ArrayVal):
                    arr = inst.scope[name] = ArrayVal()
                i = self.ev(inst, idx)
                arr.items["?" if i is UNKNOWN else i] = value
            else:
                inst.scope[name] = value
            return
        cur = inst.scope.get(name)
        if idx is not None:
            cur = ctx.index(cur, self.ev(inst, idx))
        for seg in segs[1:-1]:
            cur = ctx.member(cur, seg.split("[")[0])
        last = segs[-1].split("[")[0]
        if isinstance(cur, Obj):
            cur.fields[last] = value
        elif isinstance(cur, InstRef):
            child = self.top.insts.get(cur.path)
            if child is not None and isinstance(value, InstRef):
                self.top.links.append({"owner": cur.path, "handle": ".".join(segs[1:]), "target": value.path,
                                       "by": inst.path})

    # --------------------------------------------------------- exécution
    def exec_ops(self, inst: Inst, ops: list, st: St, mc):
        for o in ops:
            k = o["op"]
            if k == "if":
                self.exec_if(inst, o, st, mc)
            elif k == "loop":
                self.exec_loop(inst, o, st, mc)
            elif k == "create":
                self.do_create(inst, o, st)
            elif k == "newarray":
                size = self.ev(inst, o["size"])
                arr = ArrayVal(size if isinstance(size, int) else UNKNOWN)
                if st.act:
                    self.assign_lhs(inst, o["var"], arr)
            elif k == "assign":
                self.do_assign(inst, o, st)
            elif k == "cfg":
                self.do_cfg(inst, o, st)
            elif k == "override":
                self.do_override(inst, o, st)
            elif k == "connect":
                self.do_connect(inst, o, st)
            elif k == "start":
                self.do_start(inst, o, st)
            elif k == "super" and mc:
                chain, idx = mc
                if idx + 1 < len(chain):
                    self.exec_ops(inst, chain[idx + 1][1]["ops"], st, (chain, idx + 1))
            elif k == "localdecl":
                inst.scope.setdefault(o["var"], None)
                inst.scope.setdefault("__types", {})[o["var"]] = o["type"]

    def exec_if(self, inst, o, st, mc):
        v = truth(self.ev(inst, o["cond"]))
        c = o["cond"]
        g_then = st.guards + (c,)
        g_else = st.guards + (f"!({c})",)
        if v is True:
            self.exec_ops(inst, o["then"], St(st.act, st.unres, g_then), mc)
            self.exec_ops(inst, o["else"], St(False, st.unres, g_else), mc)
        elif v is False:
            self.exec_ops(inst, o["then"], St(False, st.unres, g_then), mc)
            self.exec_ops(inst, o["else"], St(st.act, st.unres, g_else), mc)
        else:
            self.exec_ops(inst, o["then"], St(st.act, True, g_then), mc)
            self.exec_ops(inst, o["else"], St(st.act, True, g_else), mc)

    def exec_loop(self, inst, o, st, mc):
        var = o["var"]
        rng = None
        if o["kind"] == "foreach":
            arr = self.ev(inst, o["arr"])
            if isinstance(arr, ArrayVal) and isinstance(arr.size, int):
                rng = range(arr.size)
        elif o["kind"] == "for":
            s, b = self.ev(inst, o["start"]), self.ev(inst, o["bound"])
            if isinstance(s, int) and isinstance(b, int):
                rng = range(s, b + (1 if o["cmp"] == "<=" else 0))
        old = inst.scope.get(var, None)
        if rng is not None and len(rng) <= self.max_expand:
            for i in rng:
                inst.scope[var] = i
                self.exec_ops(inst, o["body"], st, mc)
        else:
            inst.scope[var] = UNKNOWN
            self.exec_ops(inst, o["body"], St(st.act, st.unres or rng is None, st.guards), mc)
        inst.scope[var] = old

    def do_assign(self, inst, o, st):
        if not st.act:
            return
        val = self.ev(inst, o["rhs"])
        lhs = o["lhs"]
        self.assign_lhs(inst, lhs, val)

    def do_start(self, inst, o, st):
        if not st.act:
            return
        seq = inst.scope.get(o["seq"].split(".")[0])
        if not isinstance(seq, Obj):
            return
        on = o["on"]
        r = self.resolve_ep(inst, on) if on else None
        self.top.starts.append({"seq": seq.type, "on": r[0] if r and r[1] is None else None,
                                "on_expr": on, "by": inst.path, "loc": o["loc"]})

    def do_connect(self, inst, o, st):
        a = self.resolve_ep(inst, o["src"])
        b = self.resolve_ep(inst, o["dst"])
        if not a or not b:
            self.top.diagnostics.append({"severity": "info", "code": "CONNECT_UNRESOLVED",
                                         "message": f"connexion non résolue: {o['src']} -> {o['dst']}", "loc": o["loc"]})
            return
        ia, ib = self.top.insts.get(a[0]), self.top.insts.get(b[0])
        act = st.act and (ia is None or ia.active) and (ib is None or ib.active)
        self.top.conns.append({"src": {"inst": a[0], "port": a[1]}, "dst": {"inst": b[0], "port": b[1]},
                               "active": act, "unresolved": st.unres, "guards": list(st.guards), "loc": o["loc"],
                               "by": inst.path})

    # ----------------------------------------------------------- création
    def declared_type_of(self, inst: Inst, var: str) -> str | None:
        base = re.match(r"^\s*(?:this\.)?(\w+)", var).group(1)
        lt = inst.scope.get("__types", {}).get(base)
        if lt:
            return lt
        m = self.tm.all_members(inst.cls).get(base) if inst.cls else None
        return m["type"] if m else None

    def do_create(self, inst: Inst, o: dict, st: St):
        var = o["var"].replace("this.", "")
        typ = o["type"] or self.declared_type_of(inst, var)
        if not typ:
            return
        n, _ = self.tm.resolve(typ)
        if self.tm.is_port_type(typ) or n in ("covergroup", "mailbox", "semaphore", "event"):
            return
        is_comp = self.tm.is_component(typ) or (n not in self.f.classes and o["parent"] and n.startswith("uvm_"))
        if not is_comp and (o["parent"] and n not in self.f.classes and n not in kb.ROLE_BY_BASE):
            is_comp = True
        if not is_comp:
            if st.act:
                self.assign_lhs(inst, var, self.new_obj(typ, o["loc"]))
            return
        # composant
        name = self.ev(inst, o["name"])
        base = re.match(r"^(\w+)", var).group(1)
        idx_m = re.match(r"^\w+\s*\[(.*)\]\s*$", var)
        array = None
        if idx_m:
            iv = self.ev(inst, idx_m.group(1))
            array = {"member": base, "index": None if iv is UNKNOWN else iv}
        if name is UNKNOWN or not isinstance(name, str):
            name = f"{base}*"
        if "*" in name:
            array = array or {"member": base, "index": None}
            array["unresolved"] = True
        path = f"{inst.path}.{name}"
        old = self.top.insts.get(path)
        if old is not None and (old.active or not st.act):
            self.assign_lhs(inst, var, InstRef(path), force=True)
            return
        eff, hit = self.effective_type(typ, path)
        eff_cls = self.tm.registered.get(base_name(self.tm.resolve(eff)[0] or eff), None)
        child = Inst(path, name, typ, eff, self.tm.role(eff), inst.path, active=st.act and inst.active,
                     unresolved=st.unres, guards=list(st.guards), array=array, loc=o["loc"],
                     cls=eff_cls or self.tm.resolve(eff)[0], override=hit)
        if hit and st.act:
            self.top.applied_overrides.append({"path": path, "orig": hit["orig"], "over": hit["over"], "loc": hit["loc"]})
        self.top.insts[path] = child
        if path not in inst.children:
            inst.children.append(path)
        child.scope.update(self.init_scope(child.cls) if child.cls in self.f.classes else {})
        inst.pending.append(child)
        arr = inst.scope.get(base)
        if idx_m:
            if not isinstance(arr, ArrayVal):
                arr = inst.scope[base] = ArrayVal()
            arr.items["?" if array["index"] is None else array["index"]] = InstRef(path)
        else:
            inst.scope[base] = InstRef(path)

    # -------------------------------------------------------- élaboration
    def run_method(self, inst: Inst, mname: str, st: St):
        chain = self.tm.method_chain(inst.cls, mname) if inst.cls in self.f.classes else []
        if chain:
            self.exec_ops(inst, chain[0][1]["ops"], st, (chain, 0))

    def elaborate(self, inst: Inst):
        if inst.cls in self.f.classes:
            if not inst.scope:
                inst.scope.update(self.init_scope(inst.cls))
            else:
                for k, v in self.init_scope(inst.cls).items():
                    inst.scope.setdefault(k, v)
        st = St(inst.active, inst.unresolved, tuple(inst.guards))
        base = St(inst.active, False, ())
        self.run_method(inst, "new", base)
        self.run_method(inst, "build_phase", base)
        pend, inst.pending = inst.pending, []
        for ch in pend:
            self.elaborate(ch)
        self.run_method(inst, "connect_phase", base)
        for ph in PHASES_AFTER:
            self.run_method(inst, ph, base)
        _ = st


def elaborate_test(tm: TypeModel, facts: Facts, test: str, modules=None, max_expand=64) -> Topology:
    return Elaborator(tm, facts, max_expand).run(test, modules)
