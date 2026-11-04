"""Résolution des types : typedefs, chaînes d'héritage, rôles, ports (utilisateur + hérités UVM)."""
from __future__ import annotations

import re

from ..extract import textutil as tu
from ..extract.facts import ClassFacts, Facts
from . import uvm_kb as kb


def base_name(t: str | None) -> str:
    if not t:
        return ""
    t = re.sub(r"^(virtual|const|automatic)\s+", "", t.strip())
    return tu.split_type(t)[0].split("::")[-1]


def subst(text: str | None, bind: dict) -> str | None:
    if not text or not bind:
        return text
    return re.sub(r"\b\w+\b", lambda m: bind.get(m.group(0), m.group(0)), text)


class TypeModel:
    def __init__(self, facts: Facts):
        self.f = facts
        self.enums: dict[str, int] = dict(kb.ENUMS)
        for _, t in facts.typedefs.items():
            if t.startswith("enum"):
                self._enum(t)
        self.registered: dict[str, str] = {}
        for c in facts.classes.values():
            self.registered[c.registered or c.name] = c.name
            self.registered.setdefault(c.name, c.name)
        self._ports_cache: dict[str, dict] = {}

    def _enum(self, t: str):
        m = re.search(r"\{(.*)\}", t, re.S)
        if not m:
            return
        n = 0
        for item in tu.split_args(m.group(1)):
            mm = re.match(r"(\w+)\s*(?:=\s*(.+))?$", item.strip())
            if mm:
                if mm.group(2):
                    try:
                        n = int(mm.group(2).replace("'", "").replace("_", ""), 0)
                    except ValueError:
                        pass
                self.enums.setdefault(mm.group(1), n)
                n += 1

    # ----- typedefs
    def resolve(self, t: str | None, depth=0) -> tuple[str, str]:
        """'apb_sequencer' -> ('uvm_sequencer', 'apb_item')."""
        if not t:
            return "", ""
        t = re.sub(r"^(virtual|const)\s+", "", tu.squash(t))
        name, params = tu.split_type(t)
        name = name.split("::")[-1]
        td = self.f.typedefs.get(name)
        if td and depth < 8 and not td.startswith(("enum", "struct", "union")):
            n2, p2 = self.resolve(td, depth + 1)
            return n2, (params or p2)
        return name, params

    def cls(self, t: str | None) -> ClassFacts | None:
        n, _ = self.resolve(t)
        return self.f.classes.get(n) or self.f.classes.get(self.registered.get(n, ""))

    # ----- héritage
    def chain(self, name: str) -> list[str]:
        """[classe, parent, ..., base UVM]."""
        out, seen = [], set()
        cur = name
        while cur and cur not in seen:
            seen.add(cur)
            out.append(cur)
            c = self.f.classes.get(cur)
            if not c or not c.base:
                break
            cur, _ = self.resolve(c.base)
        return out

    def uvm_base(self, name: str) -> str | None:
        ch = self.chain(name)
        for n in ch:
            if n not in self.f.classes:
                return n
        return None

    def is_component(self, t: str | None) -> bool:
        n, _ = self.resolve(t)
        if n in self.f.classes:
            ub = self.uvm_base(n)
            return ub in kb.COMPONENT_BASES
        return n in kb.COMPONENT_BASES or n in kb.FIFO_TYPES

    def is_port_type(self, t: str | None) -> bool:
        n, _ = self.resolve(t)
        return n.startswith(kb.PORT_PREFIXES) and n not in self.f.classes or \
            n in self.f.generated_decl_classes or bool(re.match(r"^uvm_\w*_imp_?\w*$", n))

    def role(self, t: str | None) -> str:
        n, _ = self.resolve(t)
        if n in kb.ROLE_BY_BASE:
            r = kb.ROLE_BY_BASE[n]
            return r
        if n in self.f.classes:
            ch = self.chain(n)
            r = None
            for c in ch:
                if c in kb.ROLE_BY_BASE:
                    r = kb.ROLE_BY_BASE[c]
                    break
            r = r or self._heuristic(n)
            c = self.f.classes[n]
            if r == "sequencer" and any(self.role(m["type"]) in ("sequencer", "virtual_sequencer")
                                        for m in self.all_members(n).values()):
                r = "virtual_sequencer"
            if r == "component" and re.search(r"(ref_?model|predictor|golden)", n, re.I):
                r = "ref_model"
            if r == "object" and re.search(r"(cfg|config)", n, re.I):
                r = "config"
            if r == "sequence" and c.p_sequencer and self.role(c.p_sequencer) == "virtual_sequencer":
                r = "virtual_sequence"
            if r == "sequence" and any(self.f.classes[x].p_sequencer and
                                       self.role(self.f.classes[x].p_sequencer) == "virtual_sequencer"
                                       for x in ch if x in self.f.classes):
                r = "virtual_sequence"
            return r
        return self._heuristic(n)

    @staticmethod
    def _heuristic(n: str) -> str:
        for pat, r in (("scoreboard|checker|comparator", "scoreboard"), ("driver|drv", "driver"),
                       ("monitor|mon$", "monitor"), ("agent", "agent"), ("vseqr|virtual_?sequencer", "virtual_sequencer"),
                       ("sequencer|sqr", "sequencer"), ("_env$|^env", "env"), ("test", "test"),
                       ("coverage|cov", "subscriber")):
            if re.search(pat, n, re.I):
                return r
        return "component" if n else "unknown"

    def all_members(self, name: str) -> dict:
        out: dict = {}
        for n in reversed(self.chain(name)):
            c = self.f.classes.get(n)
            if c:
                out.update(c.members)
        return out

    def method_chain(self, name: str, mname: str) -> list[tuple[str, dict]]:
        res = []
        for n in self.chain(name):
            c = self.f.classes.get(n)
            if c and mname in c.methods:
                res.append((n, c.methods[mname]))
        return res

    def class_bind(self, tname: str | None) -> dict:
        """Liaison paramètres de classe -> arguments pour un type 'foo#(a,b)'."""
        n, p = self.resolve(tname)
        c = self.f.classes.get(n)
        if not c or not c.params:
            return {}
        args = tu.split_args(p) if p else []
        bind = {}
        for i, prm in enumerate(c.params):
            if i < len(args) and args[i].strip():
                bind[prm["name"]] = re.sub(r"^\.\w+\((.*)\)$", r"\1", args[i].strip())
            elif prm.get("default"):
                bind[prm["name"]] = prm["default"]
        return bind

    # ----- ports
    def ports(self, tname: str | None) -> dict[str, dict]:
        key = tname or ""
        if key in self._ports_cache:
            return self._ports_cache[key]
        n, p = self.resolve(tname)
        out: dict[str, dict] = {}
        self._ports_cache[key] = out
        bind = self.class_bind(tname)
        if n in self.f.classes:
            for cn in reversed(self.chain(n)):
                c = self.f.classes.get(cn)
                if c:
                    for mname, m in c.members.items():
                        info = self.port_info(m["type"])
                        if info:
                            info["txn"] = subst(info["txn"], bind)
                            out[mname] = info
                    continue
                self._kb_ports(cn, self._base_params_for(n, cn, bind), out)
        else:
            self._kb_ports(n, p, out)
        return out

    def _base_params_for(self, user: str, uvm_cls: str, bind: dict) -> str:
        cur = user
        while cur in self.f.classes:
            c = self.f.classes[cur]
            nxt, _ = self.resolve(c.base)
            if nxt == uvm_cls:
                return subst(self.resolve(c.base)[1] or tu.split_type(c.base or "")[1], self.class_bind_of(cur, bind)) or ""
            cur = nxt
        return ""

    def class_bind_of(self, cls_name: str, outer: dict) -> dict:
        return outer

    def _kb_ports(self, cn: str, params: str, out: dict):
        args = tu.split_args(params) if params else []
        for pname, kind, proto, idx in kb.KB_PORTS.get(cn, []):
            txn = args[idx].strip() if idx is not None and idx < len(args) else None
            out[pname] = {"kind": kind, "protocol": proto, "txn": txn}

    def port_info(self, t: str) -> dict | None:
        if not t:
            return None
        n, p = self.resolve(t)
        if n in kb.FIFO_TYPES or n in self.f.classes:
            return None
        if not (n.startswith("uvm_") and re.search(r"_(port|export|imp)", n) or n in self.f.generated_decl_classes):
            return None
        kind = "port" if re.search(r"_port", n) else "export" if re.search(r"_export", n) else "imp"
        pm = re.search(r"(analysis|get_peek|put|get|peek|transport|master|slave|seq_item)", n)
        args = tu.split_args(p) if p else []
        return {"kind": kind, "protocol": pm.group(1) if pm else "tlm", "txn": args[0].strip() if args else None}

    def txn_of_seq(self, name: str) -> str | None:
        """Type d'item d'une séquence (uvm_sequence #(T))."""
        for cn in self.chain(name):
            c = self.f.classes.get(cn)
            if c is None:
                continue
            bn, bp = self.resolve(c.base)
            if bn in ("uvm_sequence", "uvm_sequence_base", "uvm_reg_sequence") and bp:
                return tu.split_args(bp)[0].strip()
        return None

    def item_of_sequencer(self, t: str | None) -> str | None:
        ps = self.ports(t)
        return ps.get("seq_item_export", {}).get("txn")
