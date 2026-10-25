"""
logic.py
========
Logical representations for First-Order and Propositional Logic.
Defines Terms, Variables, Functions, Predicates, Literals, Clauses, and Formulas.
Also contains Unification and Clause Resolution logic.
"""

from typing import Any, Dict, Iterator, List, Optional, Set, Tuple, Union

class Term:
    """Base class for terms in First-Order Logic."""
    pass

class Var(Term):
    """Variable term in FOL (e.g. 'x')."""
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        return isinstance(other, Var) and self.name == other.name

    def __hash__(self):
        return hash(("var", self.name))

class Fn(Term):
    """Function term in FOL (e.g. 'f(x)' or constant '0' if args is empty)."""
    def __init__(self, name: str, args: Optional[List[Term]] = None):
        self.name = name
        self.args = args or []

    def __repr__(self):
        if not self.args:
            return self.name
        return f"{self.name}({', '.join(map(str, self.args))})"

    def __eq__(self, other):
        return isinstance(other, Fn) and self.name == other.name and self.args == other.args

    def __hash__(self):
        return hash(("fn", self.name, tuple(self.args)))

class Pred:
    """Predicate in FOL (e.g. 'P(x, y)' or 'Equals(x, y)')."""
    def __init__(self, name: str, args: List[Term]):
        self.name = name
        self.args = args

    def __repr__(self):
        return f"{self.name}({', '.join(map(str, self.args))})"

    def __eq__(self, other):
        return isinstance(other, Pred) and self.name == other.name and self.args == other.args

    def __hash__(self):
        return hash((self.name, tuple(self.args)))

class Literal:
    """A Literal represents a Predicate or its negation."""
    def __init__(self, pred: Pred, sign: bool = True):
        self.pred = pred
        self.sign = sign  # True = positive, False = negative

    def negate(self):
        return Literal(self.pred, not self.sign)

    def __repr__(self):
        return ("" if self.sign else "~") + str(self.pred)

    def __eq__(self, other):
        return isinstance(other, Literal) and self.pred == other.pred and self.sign == other.sign

    def __hash__(self):
        return hash((self.pred, self.sign))

class Clause:
    """A Clause represents a disjunction of Literals (e.g., L1 | L2 | ... | Ln)."""
    def __init__(self, literals: List[Literal]):
        self.literals = frozenset(literals)

    def __repr__(self):
        if not self.literals:
            return "[]"
        return " | ".join(map(str, sorted(self.literals, key=lambda l: str(l))))

    def __eq__(self, other):
        return isinstance(other, Clause) and self.literals == other.literals

    def __hash__(self):
        return hash(self.literals)

    def is_empty(self) -> bool:
        return len(self.literals) == 0

# --- Formulas for Propositional / First-Order Logic (Natural Deduction) ---

class Formula:
    """Base class for general logical formulas."""
    pass

class Prop(Formula):
    """Propositional variable (e.g. P)."""
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        return isinstance(other, Prop) and self.name == other.name

    def __hash__(self):
        return hash(("prop", self.name))

class And(Formula):
    """Conjunction of two formulas."""
    def __init__(self, left: Formula, right: Formula):
        self.left = left
        self.right = right

    def __repr__(self):
        return f"({self.left} & {self.right})"

    def __eq__(self, other):
        return isinstance(other, And) and self.left == other.left and self.right == other.right

    def __hash__(self):
        return hash(("and", self.left, self.right))

class Or(Formula):
    """Disjunction of two formulas."""
    def __init__(self, left: Formula, right: Formula):
        self.left = left
        self.right = right

    def __repr__(self):
        return f"({self.left} | {self.right})"

    def __eq__(self, other):
        return isinstance(other, Or) and self.left == other.left and self.right == other.right

    def __hash__(self):
        return hash(("or", self.left, self.right))

class Implies(Formula):
    """Logical implication."""
    def __init__(self, antecedent: Formula, consequent: Formula):
        self.antecedent = antecedent
        self.consequent = consequent

    def __repr__(self):
        return f"({self.antecedent} -> {self.consequent})"

    def __eq__(self, other):
        return isinstance(other, Implies) and self.antecedent == other.antecedent and self.consequent == other.consequent

    def __hash__(self):
        return hash(("implies", self.antecedent, self.consequent))

class Not(Formula):
    """Logical negation."""
    def __init__(self, formula: Formula):
        self.formula = formula

    def __repr__(self):
        return f"~{self.formula}"

    def __eq__(self, other):
        return isinstance(other, Not) and self.formula == other.formula

    def __hash__(self):
        return hash(("not", self.formula))

# --- Unification & Substitution ---

def apply_sub_term(term: Term, sub: Dict[str, Term]) -> Term:
    """Applies a substitution mapping to a Term."""
    if isinstance(term, Var):
        if term.name in sub:
            return apply_sub_term(sub[term.name], sub)
        return term
    elif isinstance(term, Fn):
        return Fn(term.name, [apply_sub_term(arg, sub) for arg in term.args])
    return term

def apply_sub_pred(pred: Pred, sub: Dict[str, Term]) -> Pred:
    """Applies a substitution mapping to a Predicate."""
    return Pred(pred.name, [apply_sub_term(arg, sub) for arg in pred.args])

def apply_sub_lit(lit: Literal, sub: Dict[str, Term]) -> Literal:
    """Applies a substitution mapping to a Literal."""
    return Literal(apply_sub_pred(lit.pred, sub), lit.sign)

def apply_sub_clause(clause: Clause, sub: Dict[str, Term]) -> Clause:
    """Applies a substitution mapping to a Clause."""
    return Clause([apply_sub_lit(lit, sub) for lit in clause.literals])

def resolve_sub(term: Any, sub: Dict[str, Term]) -> Any:
    """Resolves variable chains in substitution."""
    if isinstance(term, Var) and term.name in sub:
        return resolve_sub(sub[term.name], sub)
    return term

def occurs_check(v: Var, term: Any, sub: Dict[str, Term]) -> bool:
    """Occurs check to prevent infinite terms during unification."""
    term = resolve_sub(term, sub)
    if v == term:
        return True
    if isinstance(term, Fn):
        return any(occurs_check(v, arg, sub) for arg in term.args)
    if isinstance(term, Pred):
        return any(occurs_check(v, arg, sub) for arg in term.args)
    return False

def unify_var(v: Var, x: Any, sub: Dict[str, Term]) -> Optional[Dict[str, Term]]:
    """Unifies a variable with a term/variable."""
    if occurs_check(v, x, sub):
        return None
    new_sub = dict(sub)
    new_sub[v.name] = x
    return new_sub

def unify(x: Any, y: Any, sub: Optional[Dict[str, Term]] = None) -> Optional[Dict[str, Term]]:
    """Unifies two terms or predicates under a substitution."""
    if sub is None:
        sub = {}
    x = resolve_sub(x, sub)
    y = resolve_sub(y, sub)
    if x == y:
        return sub
    if isinstance(x, Var):
        return unify_var(x, y, sub)
    if isinstance(y, Var):
        return unify_var(y, x, sub)
    if isinstance(x, Fn) and isinstance(y, Fn):
        if x.name != y.name or len(x.args) != len(y.args):
            return None
        for ax, ay in zip(x.args, y.args):
            sub = unify(ax, ay, sub)
            if sub is None:
                return None
        return sub
    if isinstance(x, Pred) and isinstance(y, Pred):
        if x.name != y.name or len(x.args) != len(y.args):
            return None
        for ax, ay in zip(x.args, y.args):
            sub = unify(ax, ay, sub)
            if sub is None:
                return None
        return sub
    return None

def rename_variables(clause: Clause, suffix: str) -> Clause:
    """Renames all variables in a Clause by appending a suffix."""
    sub: Dict[str, Term] = {}
    def collect_vars(term: Term):
        if isinstance(term, Var):
            sub[term.name] = Var(f"{term.name}_{suffix}")
        elif isinstance(term, Fn):
            for arg in term.args:
                collect_vars(arg)
    for lit in clause.literals:
        for arg in lit.pred.args:
            collect_vars(arg)
    return apply_sub_clause(clause, sub)

def resolve_clauses(c1: Clause, c2: Clause, var_counter: int) -> List[Tuple[Clause, Dict[str, Term], Literal, Literal]]:
    """
    Attempts to resolve c1 and c2. Returns a list of resolvent clauses
    along with their unification substitution and resolved literals.
    """
    c1_renamed = rename_variables(c1, f"L{var_counter}")
    c2_renamed = rename_variables(c2, f"R{var_counter}")
    resolvents = []
    for lit1 in c1_renamed.literals:
        for lit2 in c2_renamed.literals:
            if lit1.sign != lit2.sign:
                sub = unify(lit1.pred, lit2.pred)
                if sub is not None:
                    lits = (c1_renamed.literals - {lit1}) | (c2_renamed.literals - {lit2})
                    resolved_lits = [apply_sub_lit(l, sub) for l in lits]
                    resolvents.append((Clause(resolved_lits), sub, lit1, lit2))
    return resolvents


# --- One-way matching, subsumption, factoring (added in v2) ---


def match_term(pattern: Any, target: Any, sub: Dict[str, Term]) -> Optional[Dict[str, Term]]:
    """One-way matching: find ``sub`` with ``pattern·sub == target``.

    Unlike :func:`unify`, variables in ``target`` are treated as constants, which
    is what subsumption and "is an instance of" checks require.
    """
    if isinstance(pattern, Var):
        bound = sub.get(pattern.name)
        if bound is None:
            new_sub = dict(sub)
            new_sub[pattern.name] = target
            return new_sub
        return sub if bound == target else None
    if isinstance(pattern, (Fn, Pred)):
        if type(target) is not type(pattern) or pattern.name != target.name:
            return None
        if len(pattern.args) != len(target.args):
            return None
        cur: Optional[Dict[str, Term]] = sub
        for a, b in zip(pattern.args, target.args):
            cur = match_term(a, b, cur) if cur is not None else None
            if cur is None:
                return None
        return cur
    return sub if pattern == target else None


def subsumption_substitutions(general: Clause, specific: Clause) -> Iterator[Dict[str, Term]]:
    """Yield every ``sub`` such that ``general·sub ⊆ specific`` (literal-wise)."""
    lits_g = sorted(general.literals, key=lambda lit: -len(str(lit)))
    lits_s = list(specific.literals)

    def search(idx: int, sub: Dict[str, Term]) -> Iterator[Dict[str, Term]]:
        if idx == len(lits_g):
            yield sub
            return
        lit = lits_g[idx]
        for target in lits_s:
            if lit.sign == target.sign:
                new_sub = match_term(lit.pred, target.pred, sub)
                if new_sub is not None:
                    yield from search(idx + 1, new_sub)

    yield from search(0, {})


def subsumes(general: Clause, specific: Clause) -> bool:
    """True iff some substitution maps ``general`` into a subset of ``specific``."""
    return next(subsumption_substitutions(general, specific), None) is not None


def is_instance(general: Clause, specific: Clause) -> bool:
    """True iff ``specific == general·sub`` exactly for some substitution."""
    for sub in subsumption_substitutions(general, specific):
        if _apply_simultaneous(general, sub) == specific:
            return True
    return False


def _apply_simultaneous(clause: Clause, sub: Dict[str, Term]) -> Clause:
    """Apply a *matching* substitution (no chasing: x->f(x) is legal here)."""

    def t(term: Any) -> Any:
        if isinstance(term, Var):
            return sub.get(term.name, term)
        if isinstance(term, Fn):
            return Fn(term.name, [t(a) for a in term.args])
        return term

    return Clause([Literal(Pred(lit.pred.name, [t(a) for a in lit.pred.args]), lit.sign) for lit in clause.literals])


def is_variant(a: Clause, b: Clause) -> bool:
    """Equal up to consistent variable renaming (checked as mutual instances)."""
    return len(a.literals) == len(b.literals) and is_instance(a, b) and is_instance(b, a)


def is_tautology(clause: Clause) -> bool:
    """A clause containing both L and ~L is valid and can be discarded."""
    return any(lit.negate() in clause.literals for lit in clause.literals)


def factors(clause: Clause) -> List[Tuple[Clause, Dict[str, Term]]]:
    """All binary factors: unify two same-sign literals and merge them."""
    out: List[Tuple[Clause, Dict[str, Term]]] = []
    lits = list(clause.literals)
    for i in range(len(lits)):
        for j in range(i + 1, len(lits)):
            if lits[i].sign == lits[j].sign:
                sub = unify(lits[i].pred, lits[j].pred)
                if sub is not None:
                    out.append((apply_sub_clause(clause, sub), sub))
    return out


def clause_vars(clause: Clause) -> Set[str]:
    names: Set[str] = set()

    def walk(t: Any) -> None:
        if isinstance(t, Var):
            names.add(t.name)
        elif isinstance(t, (Fn, Pred)):
            for a in t.args:
                walk(a)

    for lit in clause.literals:
        walk(lit.pred)
    return names


def negate_goal(goal: Clause, prefix: str = "sk") -> List[Clause]:
    """Clauses for ¬(∀vars. goal): Skolemize the goal's variables to fresh constants.

    The goal ``L1 | ... | Ln`` is implicitly universally quantified; its negation is
    ``∃vars. ¬L1 ∧ ... ∧ ¬Ln``, so every variable becomes a fresh Skolem constant
    shared across the resulting unit clauses.
    """
    sub: Dict[str, Term] = {v: Fn(f"{prefix}_{v}") for v in sorted(clause_vars(goal))}
    return [Clause([apply_sub_lit(lit, sub).negate()]) for lit in goal.literals]


def symbol_count(clause: Clause) -> int:
    """Clause weight used by the given-clause selection heuristic."""

    def w(t: Any) -> int:
        if isinstance(t, (Fn, Pred)):
            return 1 + sum(w(a) for a in t.args)
        return 1

    return sum(w(lit.pred) for lit in clause.literals)
