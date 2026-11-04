"""Écriture des sorties : deux couches séparées mais liées (architecture/ et implementation/)."""
from __future__ import annotations

import json
from pathlib import Path

from ..pipeline import Result
from . import drawio, graphviz, html, jsonviews, markdown, mermaid
from .common import View

ALL_VIEWS = ["block", "tree", "classes", "config", "seq", "harness", "tests", "lint", "dataflow"]
ALL_FORMATS = ["mermaid", "dot", "svg", "html", "drawio", "md", "json"]


def _w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_all(res: Result, out: str, views=None, formats=None, hide_inactive=False, raw=False,
              only_test: str | None = None) -> list[Path]:
    views = views or ALL_VIEWS
    formats = formats or ALL_FORMATS
    out_p = Path(out)
    arch, impl = res.arch, res.impl
    written: list[Path] = []
    A = out_p / "architecture"
    V = A / "views"
    written.append(_w(A / "architecture.json", json.dumps(arch, indent=2, ensure_ascii=False)))
    tests = [None] + ([only_test] if only_test else arch["environment"]["tests"])
    if not arch["environment"]["instances"]:      # aucun test élaboré : pas de vue d'instances
        views = [v for v in views if v not in ("block", "tree", "seq", "harness", "dataflow")]
        formats = [x for x in formats if x not in ("drawio", "html")]

    if "block" in views:
        for t in tests:
            v = View(arch, t, hide_inactive, raw)
            suffix = "" if (t is None or not hide_inactive) else ".hidden"
            if "mermaid" in formats:
                written.append(_w(V / f"block.{v.tag}{suffix}.mmd", mermaid.block(v)))
            if "dot" in formats or "svg" in formats:
                dot = graphviz.block(v)
                if "dot" in formats:
                    written.append(_w(V / f"block.{v.tag}{suffix}.dot", dot))
                if "svg" in formats and graphviz.to_svg(dot, V / f"block.{v.tag}{suffix}.svg"):
                    written.append(V / f"block.{v.tag}{suffix}.svg")
        if "drawio" in formats:
            written.append(_w(V / "block.drawio", drawio.document(arch, hide_inactive, raw)))
    if "tree" in views:
        if "mermaid" in formats:
            written.append(_w(V / "hierarchy.mmd", mermaid.hierarchy(View(arch, None))))
        if "md" in formats:
            written.append(_w(V / "hierarchy.txt", markdown.tree_text(arch) + "\n"))
    if "classes" in views:
        if "mermaid" in formats:
            written.append(_w(V / "classes.mmd", mermaid.classes(arch)))
        if "dot" in formats or "svg" in formats:
            dot = graphviz.classes(arch)
            if "dot" in formats:
                written.append(_w(V / "classes.dot", dot))
            if "svg" in formats and graphviz.to_svg(dot, V / "classes.svg"):
                written.append(V / "classes.svg")
    if "config" in views and ("dot" in formats or "svg" in formats):
        dot = graphviz.config_db(arch)
        if "dot" in formats:
            written.append(_w(V / "config_db.dot", dot))
        if "svg" in formats and graphviz.to_svg(dot, V / "config_db.svg"):
            written.append(V / "config_db.svg")
    if "seq" in views and "mermaid" in formats:
        written.append(_w(V / "sequences.mmd", mermaid.sequences(arch)))
    if "harness" in views and "mermaid" in formats:
        written.append(_w(V / "harness.mmd", mermaid.harness(arch)))
    if "json" in formats:
        mapping = {"tree": ["hierarchy", "connections"], "classes": ["classes"], "config": ["config_db"],
                   "seq": ["sequences"], "harness": ["harness"], "tests": ["tests"], "lint": ["lint"],
                   "dataflow": ["dataflow"], "block": ["connections"]}
        done = set()
        for v in views:
            for name in mapping.get(v, []):
                if name not in done:
                    done.add(name)
                    written.append(_w(V / f"{name}.json", json.dumps(jsonviews.ALL[name](arch), indent=2, ensure_ascii=False)))
    if "md" in formats:
        written.append(_w(A / "report.md", markdown.architecture_report(arch, "../implementation/classes" if impl else None)))
    if "html" in formats:
        written.append(_w(out_p / "index.html", html.build(arch, impl)))
    if impl:
        I = out_p / "implementation"
        written.append(_w(I / "implementation.json", json.dumps(impl, indent=2, ensure_ascii=False)))
        by = {c["name"]: c for c in arch["classes"]}
        if "md" in formats:
            written.append(_w(I / "report.md", markdown.impl_report(impl, arch)))
            for c in impl["classes"]:
                written.append(_w(I / "classes" / f"{c['name']}.md", markdown.impl_class_md(c, by.get(c["name"]))))
    return written
