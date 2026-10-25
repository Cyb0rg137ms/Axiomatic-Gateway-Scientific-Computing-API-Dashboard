"""Tiny TPTP-style CNF syntax: ``~p(X) | q(f(X), a)``.

* Identifiers starting with an uppercase letter or ``_`` are **variables**.
* Everything else (lowercase identifiers, digits) is a constant/function/predicate.
* ``~`` negates a literal, ``|`` separates literals; ``$false`` is the empty clause.
"""

from __future__ import annotations

import re
from typing import List

from app.logic import Clause, Fn, Literal, Pred, Term, Var

_TOKEN = re.compile(r"\s*(?:(\$false)|([A-Za-z_][A-Za-z0-9_]*|\d+)|(.))")


class ClauseSyntaxError(ValueError):
    """Raised with the offending position when a clause cannot be parsed."""


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text
        self.toks: List[tuple[str, str, int]] = []
        pos = 0
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if m is None or m.end() == pos:
                break
            if m.group(1):
                self.toks.append(("false", m.group(1), m.start(1)))
            elif m.group(2):
                self.toks.append(("id", m.group(2), m.start(2)))
            elif m.group(3):
                self.toks.append(("sym", m.group(3), m.start(3)))
            pos = m.end()
        self.i = 0

    def peek(self) -> tuple[str, str, int] | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def expect(self, value: str) -> None:
        tok = self.peek()
        if tok is None or tok[1] != value:
            where = tok[2] if tok else len(self.text)
            raise ClauseSyntaxError(f"expected {value!r} at column {where} in {self.text!r}")
        self.i += 1

    def ident(self) -> str:
        tok = self.peek()
        if tok is None or tok[0] != "id":
            where = tok[2] if tok else len(self.text)
            raise ClauseSyntaxError(f"expected identifier at column {where} in {self.text!r}")
        self.i += 1
        return tok[1]

    def args(self) -> List[Term]:
        out: List[Term] = []
        tok = self.peek()
        if tok is not None and tok[1] == "(":
            self.i += 1
            out.append(self.term())
            while (tok := self.peek()) is not None and tok[1] == ",":
                self.i += 1
                out.append(self.term())
            self.expect(")")
        return out

    def term(self) -> Term:
        name = self.ident()
        if name[0].isupper() or name[0] == "_":
            return Var(name)
        return Fn(name, self.args())

    def literal(self) -> Literal:
        sign = True
        while (tok := self.peek()) is not None and tok[1] == "~":
            self.i += 1
            sign = not sign
        name = self.ident()
        return Literal(Pred(name, self.args()), sign)

    def clause(self) -> Clause:
        tok = self.peek()
        if tok is not None and tok[0] == "false":
            self.i += 1
            lits: List[Literal] = []
        else:
            lits = [self.literal()]
            while (tok := self.peek()) is not None and tok[1] == "|":
                self.i += 1
                lits.append(self.literal())
        if self.peek() is not None:
            raise ClauseSyntaxError(f"trailing input at column {self.peek()[2]} in {self.text!r}")  # type: ignore[index]
        return Clause(lits)


def parse_clause(text: str) -> Clause:
    """Parse one clause; raises :class:`ClauseSyntaxError` on bad input."""
    if not text.strip():
        raise ClauseSyntaxError("empty clause text (use $false for the empty clause)")
    return _Parser(text).clause()


def parse_clauses(lines: List[str]) -> List[Clause]:
    return [parse_clause(s) for s in lines if s.strip() and not s.lstrip().startswith("%")]
