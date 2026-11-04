"""Évaluateur d'expressions SystemVerilog restreint (3 valeurs : vrai / faux / UNKNOWN)."""
from __future__ import annotations

import fnmatch
import re


class _Unknown:
    _inst = None

    def __new__(cls):
        if cls._inst is None:
            cls._inst = super().__new__(cls)
        return cls._inst

    def __repr__(self):
        return "UNKNOWN"

    def __bool__(self):
        raise TypeError("UNKNOWN n'a pas de valeur booléenne")


UNKNOWN = _Unknown()
_obj_counter = [0]


class Sym(str):
    """Constante symbolique (enum) non numérique."""


class Obj:
    def __init__(self, type_name: str, fields: dict | None = None, loc: str = ""):
        _obj_counter[0] += 1
        self.id = _obj_counter[0]
        self.type = type_name
        self.fields = fields or {}
        self.loc = loc

    def __repr__(self):
        return f"Obj({self.type}#{self.id})"


class ArrayVal:
    def __init__(self, size=UNKNOWN):
        self.size = size
        self.items: dict = {}


class InstRef:
    def __init__(self, path: str):
        self.path = path

    def __repr__(self):
        return f"InstRef({self.path})"


TOKEN_RE = re.compile(r"""\s*(?:
  (?P<str>"(?:[^"\\]|\\.)*")|
  (?P<num>\d*'[sS]?[bBdDhHoO][0-9a-fA-F_xXzZ?]+|'[01xXzZ]|\d[\d_]*)|
  (?P<id>\$?[A-Za-z_]\w*)|
  (?P<op>==|!=|<=|>=|&&|\|\||<<|>>|[-+*/%<>!~&|^?:()\[\].,{}])
)""", re.X)


def tokenize(s: str):
    pos, out = 0, []
    s = s.strip()
    while pos < len(s):
        m = TOKEN_RE.match(s, pos)
        if not m or m.end() == pos:
            raise ValueError(f"token inattendu: {s[pos:pos+10]!r}")
        pos = m.end()
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
    return out


def parse_int(tok: str):
    t = tok.replace("_", "")
    if "'" in t:
        w, _, rest = t.partition("'")
        if not rest:
            return UNKNOWN
        if rest[0] in "01":
            return int(rest[0])
        if rest[0] in "xXzZ":
            return UNKNOWN
        base = rest[0].lower()
        if rest[0] in "sS":
            base, rest = rest[1].lower(), rest[1:]
        digits = rest[1:]
        if re.search(r"[xXzZ?]", digits):
            return UNKNOWN
        return int(digits, {"b": 2, "d": 10, "h": 16, "o": 8}[base])
    return int(t)


class Evaluator:
    """ctx doit fournir : lookup(name) -> valeur|MISSING ; call(recv, name, args) -> valeur ; enums (dict)."""

    MISSING = object()

    def __init__(self, ctx):
        self.ctx = ctx

    def eval(self, expr: str):
        if expr is None:
            return UNKNOWN
        try:
            self.toks = tokenize(expr)
        except ValueError:
            return UNKNOWN
        self.i = 0
        try:
            v = self.ternary()
        except (ValueError, TypeError, IndexError, ZeroDivisionError):
            return UNKNOWN
        return v if self.i >= len(self.toks) else UNKNOWN

    # -- helpers
    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def accept(self, *ops):
        k, v = self.peek()
        if k == "op" and v in ops:
            self.i += 1
            return v
        return None

    def ternary(self):
        c = self.logic_or()
        if self.accept("?"):
            a = self.ternary()
            if not self.accept(":"):
                raise ValueError("':' attendu")
            b = self.ternary()
            if c is UNKNOWN:
                return a if a == b else UNKNOWN
            return a if truth(c) else b
        return c

    def logic_or(self):
        v = self.logic_and()
        while self.accept("||"):
            r = self.logic_and()
            tv, tr = truth(v), truth(r)
            v = True if (tv is True or tr is True) else (UNKNOWN if (tv is UNKNOWN or tr is UNKNOWN) else False)
        return v

    def logic_and(self):
        v = self.bit_or()
        while self.accept("&&"):
            r = self.bit_or()
            tv, tr = truth(v), truth(r)
            v = False if (tv is False or tr is False) else (UNKNOWN if (tv is UNKNOWN or tr is UNKNOWN) else True)
        return v

    def _bin(self, sub, ops, fn):
        v = sub()
        while True:
            op = self.accept(*ops)
            if not op:
                return v
            r = sub()
            v = UNKNOWN if (v is UNKNOWN or r is UNKNOWN) else fn(op, v, r)

    def bit_or(self):
        return self._bin(self.bit_xor, ["|"], lambda o, a, b: int(a) | int(b))

    def bit_xor(self):
        return self._bin(self.bit_and, ["^"], lambda o, a, b: int(a) ^ int(b))

    def bit_and(self):
        return self._bin(self.equality, ["&"], lambda o, a, b: int(a) & int(b))

    def equality(self):
        return self._bin(self.relational, ["==", "!="], lambda o, a, b: (_eq(a, b) if o == "==" else not _eq(a, b)))

    def relational(self):
        return self._bin(self.shift, ["<=", ">=", "<", ">"], lambda o, a, b: {
            "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[o])

    def shift(self):
        return self._bin(self.additive, ["<<", ">>"], lambda o, a, b: (a << b) if o == "<<" else (a >> b))

    def additive(self):
        return self._bin(self.mult, ["+", "-"], lambda o, a, b: a + b if o == "+" else a - b)

    def mult(self):
        return self._bin(self.unary, ["*", "/", "%"], lambda o, a, b: a * b if o == "*" else (a // b if o == "/" else a % b))

    def unary(self):
        if self.accept("!"):
            v = self.unary()
            t = truth(v)
            return UNKNOWN if t is UNKNOWN else (not t)
        if self.accept("~"):
            v = self.unary()
            return UNKNOWN if v is UNKNOWN else ~int(v)
        if self.accept("-"):
            v = self.unary()
            return UNKNOWN if v is UNKNOWN else -v
        if self.accept("+"):
            return self.unary()
        return self.postfix()

    def postfix(self):
        k, v = self.peek()
        if k == "num":
            self.i += 1
            return parse_int(v)
        if k == "str":
            self.i += 1
            return bytes(v[1:-1], "utf-8").decode("unicode_escape")
        if self.accept("("):
            val = self.ternary()
            if not self.accept(")"):
                raise ValueError("')' attendu")
            return val
        if self.accept("{"):  # concaténation de chaînes
            parts = []
            while True:
                parts.append(self.ternary())
                if self.accept(","):
                    continue
                if self.accept("}"):
                    break
                raise ValueError("'}' attendu")
            return UNKNOWN if any(p is UNKNOWN for p in parts) else "".join(str(p) for p in parts)
        if k == "id":
            self.i += 1
            name = v
            if name in ("this", "super"):
                if self.accept("."):
                    k2, name = self.peek()
                    self.i += 1
                else:
                    return UNKNOWN
            if self.peek() == ("op", "("):
                args = self.args()
                return self.ctx.call(None, name, args)
            cur = self.ctx.lookup(name)
            if cur is Evaluator.MISSING:
                cur = self.ctx.enums.get(name, UNKNOWN) if name in self.ctx.enums else (
                    Sym(name) if re.match(r"^[A-Z][A-Z0-9_]+$", name) else UNKNOWN)
            while True:
                if self.accept("."):
                    k2, member = self.peek()
                    self.i += 1
                    if self.peek() == ("op", "("):
                        args = self.args()
                        cur = self.ctx.call(cur, member, args)
                    else:
                        cur = self.ctx.member(cur, member)
                elif self.peek() == ("op", "["):
                    self.i += 1
                    idx = self.ternary()
                    if not self.accept("]"):
                        raise ValueError("']' attendu")
                    cur = self.ctx.index(cur, idx)
                else:
                    return cur
        raise ValueError(f"expression inattendue: {k} {v}")

    def args(self):
        self.accept("(")
        out = []
        if self.accept(")"):
            return out
        while True:
            out.append(self.ternary())
            if self.accept(","):
                continue
            if self.accept(")"):
                return out
            raise ValueError("')' attendu")


def truth(v):
    if v is UNKNOWN:
        return UNKNOWN
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v != 0
    if isinstance(v, Sym):
        return UNKNOWN
    if v is None:
        return False
    return True


def _eq(a, b):
    if isinstance(a, Sym) or isinstance(b, Sym):
        return str(a) == str(b)
    if isinstance(a, (int, bool)) and isinstance(b, (int, bool)):
        return int(a) == int(b)
    return a == b


def sformatf(fmt, args):
    """$sformatf avec UNKNOWN -> '*' (motif)."""
    if fmt is UNKNOWN:
        return UNKNOWN
    it = iter(args)

    def rep(m):
        try:
            a = next(it)
        except StopIteration:
            return m.group(0)
        if a is UNKNOWN:
            return "*"
        spec = m.group(2).lower()
        if spec in ("d", "s", "0d"):
            return str(a)
        if spec in ("h", "x"):
            return format(int(a), "x")
        if spec == "b":
            return format(int(a), "b")
        return str(a)

    return re.sub(r"%(\d*)([dDsShHxXbB])", lambda m: rep(m), fmt)


_GLOB_CACHE: dict[str, "re.Pattern"] = {}


def glob_match(pattern: str, path: str) -> bool:
    """Glob UVM : '*' et '?' seulement ; les crochets sont littéraux (ex. masters[0])."""
    rx = _GLOB_CACHE.get(pattern)
    if rx is None:
        rx = _GLOB_CACHE[pattern] = re.compile(
            "^" + "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern) + "$", re.S)
    return rx.match(path) is not None
