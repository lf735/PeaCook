"""Chargement des sources SystemVerilog (filelist .f ou scan de répertoire) via pyslang."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from pyslang.driver import Driver

SV_EXT = {".sv", ".svh", ".v", ".vh", ".vhd_skip"}
STUB = Path(__file__).parent / "stubs" / "uvm_macros.svh"


@dataclass
class SourceSet:
    files: list[str] = field(default_factory=list)
    incdirs: list[str] = field(default_factory=list)
    defines: dict[str, str] = field(default_factory=dict)
    diagnostics: list[dict] = field(default_factory=list)
    trees: list = field(default_factory=list)
    sm: object = None  # SourceManager
    root: str = "."


def parse_filelist(path: str, _seen=None) -> tuple[list[str], list[str], dict[str, str]]:
    """Lit un .f (récursif -f, +incdir+, +define+, -I, -D, commentaires, $VAR)."""
    _seen = _seen or set()
    p = Path(path).resolve()
    if p in _seen:
        return [], [], {}
    _seen.add(p)
    base = p.parent
    files, inc, defs = [], [], {}
    text = p.read_text(errors="replace")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for raw in text.splitlines():
        line = re.sub(r"//.*$", "", raw).strip()
        line = os.path.expandvars(line)
        if not line or line.startswith("#"):
            continue
        for tok in line.split():
            if tok.startswith("+incdir+"):
                for d in tok[8:].split("+"):
                    if d:
                        inc.append(str((base / d).resolve()) if not os.path.isabs(d) else d)
            elif tok.startswith("+define+"):
                for d in tok[8:].split("+"):
                    if d:
                        k, _, v = d.partition("=")
                        defs[k] = v
            elif tok.startswith("-I") and len(tok) > 2:
                inc.append(str((base / tok[2:]).resolve()))
            elif tok.startswith("-D") and len(tok) > 2:
                k, _, v = tok[2:].partition("=")
                defs[k] = v
            elif tok in ("-f", "-F", "-sv", "-v", "-y") or tok.startswith("+") or tok.startswith("-"):
                continue
            else:
                # argument éventuel de -f
                if line.split()[0] in ("-f", "-F") and tok != line.split()[0]:
                    f2, i2, d2 = parse_filelist(str((base / tok).resolve()), _seen)
                    files += f2
                    inc += i2
                    defs.update(d2)
                else:
                    files.append(str((base / tok).resolve()) if not os.path.isabs(tok) else tok)
    return files, inc, defs


def scan_dir(root: str, exclude: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Scan de répertoire : ordre = packages/interfaces d'abord, fichiers inclus exclus de la liste."""
    exclude = exclude or []
    allf = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(".")]
        for f in fn:
            if Path(f).suffix.lower() in SV_EXT:
                full = str(Path(dp, f).resolve())
                if not any(Path(full).match(g) for g in exclude):
                    allf.append(full)
    inc_re = re.compile(r'`include\s+"([^"]+)"')
    included: set[str] = set()
    byname = {Path(f).name: f for f in allf}
    for f in allf:
        try:
            for m in inc_re.finditer(Path(f).read_text(errors="replace")):
                n = Path(m.group(1)).name
                if n in byname:
                    included.add(byname[n])
        except OSError:
            pass
    incdirs = sorted({str(Path(f).parent) for f in allf})

    def rank(f: str) -> int:
        try:
            t = Path(f).read_text(errors="replace")
        except OSError:
            return 5
        if re.search(r"^\s*(package|interface)\s", t, re.M):
            return 0
        if re.search(r"^\s*module\s", t, re.M):
            return 2
        return 1

    srcs = [f for f in allf if f not in included]
    srcs.sort(key=lambda f: (rank(f), f))
    return srcs, incdirs


def load(filelist: str | None = None, directory: str | None = None, incdirs=None, defines=None,
         exclude=None, uvm_home: str | None = None) -> SourceSet:
    ss = SourceSet()
    incdirs = list(incdirs or [])
    defines = dict(defines or {})
    if filelist:
        f, i, d = parse_filelist(filelist)
        ss.files, ss.incdirs, ss.defines = f, i + incdirs, {**d, **defines}
        ss.root = str(Path(filelist).resolve().parent)
    elif directory:
        f, i = scan_dir(directory, exclude)
        ss.files, ss.incdirs, ss.defines = f, i + incdirs, defines
        ss.root = str(Path(directory).resolve())
    else:
        raise ValueError("filelist ou directory requis")

    args = ["slang", "--single-unit", "--ignore-unknown-modules", 
            "--allow-use-before-declare", "--lint-only"]
    for d in ss.incdirs:
        args += ["-I", d]
    for k, v in ss.defines.items():
        args += ["-D", f"{k}={v}" if v else k]
    if uvm_home:
        args += ["-I", str(Path(uvm_home) / "src")]
        args += [str(Path(uvm_home) / "src" / "uvm_pkg.sv")]
    else:
        args += ["-I", str(STUB.parent), str(STUB)]
    args += ss.files
    drv = Driver()
    drv.addStandardArgs()
    drv.parseCommandLine(" ".join(_q(a) for a in args))
    drv.processOptions()
    drv.parseAllSources()
    ss.sm = drv.sourceManager
    ss.trees = list(drv.syntaxTrees)
    for t in ss.trees:
        for d in t.diagnostics:
            ss.diagnostics.append({"severity": "info", "code": "PARSE_" + str(d.code).split("(")[-1].rstrip(")"),
                                   "message": str(d.code), "loc": _loc(ss.sm, d.location)})
    return ss


def _q(a: str) -> str:
    return f'"{a}"' if (" " in a or "\\" in a) else a


def _loc(sm, loc) -> str:
    try:
        return f"{Path(sm.getFileName(loc)).as_posix()}:{sm.getLineNumber(loc)}"
    except Exception:  # noqa: BLE001
        return "?"
