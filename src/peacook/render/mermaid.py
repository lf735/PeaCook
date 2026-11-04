"""Rendus Mermaid : bloc UVM, UML des classes, séquences, harnais."""
from __future__ import annotations

from .common import COND_STROKE, INACTIVE, View, safe


def _lbl(s: str) -> str:
    return safe(s).replace("#", "#35;").replace("<", "&lt;").replace(">", "&gt;")


def block(view: View) -> str:
    ids: dict[str, str] = {}
    lines = ["flowchart LR"]
    styles: list[str] = []

    def nid(i: str) -> str:
        return ids.setdefault(i, f"n{len(ids)}")

    def emit(i: str, ind: str):
        inst = view.by_id[i]
        n = nid(i)
        kids = view.ordered_children(i)
        if kids:
            lines.append(f'{ind}subgraph {n}["{_lbl(view.label(inst))}"]')
            for k in kids:
                emit(k, ind + "  ")
            lines.append(f"{ind}end")
        else:
            lines.append(f'{ind}{n}["{_lbl(view.label(inst))}"]')
        st = view.style_of(inst)
        extra = ",stroke-dasharray:5 4" if st["kind"] in ("conditional", "inactive") else ""
        styles.append(f"style {n} fill:{st['fill']},stroke:{st['stroke']},color:{st['font']}{extra}")

    for r in view.roots():
        emit(r, "  ")
    edges = view.edges()
    link_styles = []
    for k, e in enumerate(edges):
        a, b = nid(e.src), nid(e.dst)
        arrow = "-.->" if (e.kind == "handle" or e.conditional or (view.test and not e.active)) else "-->"
        lab = _lbl(e.label)
        lines.append(f'  {a} {arrow}|"{lab}"| {b}' if lab else f"  {a} {arrow} {b}")
        link_styles.append(f"linkStyle {k} stroke:{view.edge_color(e)},color:{view.edge_color(e)}")
    lines += ["  " + s for s in styles + link_styles]
    return "\n".join(lines) + "\n"


def hierarchy(view: View) -> str:
    """Arbre de hiérarchie en flowchart Mermaid (une branche par instance)."""
    ids = {}
    lines = ["flowchart TD"]

    def nid(i):
        return ids.setdefault(i, f"h{len(ids)}")

    def emit(i):
        inst = view.by_id[i]
        st = view.style_of(inst)
        lines.append(f'  {nid(i)}["{_lbl(view.label(inst))}"]')
        extra = ",stroke-dasharray:5 4" if st["kind"] != "normal" else ""
        lines.append(f"  style {nid(i)} fill:{st['fill']},stroke:{st['stroke']},color:{st['font']}{extra}")
        for k in view.ordered_children(i):
            lines.append(f"  {nid(i)} --> {nid(k)}")
            emit(k)

    for r in view.roots():
        emit(r)
    return "\n".join(lines) + "\n"


def classes(arch: dict, package: str | None = None) -> str:
    lines = ["classDiagram", "  direction LR"]
    names = {c["name"] for c in arch["classes"] if not package or c["package"] == package}
    ext = set()
    for c in arch["classes"]:
        if c["name"] not in names:
            continue
        lines.append(f"  class {c['name']} {{")
        lines.append(f"    <<{c['role']}>>")
        for p in c["ports"]:
            lines.append(f"    +{p['kind']} {p['name']} : {_cl(p['protocol'])}~{_cl(p['txn'] or '')}~")
        for h in c["config_members"] + c["handles"]:
            lines.append(f"    +{_cl(h['type'])} {h['name']}")
        for v in c["vifs"]:
            lines.append(f"    +{_cl(v['type'])} {v['name']}")
        lines.append("  }")
    for c in arch["classes"]:
        if c["name"] not in names:
            continue
        if c["base"]:
            b = c["base"].split("#")[0].strip()
            if b not in names and b not in ext:
                ext.add(b)
                lines.append(f"  class {b}")
            lines.append(f"  {b} <|-- {c['name']}")
        for ch in c["children"]:
            t = ch["type"].split("#")[0].strip()
            if t in names:
                lines.append(f"  {c['name']} *-- {t} : {_cl(ch['member'])}")
    return "\n".join(lines) + "\n"


def _cl(s: str) -> str:
    return s.replace("#", "").replace("(", "").replace(")", "").replace("<", "").replace(">", "").replace(",", " ").replace(" ", "_").strip("_")


def sequences(arch: dict) -> str:
    env = arch["environment"]
    lines = ["flowchart LR"]
    ids = {}

    def nid(x):
        return ids.setdefault(x, f"s{len(ids)}")

    seen = set()
    for r in env["sequences"]:
        a = nid(r["started_by"])
        lines.append(f'  {a}["{_lbl(r["started_by"].split(":", 1)[1])}"]') if a not in seen else None
        seen.add(a)
        s = nid(r["seq"])
        if s not in seen:
            seen.add(s)
            lines.append(f'  {s}(["{_lbl(r["seq_name"])}\\n{_lbl(r["item"] or "")}"])')
        lines.append(f"  {a} -->|start| {s}")
        if r["on"]:
            o = nid(r["on"])
            if o not in seen:
                seen.add(o)
                lines.append(f'  {o}[/"{_lbl(r["on"].split(":", 1)[1])}"/]')
            lines.append(f"  {s} -.->|on| {o}")
    for l in env["handle_links"]:
        a, b = nid(l["owner"]), nid(l["target"])
        for x, i in ((a, l["owner"]), (b, l["target"])):
            if x not in seen:
                seen.add(x)
                lines.append(f'  {x}[/"{_lbl(i.split(":", 1)[1])}"/]')
        lines.append(f"  {a} -.->|{_lbl(l['handle'])}| {b}")
    return "\n".join(lines) + "\n"


def harness(arch: dict) -> str:
    lines = ["flowchart LR"]
    for t in arch["harness"]["tops"]:
        lines.append(f'  subgraph top_{t["name"]}["{t["name"]}"]')
        for i in t["interfaces"]:
            lines.append(f'    if_{i["name"]}[["{_lbl(i["name"])} : {_lbl(i["type"])}"]]')
        for d in t["duts"]:
            lines.append(f'    dut_{d["name"]}["{_lbl(d["name"])} : {_lbl(d["type"])}"]')
            for ifn in d["interfaces"]:
                lines.append(f"    if_{ifn} --- dut_{d['name']}")
        lines.append("  end")
        for k, v in enumerate(t["vif_sets"]):
            tgt = f"tgt{k}"
            lines.append(f'  {tgt}["{_lbl(v["pattern"])}"]')
            if v["interface_instance"]:
                lines.append(f"  if_{v['interface_instance']} -->|{_lbl(v['field'])}| {tgt}")
    return "\n".join(lines) + "\n"
