"""Rendus Graphviz (DOT en texte pur) + conversion SVG si `dot` est disponible."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .common import INACTIVE, View, safe

DOT_CANDIDATES = [r"C:\Program Files\Graphviz\bin\dot.exe", r"C:\Program Files (x86)\Graphviz\bin\dot.exe"]


def find_dot() -> str | None:
    p = shutil.which("dot")
    if p:
        return p
    for c in DOT_CANDIDATES:
        if os.path.exists(c):
            return c
    return None


def to_svg(dot_text: str, out: Path) -> bool:
    exe = find_dot()
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "-Tsvg", "-o", str(out)], input=dot_text.encode("utf-8"), capture_output=True, timeout=120)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _q(s: str) -> str:
    return '"' + safe(s).replace("\n", "\\n") + '"'


def block(view: View) -> str:
    ids: dict[str, str] = {}
    out = ["digraph uvm {", "  compound=true; rankdir=LR; newrank=true; fontname=Helvetica; nodesep=0.35; ranksep=0.7;",
           '  node [shape=box style="rounded,filled" fontname=Helvetica fontsize=10];',
           "  edge [fontname=Helvetica fontsize=9];"]

    def nid(i):
        return ids.setdefault(i, f"n{len(ids)}")

    anchors: dict[str, str] = {}

    def emit(i: str, ind: str):
        inst = view.by_id[i]
        n = nid(i)
        st = view.style_of(inst)
        dashed = ",dashed" if st["kind"] in ("conditional", "inactive") else ""
        kids = view.ordered_children(i)
        if kids:
            out.append(f"{ind}subgraph cluster_{n} {{")
            out.append(f'{ind}  label={_q(view.label(inst))}; style="rounded,filled{dashed}"; fillcolor="{st["fill"]}"; '
                       f'color="{st["stroke"]}"; fontcolor="{st["font"]}"; fontsize=11;')
            out.append(f"{ind}  a_{n} [shape=point style=invis width=0 label=\"\"];")
            anchors[i] = f"a_{n}"
            for k in kids:
                emit(k, ind + "  ")
            out.append(f"{ind}}}")
        else:
            out.append(f'{ind}{n} [label={_q(view.label(inst))} fillcolor="{st["fill"]}" color="{st["stroke"]}" '
                       f'fontcolor="{st["font"]}" style="rounded,filled{dashed}"];')
            anchors[i] = n

    for r in view.roots():
        emit(r, "  ")
    for e in view.edges():
        a, b = anchors[e.src], anchors[e.dst]
        attrs = [f"label={_q(e.label)}", f'color="{view.edge_color(e)}"', f'fontcolor="{view.edge_color(e)}"']
        if e.kind == "handle" or e.conditional or (view.test and not e.active):
            attrs.append("style=dashed")
        if view.by_id[e.src]["id"] in view.kids and view.children(e.src):
            attrs.append(f"ltail=cluster_{ids[e.src]}")
        if view.children(e.dst):
            attrs.append(f"lhead=cluster_{ids[e.dst]}")
        out.append(f"  {a} -> {b} [{', '.join(attrs)}];")
    out.append("}")
    return "\n".join(out) + "\n"


def classes(arch: dict) -> str:
    out = ["digraph classes {", "  rankdir=BT; fontname=Helvetica;",
           '  node [shape=record fontname=Helvetica fontsize=10 style=filled];']
    from .common import color_of
    names = {c["name"] for c in arch["classes"]}
    ext = set()
    for c in arch["classes"]:
        ports = "\\l".join(f"{p['kind']} {p['name']} : {p['protocol']}({p['txn'] or ''})" for p in c["ports"])
        body = f"{{«{c['role']}»\\n{c['name']}|{safe(ports)}\\l}}"
        out.append(f'  {c["name"]} [label="{body}" fillcolor="{color_of(c["role"])}"];')
    for c in arch["classes"]:
        if c["base"]:
            b = c["base"].split("#")[0].strip()
            if b not in names and b not in ext:
                ext.add(b)
                out.append(f'  {b} [label="{b}" fillcolor="#ffffff"];')
            out.append(f"  {c['name']} -> {b} [arrowhead=empty];")
        for ch in c["children"]:
            t = ch["type"].split("#")[0].strip()
            if t in names:
                out.append(f'  {t} -> {c["name"]} [arrowhead=diamond label="{safe(ch["member"])}" fontsize=8 color="#2471a3"];')
    out.append("}")
    return "\n".join(out) + "\n"


def config_db(arch: dict) -> str:
    out = ["digraph cfg {", "  rankdir=LR; node [fontname=Helvetica fontsize=10 shape=box style=\"rounded,filled\" fillcolor=\"#f4ecf7\"];"]
    for k, s in enumerate(arch["environment"]["config_db"]["sets"]):
        who = s["setter"].split(":", 1)[1] if s["setter"] else "(tb_top)"
        col = "#c0392b" if s["status"] == "orphan_set" else "#555555"
        out.append(f'  f{k} [label={_q(s["field"] + chr(10) + s["type"])} shape=note fillcolor="#fcf3cf"];')
        out.append(f'  "{who}" -> f{k} [label="set" color="{col}"];')
        for c in s["consumers"]:
            out.append(f'  f{k} -> "{c.split(":", 1)[1]}" [label="get" color="{col}"];')
        if not s["consumers"]:
            out.append(f'  f{k} -> "(aucun get)" [style=dashed color="#c0392b"];')
    out.append("}")
    return "\n".join(out) + "\n"
