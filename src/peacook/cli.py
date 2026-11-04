"""Interface en ligne de commande de PeaCook."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__


def _common(p: argparse.ArgumentParser):
    g = p.add_argument_group("sources")
    g.add_argument("-f", "--filelist", help="filelist .f (+incdir+, +define+, -f imbriqués)")
    g.add_argument("-d", "--dir", dest="directory", help="répertoire à scanner (alternative à -f)")
    g.add_argument("-I", dest="incdirs", action="append", default=[], help="répertoire d'include supplémentaire")
    g.add_argument("-D", dest="defines", action="append", default=[], help="define NAME[=VAL]")
    g.add_argument("--exclude", action="append", default=[], help="glob de fichiers à exclure (mode --dir)")
    g.add_argument("--uvm-home", help="chemin d'une distribution UVM (utiliser les vraies macros au lieu des stubs)")
    p.add_argument("--test", action="append", help="limiter à ce(s) test(s) (répétable)")
    p.add_argument("--max-array-expand", type=int, default=64, help="borne de dépliage des tableaux d'instances")
    p.add_argument("--no-impl", action="store_true", help="ne pas extraire la couche implémentation")


def _render_args(p: argparse.ArgumentParser):
    from .render.output import ALL_FORMATS, ALL_VIEWS
    p.add_argument("--views", default=",".join(ALL_VIEWS), help=f"parmi: {','.join(ALL_VIEWS)}")
    p.add_argument("--formats", default=",".join(ALL_FORMATS), help=f"parmi: {','.join(ALL_FORMATS)}")
    p.add_argument("--hide-inactive", action="store_true", help="ne pas afficher les éléments grisés (désactivés)")
    p.add_argument("--raw", action="store_true", help="connexions hiérarchiques au lieu de bout en bout")


def _defs(items):
    out = {}
    for d in items:
        k, _, v = d.partition("=")
        out[k] = v
    return out


def _analyze(a):
    from .pipeline import analyze
    if not (a.filelist or a.directory):
        raise SystemExit("préciser -f <filelist> ou -d <répertoire>")
    return analyze(filelist=a.filelist, directory=a.directory, incdirs=a.incdirs, defines=_defs(a.defines),
                   exclude=a.exclude, uvm_home=a.uvm_home, tests=a.test, max_expand=a.max_array_expand,
                   with_impl=not a.no_impl)


def _csv(s):
    return [x.strip() for x in s.split(",") if x.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="peacook", description="Extraction d'architecture d'environnements UVM")
    ap.add_argument("--version", action="version", version=f"peacook {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="analyse les sources et écrit le modèle JSON")
    _common(s)
    s.add_argument("-o", "--out", default="out", help="dossier de sortie")

    r = sub.add_parser("render", help="génère les vues à partir d'un architecture.json")
    r.add_argument("model", help="architecture.json (le implementation.json voisin est lu s'il existe)")
    r.add_argument("-o", "--out", default="out")
    _render_args(r)

    a = sub.add_parser("all", help="scan + rendu")
    _common(a)
    a.add_argument("-o", "--out", default="out")
    _render_args(a)

    c = sub.add_parser("check", help="lint d'architecture (code de sortie pour la CI)")
    c.add_argument("model", nargs="?", help="architecture.json ; sinon utiliser -f/-d")
    _common(c)
    c.add_argument("--fail-on", choices=["error", "warning", "info"], default="error")

    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

    from .render.output import write_all

    if args.cmd in ("scan", "all"):
        res = _analyze(args)
        if args.cmd == "scan":
            out = Path(args.out)
            (out / "architecture").mkdir(parents=True, exist_ok=True)
            (out / "architecture" / "architecture.json").write_text(json.dumps(res.arch, indent=2, ensure_ascii=False), encoding="utf-8")
            if res.impl:
                (out / "implementation").mkdir(parents=True, exist_ok=True)
                (out / "implementation" / "implementation.json").write_text(json.dumps(res.impl, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"modèle écrit dans {out}")
        else:
            files = write_all(res, args.out, _csv(args.views), _csv(args.formats), args.hide_inactive, args.raw,
                              args.test[0] if args.test and len(args.test) == 1 else None)
            print(f"{len(files)} fichier(s) écrits dans {args.out}")
        _summary(res.arch)
        return 0

    if args.cmd == "render":
        from .pipeline import Result
        mp = Path(args.model)
        arch = json.loads(mp.read_text(encoding="utf-8"))
        ip = mp.parent.parent / "implementation" / "implementation.json"
        impl = json.loads(ip.read_text(encoding="utf-8")) if ip.exists() else None
        files = write_all(Result(arch, impl, None, None, None), args.out, _csv(args.views),  # type: ignore[arg-type]
                          _csv(args.formats), args.hide_inactive, args.raw)
        print(f"{len(files)} fichier(s) écrits dans {args.out}")
        return 0

    if args.cmd == "check":
        if args.model:
            arch = json.loads(Path(args.model).read_text(encoding="utf-8"))
        else:
            arch = _analyze(args).arch
        order = {"error": 0, "warning": 1, "info": 2}
        bad = 0
        for d in arch["diagnostics"]:
            print(f"{d['severity']:7} {d['code']:28} {d['message']}" + (f"  [{d['loc']}]" if d.get("loc") else ""))
            if order[d["severity"]] <= order[args.fail_on]:
                bad += 1
        return 1 if bad else 0
    return 0


def _summary(arch: dict):
    env = arch["environment"]
    print(f"tests: {len(env['tests'])} · classes: {len(arch['classes'])} · instances: {len(env['instances'])} "
          f"({sum(1 for i in env['instances'] if i['conditional'])} conditionnelles) · "
          f"connexions: {len(env['flat_connections'])}")
    for sev in ("error", "warning"):
        n = sum(1 for d in arch["diagnostics"] if d["severity"] == sev)
        if n:
            print(f"  {n} {sev}(s)")


if __name__ == "__main__":
    raise SystemExit(main())
