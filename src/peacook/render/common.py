"""Préparation commune des vues : arbre d'instances, états par test, arêtes filtrées, palette."""
from __future__ import annotations

from dataclasses import dataclass

from ..resolve.uvm_kb import ROLE_COLORS

ROLE_ORDER = ["test", "env", "reg_block", "agent", "virtual_sequencer", "sequencer", "driver", "monitor",
              "ref_model", "predictor", "scoreboard", "subscriber", "fifo", "component"]
INACTIVE = {"fill": "#f0f0f0", "stroke": "#bdbdbd", "font": "#9e9e9e"}
COND_STROKE = "#d35400"
PROTO_COLOR = {"analysis": "#2471a3", "seq_item": "#ca6f1e", "handle": "#7d3c98"}


def color_of(role: str) -> str:
    return ROLE_COLORS.get(role, "#ececec")


def safe(s: str) -> str:
    return s.replace('"', "'").replace("\\", "/")


@dataclass
class Edge:
    src: str
    dst: str
    label: str
    protocol: str
    active: bool
    conditional: bool
    kind: str = "flow"


class View:
    """Une vue de l'environnement : test=None -> schéma de référence (surensemble)."""

    def __init__(self, arch: dict, test: str | None = None, hide_inactive: bool = False, raw: bool = False):
        self.arch, self.env, self.test = arch, arch["environment"], test
        self.hide, self.raw = hide_inactive, raw
        self.by_id = {i["id"]: i for i in self.env["instances"]}
        self.kids: dict[str, list[str]] = {}
        for i in self.env["instances"]:
            if i["parent"]:
                self.kids.setdefault(i["parent"], []).append(i["id"])
        self.visible = {i["id"] for i in self.env["instances"] if self._vis(i)}

    # ----- états
    def active(self, inst: dict) -> bool:
        if self.test is None:
            return True
        return inst["states"][self.test]["active"]

    def _vis(self, inst) -> bool:
        if self.test is not None and not inst["states"][self.test]["present"] and self.hide:
            return False
        return not (self.hide and self.test is not None and not self.active(inst))

    def effective(self, inst: dict) -> str:
        if self.test is not None:
            e = inst["states"][self.test]["effective_type"]
            if e:
                return e
        return inst["declared_type"] if inst["id"] != self.env["root"] else "uvm_test"

    def label(self, inst: dict) -> str:
        if inst["id"] == self.env["root"]:
            return f"uvm_test_top : {self.test}" if self.test else "uvm_test_top"
        eff = self.effective(inst)
        decl = inst["declared_type"]
        t = eff
        if self.test is not None and inst["states"][self.test]["overridden"]:
            t = f"{eff} (override)"
        elif self.test is None and inst["overridden_in"]:
            t = f"{decl} (override*)"
        arr = " ×N" if (inst.get("array") or {}).get("unresolved") else ""
        return f"{inst['name']}{arr} : {t}"

    def role_color(self, inst) -> str:
        return color_of(inst["role"])

    def children(self, iid: str) -> list[str]:
        return [k for k in self.kids.get(iid, []) if k in self.visible]

    def roots(self) -> list[str]:
        return [self.env["root"]]

    def ordered_children(self, iid):
        ks = self.children(iid)
        return sorted(ks, key=lambda k: (ROLE_ORDER.index(self.by_id[k]["role"]) if self.by_id[k]["role"] in ROLE_ORDER
                                          else 99))

    def style_of(self, inst: dict) -> dict:
        """Style d'un nœud : active / conditional / inactive."""
        if self.test is not None and not self.active(inst):
            return {"kind": "inactive", **INACTIVE}
        return {"kind": "conditional" if (self.test is None and inst["conditional"]) else "normal",
                "fill": self.role_color(inst), "stroke": COND_STROKE if (self.test is None and inst["conditional"]) else "#555555",
                "font": "#000000"}

    # ----- arêtes
    def edges(self) -> list[Edge]:
        out: list[Edge] = []
        conns = self.env["connections"] if self.raw else self.env["flat_connections"]
        for c in conns:
            s, d = (c["src"] if self.raw else c["from"]), (c["dst"] if self.raw else c["to"])
            if s["inst"] not in self.visible or d["inst"] not in self.visible:
                continue
            act = c["states"][self.test] if self.test else True
            if self.hide and self.test and not act:
                continue
            cond = self.test is None and not all(c["states"].values())
            lab = c["txn"] or c["protocol"]
            out.append(Edge(s["inst"], d["inst"], lab or "", c["protocol"], act, cond))
        for l in self.env["handle_links"]:
            if l["owner"] not in self.visible or l["target"] not in self.visible:
                continue
            act = l["states"][self.test] if self.test else True
            if self.hide and self.test and not act:
                continue
            out.append(Edge(l["owner"], l["target"], l["handle"], "handle", act,
                            self.test is None and not all(l["states"].values()), "handle"))
        return out

    def edge_color(self, e: Edge) -> str:
        return "#bdbdbd" if (self.test and not e.active) else PROTO_COLOR.get(e.protocol, "#555555")

    # ----- noms de fichiers
    @property
    def tag(self) -> str:
        return self.test or "all"
