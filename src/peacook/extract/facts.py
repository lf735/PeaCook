"""Extraction des faits UVM depuis les arbres syntaxiques pyslang.

Les corps de méthodes sont convertis en un arbre d'« opérations » (if/boucle/create/connect/config_db/...)
qui est ensuite interprété par l'élaboration. Aucune sémantique d'exécution n'est supposée ici.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pyslang.syntax import SyntaxKind as K
from pyslang.syntax import SyntaxNode

from . import textutil as tu

PHASE_METHODS = {"build_phase", "connect_phase", "end_of_elaboration_phase", "start_of_simulation_phase",
                 "run_phase", "extract_phase", "check_phase", "report_phase", "final_phase", "pre_reset_phase",
                 "reset_phase", "post_reset_phase", "pre_configure_phase", "configure_phase",
                 "post_configure_phase", "pre_main_phase", "main_phase", "post_main_phase",
                 "pre_shutdown_phase", "shutdown_phase", "post_shutdown_phase"}


@dataclass
class ClassFacts:
    name: str
    package: str | None
    base: str | None
    base_params: str
    params: list[dict]
    loc: str
    end_line: int = 0
    members: dict[str, dict] = field(default_factory=dict)
    methods: dict[str, dict] = field(default_factory=dict)
    constraints: list[dict] = field(default_factory=list)
    covergroups: list[dict] = field(default_factory=list)
    typedefs: dict[str, str] = field(default_factory=dict)
    registered: str | None = None        # `uvm_component_utils / object_utils
    p_sequencer: str | None = None
    fields_macro: list[str] = field(default_factory=list)
    raw_starts: list[dict] = field(default_factory=list)
    is_virtual: bool = False


@dataclass
class ModuleFacts:
    name: str
    kind: str
    loc: str
    instances: list[dict] = field(default_factory=list)
    ops: list[dict] = field(default_factory=list)
    modports: list[str] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    run_test: str | None = None


@dataclass
class Facts:
    classes: dict[str, ClassFacts] = field(default_factory=dict)
    modules: dict[str, ModuleFacts] = field(default_factory=dict)
    typedefs: dict[str, str] = field(default_factory=dict)
    packages: dict[str, dict] = field(default_factory=dict)
    diagnostics: list[dict] = field(default_factory=list)
    generated_decl_classes: set[str] = field(default_factory=set)


def _nodes(n):
    return [c for c in n if isinstance(c, SyntaxNode)]


class Extractor:
    def __init__(self, sm):
        self.sm = sm
        self.facts = Facts()
        self._lines: dict[str, list[str]] = {}
        self._pending_methods: list[tuple[str, str, dict]] = []

    # ---------- utilitaires ----------
    def loc(self, node) -> str:
        try:
            s = node.sourceRange.start
            return f"{Path(self.sm.getFileName(s)).as_posix()}:{self.sm.getLineNumber(s)}"
        except Exception:  # noqa: BLE001
            return "?"

    def _line_no(self, node, end=False) -> int:
        try:
            r = node.sourceRange
            return self.sm.getLineNumber(r.end if end else r.start)
        except Exception:  # noqa: BLE001
            return 0

    def _file_lines(self, node) -> list[str]:
        try:
            fn = self.sm.getFileName(node.sourceRange.start)
        except Exception:  # noqa: BLE001
            return []
        if fn not in self._lines:
            try:
                self._lines[fn] = Path(fn).read_text(errors="replace").splitlines()
            except OSError:
                self._lines[fn] = []
        return self._lines[fn]

    # ---------- point d'entrée ----------
    def run(self, trees) -> Facts:
        for t in trees:
            self.walk_top(t.root, None)
        for cname, mname, mfacts in self._pending_methods:
            c = self.facts.classes.get(cname)
            if c is not None and mname not in c.methods:
                c.methods[mname] = mfacts
        return self.facts

    def walk_top(self, node, pkg):
        k = node.kind
        if k == K.PackageDeclaration:
            name = tu.ident(str(node.header.name)) if hasattr(node, "header") else "?"
            imports = re.findall(r"import\s+([\w:\*]+)\s*;", str(node))
            self.facts.packages.setdefault(name, {"name": name, "imports": [], "loc": self.loc(node)})
            self.facts.packages[name]["imports"] += [i.replace("::*", "") for i in imports]
            for c in _nodes(node):
                self.walk_top(c, name)
            return
        if k == K.ClassDeclaration:
            self.parse_class(node, pkg)
            return
        if k in (K.ModuleDeclaration, K.InterfaceDeclaration, K.ProgramDeclaration):
            self.parse_module(node)
            return
        if k == K.TypedefDeclaration:
            m = re.match(r"typedef\s+(.*?)\s+(\w+)\s*(\[.*\])?\s*;?$", tu.squash(str(node)), re.S)
            if m and not m.group(1).startswith("class"):
                self.facts.typedefs[m.group(2)] = m.group(1)
            return
        if k in (K.FunctionDeclaration, K.TaskDeclaration):
            proto = tu.squash(str(node.prototype)) if hasattr(node, "prototype") else ""
            m = re.search(r"(\w+)::(\w+)\s*\(", proto)
            if m:
                ops = self.method_ops(node, m.group(2))
                self._pending_methods.append((m.group(1), m.group(2), self.method_facts(node, m.group(2), ops)))
            return
        for c in _nodes(node):
            self.walk_top(c, pkg)

    # ---------- classes ----------
    def parse_class(self, node, pkg):
        name = tu.ident(str(node.name))
        base, bparams = None, ""
        ext = getattr(node, "extendsClause", None)
        if ext is not None:
            txt = tu.squash(str(ext.baseName))
            base, bparams = tu.split_type(txt)
        params = []
        for c in _nodes(node):
            if c.kind == K.ParameterPortList:
                params = tu.parse_params(str(c))
        if base is None and name.startswith("uvm_"):
            self.facts.generated_decl_classes.add(name)
            return
        cf = ClassFacts(name, pkg, base, bparams, params, self.loc(node), self._line_no(node, True))
        if name in self.facts.classes:
            self.facts.diagnostics.append({"severity": "warning", "code": "DUPLICATE_CLASS",
                                           "message": f"classe {name} définie plusieurs fois", "loc": cf.loc})
            return
        self.facts.classes[name] = cf
        for m in _nodes(node):
            self.class_item(cf, m)
        self.raw_macros(cf, node)

    def class_item(self, cf: ClassFacts, m):
        k = m.kind
        if k == K.ClassPropertyDeclaration:
            for d in _nodes(m):
                if d.kind == K.DataDeclaration:
                    self.member_decl(cf, d, str(m))
        elif k == K.ClassMethodDeclaration:
            for d in _nodes(m):
                if d.kind in (K.FunctionDeclaration, K.TaskDeclaration):
                    nm = tu.method_name(str(d.prototype))
                    ops = self.method_ops(d, nm)
                    cf.methods[nm] = self.method_facts(d, nm, ops)
        elif k == K.ConstraintDeclaration:
            nm = tu.ident(str(_nodes(m)[0])) if _nodes(m) else "?"
            cf.constraints.append({"name": nm, "loc": self.loc(m), "text": tu.squash(str(m))[:200]})
        elif k == K.CovergroupDeclaration:
            t = tu.squash(str(m))
            nm = re.match(r"covergroup\s+(?:extends\s+)?(\w+)", t)
            cf.covergroups.append({
                "name": nm.group(1) if nm else "?", "loc": self.loc(m),
                "coverpoints": re.findall(r"(\w+)\s*:\s*coverpoint\s+([^;{]+)", t),
                "crosses": re.findall(r"(\w+)\s*:\s*cross\s+([^;{]+)", t)})
        elif k == K.TypedefDeclaration:
            mm = re.match(r"typedef\s+(.*?)\s+(\w+)\s*(\[.*\])?\s*;?$", tu.squash(str(m)), re.S)
            if mm and not mm.group(1).startswith("class"):
                cf.typedefs[mm.group(2)] = mm.group(1)
                self.facts.typedefs.setdefault(mm.group(2), mm.group(1))

    def member_decl(self, cf: ClassFacts, d, full_text: str):
        typ = None
        decls = []
        for c in _nodes(d):
            if c.kind == K.Declarator:
                decls.append(c)
            elif typ is None:
                typ = tu.squash(str(c))
        for dc in decls:
            m = re.match(r"\s*(\w+)\s*((?:\[[^\]]*\]\s*)*)\s*(?:=\s*(.*))?$", tu.squash(str(dc)), re.S)
            if not m:
                continue
            cf.members[m.group(1)] = {"type": typ or "?", "dims": (m.group(2) or "").strip(), "init": m.group(3),
                                      "rand": "rand" in full_text.split(typ or " ")[0], "loc": self.loc(dc)}

    def raw_macros(self, cf: ClassFacts, node):
        lines = self._file_lines(node)
        start = self._line_no(node) - 1
        end = self._line_no(node, True)
        if not lines or end <= 0:
            return
        txt = "\n".join(lines[start:end])
        txt_nc = re.sub(r"//[^\n]*", "", txt)
        m = re.search(r"`uvm_(?:component|object)(?:_param)?_utils(?:_begin)?\s*\(\s*(\w+)", txt_nc)
        if m:
            cf.registered = m.group(1)
        m = re.search(r"`uvm_declare_p_sequencer\s*\(\s*([\w#\(\)\s,]+?)\s*\)", txt_nc)
        if m:
            cf.p_sequencer = m.group(1)
        cf.fields_macro = [(m.group(3) if m.group(1) == "enum" and m.group(3) else m.group(2)) for m in
                           re.finditer(r"`uvm_field_(\w+)\s*\(\s*(\w+)\s*(?:,\s*(\w+))?", txt_nc)]
        for mm in re.finditer(r"`uvm_(?:do|create|send|rand_send)(?:_on)(?:_pri)?(?:_with)?\s*\(\s*(\w+)\s*,\s*([^,\)\n]+)", txt_nc):
            cf.raw_starts.append({"seq": mm.group(1), "on": mm.group(2).strip(), "via": "macro"})
        cf.is_virtual = bool(re.match(r"\s*virtual\s+class", txt_nc))

    # ---------- méthodes ----------
    def method_facts(self, d, name, ops):
        body_lines = max(self._line_no(d, True) - self._line_no(d), 0)
        txt = str(d)
        calls = sorted({f"{a}.{b}" for a, b in re.findall(
            r"\b([A-Za-z_][\w\.\[\]]*)\.(write|get|put|peek|try_get|try_put|get_next_item|item_done|try_next_item|"
            r"start|randomize|sample|compare|print|copy|raise_objection|drop_objection)\s*\(", txt)})
        return {"name": name, "kind": "task" if d.kind == K.TaskDeclaration else "function",
                "signature": tu.squash(str(d.prototype)), "loc": self.loc(d), "lines": body_lines,
                "is_phase": name in PHASE_METHODS, "ops": ops, "calls": calls[:40],
                "branches": len(re.findall(r"\b(if|case|for|foreach|while)\b", txt))}

    def method_ops(self, d, mname) -> list[dict]:
        ops: list[dict] = []
        for c in _nodes(d):
            if c.kind == K.FunctionPrototype:
                continue
            self.stmt(c, ops, mname)
        return ops

    # ---------- statements ----------
    def stmt(self, n, ops: list, mname: str):
        k = n.kind
        kids = _nodes(n)
        if k == K.ConditionalStatement:
            pred = tu.squash(str(kids[0])) if kids else ""
            then_ops, else_ops = [], []
            if len(kids) > 1:
                self.stmt(kids[1], then_ops, mname)
            if len(kids) > 2 and kids[2].kind == K.ElseClause:
                for e in _nodes(kids[2]):
                    self.stmt(e, else_ops, mname)
            if "uvm_config_db" in pred or "uvm_resource_db" in pred or "get_config" in pred:
                self.leaf(pred, ops, mname, n)
                ops.extend(then_ops)
                ops.extend(else_ops)
            else:
                self.leaf_calls(pred, ops, n)
                ops.append({"op": "if", "cond": pred, "then": then_ops, "else": else_ops, "loc": self.loc(n)})
        elif k == K.ForeachLoopStatement:
            lst = tu.squash(str(kids[0])) if kids else ""
            m = re.search(r"\(\s*([\w\.]+)\s*\[\s*(\w+)", lst)
            body: list = []
            for b in kids[1:]:
                self.stmt(b, body, mname)
            ops.append({"op": "loop", "kind": "foreach", "arr": m.group(1) if m else None,
                        "var": m.group(2) if m else "i", "start": "0", "bound": None, "cmp": "<", "body": body,
                        "loc": self.loc(n)})
        elif k == K.ForLoopStatement:
            init = tu.squash(str(kids[0])) if kids else ""
            m = re.search(r"(\w+)\s*=\s*(.+)$", init)
            var, start = (m.group(1), m.group(2)) if m else ("i", "0")
            stop = tu.squash(str(kids[1])) if len(kids) > 1 else ""
            mm = re.match(r"\s*\(?\s*" + re.escape(var) + r"\s*(<=|<|!=)\s*(.+?)\)?\s*$", stop)
            body = []
            for b in kids[3:]:
                self.stmt(b, body, mname)
            ops.append({"op": "loop", "kind": "for", "arr": None, "var": var, "start": start,
                        "cmp": mm.group(1) if mm else "<", "bound": mm.group(2) if mm else None,
                        "body": body, "loc": self.loc(n)})
        elif k in (K.LoopStatement, K.DoWhileStatement):
            body = []
            for b in kids:
                self.stmt(b, body, mname)
            ops.append({"op": "loop", "kind": "while", "arr": None, "var": "_", "start": "0", "bound": None,
                        "cmp": "<", "body": body, "loc": self.loc(n)})
        elif k == K.CaseStatement:
            subj = tu.squash(str(kids[0])) if kids else ""
            chain: list = []
            default_ops: list = []
            items = []
            for it in kids[1:]:
                sub = _nodes(it)
                body: list = []
                if it.kind == K.DefaultCaseItem:
                    for b in sub:
                        self.stmt(b, default_ops, mname)
                else:
                    exprs = [tu.squash(str(s)) for s in sub[:-1]]
                    if sub:
                        self.stmt(sub[-1], body, mname)
                    items.append((exprs, body))
            cur = default_ops
            for exprs, body in reversed(items):
                cond = " || ".join(f"({subj}) == ({e})" for e in exprs) or "1"
                cur = [{"op": "if", "cond": cond, "then": body, "else": cur, "loc": self.loc(n)}]
            ops.extend(cur)
        elif k == K.ExpressionStatement or tu.squash(str(n)).startswith("void'"):
            t = tu.squash(str(n)).rstrip(";").strip()
            m = re.match(r"^void'\s*\((.*)\)$", t, re.S)
            self.leaf(m.group(1).strip() if m else t, ops, mname, n)
        elif k == K.DataDeclaration:
            self.local_decl(n, ops, mname)
        elif k in (K.SequentialBlockStatement, K.ParallelBlockStatement) or True:
            for c in kids:
                self.stmt(c, ops, mname)

    def local_decl(self, n, ops, mname):
        typ, decls = None, []
        for c in _nodes(n):
            if c.kind == K.Declarator:
                decls.append(c)
            elif typ is None:
                typ = tu.squash(str(c))
        for dc in decls:
            t = tu.squash(str(dc))
            m = re.match(r"(\w+)\s*(?:=\s*(.*))?$", t, re.S)
            if not m:
                continue
            ops.append({"op": "localdecl", "var": m.group(1), "type": typ, "loc": self.loc(dc)})
            if m.group(2):
                self.leaf(f"{m.group(1)} = {m.group(2)}", ops, mname, dc, decl_type=typ)

    # ---------- feuilles ----------
    def leaf_calls(self, text, ops, node):
        """Appels dans un prédicat (ex: if (!cfg_db::get(...)))."""
        if "uvm_config_db" in text:
            self.leaf(text, ops, "", node)

    def leaf(self, s: str, ops: list, mname: str, node, decl_type: str | None = None):
        loc = self.loc(node)
        if re.match(rf"super\.{re.escape(mname)}\s*\(", s) and mname:
            ops.append({"op": "super", "loc": loc})
            return
        # config_db / resource_db
        for op in tu.find_config_ops(s):
            op["loc"] = loc
            ops.append(op)
        if "uvm_config_db" in s or "uvm_resource_db" in s:
            return
        # factory overrides
        ov = tu.find_overrides(s)
        if ov:
            for o in ov:
                o["loc"] = loc
                ops.append(o)
            return
        # create : lhs = T::type_id::create(args)
        m = re.match(r"^(?:(?P<lhs>[\w\.\[\]\s]+?)\s*=\s*)?(?P<type>[\w:#\(\)\s,\.\$\*]+?)::type_id::create\s*\((?P<args>.*)\)$", s, re.S)
        if m and m.group("lhs"):
            args = tu.split_args(m.group("args"))
            ops.append({"op": "create", "var": m.group("lhs").strip(), "type": tu.squash(m.group("type")),
                        "name": args[0] if args else '""', "parent": len(args) > 1, "loc": loc})
            return
        m = re.match(r"^(?P<lhs>[\w\.\[\]\s]+?)\s*=\s*new\s*(?:\[(?P<sz>.*?)\])?\s*(?:\((?P<args>.*)\))?$", s, re.S)
        if m:
            args = tu.split_args(m.group("args") or "")
            if m.group("sz") is not None:
                ops.append({"op": "newarray", "var": m.group("lhs").strip(), "size": m.group("sz"), "loc": loc})
            else:
                ops.append({"op": "create", "var": m.group("lhs").strip(), "type": decl_type,
                            "name": args[0] if args else '""', "parent": len(args) > 1, "loc": loc, "via_new": True})
            return
        m = re.match(r"^(?P<a>[\w\.\[\]\(\)\s]+?)\.connect\s*\((?P<b>.*)\)$", s, re.S)
        if m:
            ops.append({"op": "connect", "src": m.group("a").strip().replace("this.", ""),
                        "dst": m.group("b").strip().replace("this.", ""), "loc": loc})
            return
        m = re.match(r"^(?P<a>[\w\.\[\]\(\)]+?)\.start\s*\((?P<args>.*)\)$", s, re.S)
        if m:
            args = tu.split_args(m.group("args"))
            ops.append({"op": "start", "seq": m.group("a"), "on": args[0] if args else None, "loc": loc})
            return
        m = re.match(r"^\$sformat\s*\(\s*(?P<v>[\w\.\[\]]+)\s*,\s*(?P<rest>.*)\)$", s, re.S)
        if m:
            ops.append({"op": "assign", "lhs": m.group("v"), "rhs": f"$sformatf({m.group('rest')})", "loc": loc})
            return
        m = re.match(r"^run_test\s*\((?P<a>.*)\)$", s)
        if m:
            ops.append({"op": "run_test", "arg": tu.strip_quotes(m.group("a").strip()) or None, "loc": loc})
            return
        m = re.match(r"^\$cast\s*\(\s*([\w\.\[\]]+)\s*,\s*(.*)\)$", s)
        if m:
            ops.append({"op": "assign", "lhs": m.group(1), "rhs": m.group(2), "loc": loc, "cast": True})
            return
        m = re.match(r"^(?P<lhs>[\w\.\[\]]+)\s*=(?!=)\s*(?P<rhs>.+)$", s, re.S)
        if m:
            ops.append({"op": "assign", "lhs": m.group("lhs"), "rhs": m.group("rhs").strip(), "loc": loc})

    # ---------- modules / interfaces ----------
    def parse_module(self, node):
        kind = {K.ModuleDeclaration: "module", K.InterfaceDeclaration: "interface"}.get(node.kind, "program")
        name = tu.ident(str(node.header.name))
        mf = ModuleFacts(name, kind, self.loc(node))
        txt = str(node)
        mf.modports = re.findall(r"modport\s+(\w+)", txt)
        mf.signals = sorted(set(re.findall(r"\b(?:logic|wire|bit|reg)\b(?:\s*\[[^\]]*\])?\s+(\w+)\s*[;,=]", txt)))
        self._module_members(node, mf)
        self.facts.modules[name] = mf

    def _module_members(self, node, mf: ModuleFacts):
        for c in _nodes(node):
            if c.kind == K.HierarchyInstantiation:
                typ = None
                for t in c:
                    if not isinstance(t, SyntaxNode):
                        typ = typ or str(t).strip() or None
                        break
                if typ is None:
                    typ = tu.ident(str(c))
                for hi in _nodes(c):
                    if hi.kind == K.HierarchicalInstance:
                        nm = tu.ident(str(_nodes(hi)[0])) if _nodes(hi) else "?"
                        conns = re.findall(r"\.(\w+)\s*\(\s*([^()]*)\)", str(hi))
                        ordered = [x for x in tu.split_args(re.sub(r"^\w+\s*(?:\[.*?\])?\s*\(", "", str(hi))[:-1])] if not conns else []
                        mf.instances.append({"name": nm, "type": typ, "loc": self.loc(hi),
                                             "ports": {a: b.strip() for a, b in conns}, "ordered": ordered})
            elif c.kind == K.ClassDeclaration:   # classes (tests...) déclarées dans un module testbench
                self.parse_class(c, mf.name)
            elif c.kind == K.TypedefDeclaration:
                self.walk_top(c, None)
            elif c.kind in (K.InitialBlock, K.AlwaysBlock):
                ops: list = []
                for s in _nodes(c):
                    self.stmt(s, ops, "")
                mf.ops += ops
                for o in tu.iter_ops(ops):
                    if o["op"] == "run_test":
                        mf.run_test = o["arg"] or ""
            else:
                self._module_members(c, mf)


def extract(trees, sm) -> Facts:
    return Extractor(sm).run(trees)
