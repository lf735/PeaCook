"""Petits utilitaires de manipulation de texte SystemVerilog (arguments, parenthèses, types)."""
from __future__ import annotations

import re


_COMMENT_RE = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/', re.S)


def strip_comments(s: str) -> str:
    """Retire les commentaires (en préservant les chaînes littérales)."""
    return _COMMENT_RE.sub(lambda m: m.group(0) if m.group(0).startswith('"') else " ", s)


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", strip_comments(s)).strip()


def ident(s: str) -> str:
    m = re.search(r"[A-Za-z_]\w*", s)
    return m.group(0) if m else s.strip()


def strip_quotes(s: str) -> str:
    s = s.strip()
    return s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s


def balanced(text: str, i: int, open_c="(", close_c=")") -> int:
    """Index du caractère fermant correspondant à text[i] == open_c (ou -1)."""
    depth, in_str = 0, False
    j = i
    while j < len(text):
        ch = text[j]
        if ch == '"' and (j == 0 or text[j - 1] != "\\"):
            in_str = not in_str
        elif not in_str:
            if ch == open_c:
                depth += 1
            elif ch == close_c:
                depth -= 1
                if depth == 0:
                    return j
        j += 1
    return -1


def split_args(s: str) -> list[str]:
    out, depth, cur, in_str = [], 0, [], False
    for ch in s:
        if ch == '"':
            in_str = not in_str
        if not in_str:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 0:
                out.append("".join(cur).strip())
                cur = []
                continue
        cur.append(ch)
    last = "".join(cur).strip()
    if last or out:
        out.append(last)
    return out


def split_type(txt: str) -> tuple[str, str]:
    """'uvm_agent #(int)' -> ('uvm_agent', 'int')."""
    txt = squash(txt)
    m = re.match(r"^([\w:]+)\s*(?:#\s*\((.*)\))?$", txt, re.S)
    if not m:
        return txt, ""
    return m.group(1), (m.group(2) or "").strip()


def parse_params(txt: str) -> list[dict]:
    m = re.search(r"#\s*\((.*)\)", txt, re.S)
    if not m:
        return []
    out = []
    for item in split_args(m.group(1)):
        item = squash(item)
        kind = "type" if re.match(r"(?:parameter\s+)?type\b", item) else "value"
        item = re.sub(r"^(?:parameter|localparam)\s+", "", item)
        item = re.sub(r"^type\s+", "", item)
        nm = re.match(r"(?:[\w:\[\]\s]*\s)?(\w+)\s*(?:=\s*(.*))?$", item)
        if nm:
            out.append({"name": nm.group(1), "default": nm.group(2), "kind": kind})
    return out


def method_name(proto: str) -> str:
    m = re.search(r"(\w+)\s*\(", squash(proto))
    if m:
        return m.group(1)
    m = re.search(r"(\w+)\s*;?\s*$", squash(proto))
    return m.group(1) if m else "?"


_CFG_RE = re.compile(r"uvm_(config|resource)_db\s*#\s*\(")


def find_config_ops(s: str) -> list[dict]:
    out = []
    for m in _CFG_RE.finditer(s):
        i = m.end() - 1
        j = balanced(s, i)
        if j < 0:
            continue
        typ = squash(s[i + 1:j])
        rest = s[j + 1:]
        mm = re.match(r"\s*::\s*(\w+)\s*\(", rest)
        if not mm:
            continue
        k = mm.group(1)
        a0 = j + 1 + mm.end() - 1
        a1 = balanced(s, a0)
        args = split_args(s[a0 + 1:a1 if a1 > 0 else len(s)])
        kind = "set" if k.startswith("set") else "get" if k.startswith("get") else None
        if kind is None:
            continue
        if m.group(1) == "config":
            if len(args) < 3:
                continue
            out.append({"op": "cfg", "kind": kind, "type": typ, "ctx": args[0], "path": args[1], "field": args[2],
                        "value": args[3] if len(args) > 3 else None, "db": "config"})
        else:  # resource_db : (scope, name, value/var [, accessor])
            if len(args) < 2:
                continue
            out.append({"op": "cfg", "kind": kind, "type": typ, "ctx": "null", "path": args[0], "field": args[1],
                        "value": args[2] if len(args) > 2 else None, "db": "resource"})
    return out


_OV_NAMES = ("set_type_override_by_type", "set_inst_override_by_type", "set_type_override_by_name",
             "set_inst_override_by_name", "set_type_override", "set_inst_override")


def _gt(a: str) -> str | None:
    m = re.match(r"^\s*([\w:#\(\)\s,\.]+?)::get_type\s*\(\s*\)\s*$", a)
    return squash(m.group(1)) if m else None


def find_overrides(s: str) -> list[dict]:
    m = re.search(r"(?:(?P<cls>[\w:#\(\)\s,\.]+?)::type_id::|(?P<recv>[\w\.]*(?:get\(\))?\.)?)"
                  r"(?P<fn>" + "|".join(_OV_NAMES) + r")\s*\(", s)
    if not m:
        return []
    i = m.end() - 1
    j = balanced(s, i)
    args = split_args(s[i + 1:j if j > 0 else len(s)])
    fn = m.group("fn")
    inst = "inst" in fn
    by_name = fn.endswith("by_name")
    recv = (m.group("recv") or "").rstrip(".")
    cls = squash(m.group("cls")) if m.group("cls") else None
    o = {"op": "override", "scope": "inst" if inst else "type", "orig": None, "over": None, "path": None, "ctx": "this"}
    if cls:  # A::type_id::set_*_override(B::get_type() [, path])
        o["orig"] = cls
        o["over"] = _gt(args[0]) if args else None
        if inst and len(args) > 1:
            o["path"] = strip_quotes(args[1])
            o["ctx"] = "factory" if len(args) < 3 else args[2]
        else:
            o["ctx"] = "factory"
    else:
        factory = recv.endswith("get()") or recv in ("factory", "uvm_factory") or "factory" in recv
        o["ctx"] = "factory" if factory else (recv or "this")
        if by_name:
            if inst and not factory:   # comp.set_inst_override(path, orig, over)
                o["path"], o["orig"], o["over"] = (strip_quotes(a) for a in (args + ["", "", ""])[:3])
            else:                       # factory.set_*_by_name(orig, over [, path])
                o["orig"], o["over"] = strip_quotes(args[0]), strip_quotes(args[1]) if len(args) > 1 else None
                if inst and len(args) > 2:
                    o["path"] = strip_quotes(args[2])
        else:
            gts = [(_gt(a), a) for a in args]
            types = [g for g, _ in gts if g]
            strs = [strip_quotes(a) for g, a in gts if not g and a.strip().startswith('"')]
            if len(types) >= 2:
                o["orig"], o["over"] = types[0], types[1]
            if inst and strs:
                o["path"] = strs[0]
            elif inst and len(args) >= 3:
                o["path"] = strip_quotes(args[2] if _gt(args[0]) else args[0])
    return [o] if o["orig"] and o["over"] else []


def iter_ops(ops):
    for o in ops:
        yield o
        for key in ("then", "else", "body"):
            if key in o:
                yield from iter_ops(o[key])
