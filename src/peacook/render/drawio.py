"""Rendu draw.io (mxGraph) : blocs imbriqués éditables, une page par vue (référence + un par test)."""
from __future__ import annotations

import math
from xml.sax.saxutils import escape

from .common import View

LEAF_W, LEAF_H, PAD, HEAD, GAP = 170, 46, 14, 30, 16


def _layout(view: View, i: str, pos: dict):
    kids = view.ordered_children(i)
    if not kids:
        pos[i] = {"w": LEAF_W, "h": LEAF_H, "x": 0, "y": 0}
        return
    for k in kids:
        _layout(view, k, pos)
    area = sum((pos[k]["w"] + GAP) * (pos[k]["h"] + GAP) for k in kids)
    max_row = max(max(pos[k]["w"] for k in kids), math.sqrt(area) * 1.5)
    x = y = row_h = 0
    width = 0
    for k in kids:
        w, h = pos[k]["w"], pos[k]["h"]
        if x and x + w > max_row:
            x, y, row_h = 0, y + row_h + GAP, 0
        pos[k]["x"], pos[k]["y"] = x + PAD, y + HEAD + PAD
        x += w + GAP
        row_h = max(row_h, h)
        width = max(width, x - GAP)
    pos[i] = {"w": width + 2 * PAD, "h": y + row_h + HEAD + 2 * PAD, "x": 0, "y": 0}


def page(view: View, base_pos: dict | None = None) -> str:
    pos = base_pos or {}
    if not base_pos:
        _layout(view, view.env["root"], pos)
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    cid: dict[str, str] = {}

    def c(i):
        return cid.setdefault(i, f"c{len(cid) + 2}")

    def emit(i: str, parent: str):
        inst = view.by_id[i]
        st = view.style_of(inst)
        p = pos[i]
        kids = view.ordered_children(i)
        dash = "dashed=1;" if st["kind"] in ("conditional", "inactive") else ""
        style = (f"rounded=1;whiteSpace=wrap;html=1;fillColor={st['fill']};strokeColor={st['stroke']};"
                 f"fontColor={st['font']};{dash}" + ("verticalAlign=top;fontStyle=1;" if kids else ""))
        cells.append(f'<mxCell id="{c(i)}" value="{escape(view.label(inst), {chr(34): "&quot;"})}" style="{style}" vertex="1" parent="{parent}">'
                     f'<mxGeometry x="{p["x"]}" y="{p["y"]}" width="{p["w"]}" height="{p["h"]}" as="geometry"/></mxCell>')
        for k in kids:
            emit(k, c(i))

    emit(view.env["root"], "1")
    for k, e in enumerate(view.edges()):
        dash = "dashed=1;" if (e.kind == "handle" or e.conditional or (view.test and not e.active)) else ""
        col = view.edge_color(e)
        cells.append(f'<mxCell id="e{k}" value="{escape(e.label)}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;'
                     f'strokeColor={col};fontColor={col};{dash}endArrow=block;" edge="1" parent="1" source="{c(e.src)}" target="{c(e.dst)}">'
                     f'<mxGeometry relative="1" as="geometry"/></mxCell>')
    return "<mxGraphModel><root>" + "".join(cells) + "</root></mxGraphModel>"


def document(arch: dict, hide_inactive: bool = False, raw: bool = False) -> str:
    tests = [None] + arch["environment"]["tests"]
    pos: dict = {}
    ref = View(arch, None, False, raw)
    _layout(ref, ref.env["root"], pos)
    pages = []
    for k, t in enumerate(tests):
        v = View(arch, t, hide_inactive, raw)
        p = pos
        if hide_inactive and t:
            p = {}
            _layout(v, v.env["root"], p)
        name = "Référence (tous tests)" if t is None else t
        pages.append(f'<diagram id="p{k}" name="{escape(name, {chr(34): "&quot;"})}">{page(v, p)}</diagram>')
    return '<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="peacook">' + "".join(pages) + "</mxfile>\n"
