"""Orchestration : sources -> faits -> topologies par test -> modèles architecture + implémentation."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from . import __version__
from .analyze.checks import run_checks
from .elaborate.topology import elaborate_test
from .extract.facts import Facts, extract
from .frontend.sources import SourceSet, load
from .model import build
from .resolve.types import TypeModel


@dataclass
class Result:
    arch: dict
    impl: dict | None
    facts: Facts
    tm: TypeModel
    sources: SourceSet


def find_tests(f: Facts, tm: TypeModel) -> list[str]:
    tests = [n for n, c in f.classes.items() if tm.role(n) == "test" and not c.is_virtual]
    # tests "feuilles" d'abord n'est pas requis : on garde tous les tests concrets, ordre des sources
    return tests


def analyze(filelist=None, directory=None, incdirs=None, defines=None, exclude=None, uvm_home=None,
            tests: list[str] | None = None, max_expand: int = 64, with_impl: bool = True) -> Result:
    ss = load(filelist=filelist, directory=directory, incdirs=incdirs, defines=defines, exclude=exclude,
              uvm_home=uvm_home)
    f = extract(ss.trees, ss.sm)
    tm = TypeModel(f)
    all_tests = find_tests(f, tm)
    sel = tests or all_tests
    unknown = [t for t in sel if t not in f.classes]
    if unknown:
        raise SystemExit(f"test(s) inconnu(s): {', '.join(unknown)} (disponibles: {', '.join(all_tests)})")
    instantiated = {i["type"] for m in f.modules.values() for i in m.instances}
    tops = [m for m in f.modules.values() if m.kind == "module" and (m.run_test is not None or m.name not in instantiated)]
    topos: "OrderedDict[str, object]" = OrderedDict()
    diags = []
    for t in sel:
        topos[t] = elaborate_test(tm, f, t, tops, max_expand)
    seen = set()
    for t, top in topos.items():
        for d in top.diagnostics:
            k = (d["code"], d["message"], d["loc"])
            if k not in seen:
                seen.add(k)
                diags.append(d)
    env = build.merge_env(topos, tm, f)  # type: ignore[arg-type]
    arch = {
        "schema_version": build.SCHEMA_VERSION,
        "tool": {"name": "peacook", "version": __version__},
        "sources": {"files": [str(p) for p in ss.files], "incdirs": ss.incdirs, "defines": ss.defines},
        "packages": [{"id": f"pkg:{p['name']}", **p} for p in f.packages.values()],
        "classes": build.class_entries(tm, f),
        "tests": [{"id": f"test:{t}", "name": t, "base_chain": tm.chain(t)[1:], "loc": f.classes[t].loc,
                   "class": f"class:{t}"} for t in sel],
        "environment": env,
    }
    arch["harness"] = build.harness(f, tm, env)
    arch["diagnostics"] = run_checks(arch, f, tm, ss.diagnostics) + diags
    impl = build.implementation(f, tm) if with_impl else None
    return Result(arch, impl, f, tm, ss)
