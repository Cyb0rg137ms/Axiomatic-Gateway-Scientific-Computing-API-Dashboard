"""
axioms.py
=========
Axiom registry for ZFC Set Theory, Peano Arithmetic, and Propositional Logic.
Provides predefined axioms represented as Clauses and Formulas.
"""

from typing import Dict, List, Any
from app.logic import Var, Fn, Pred, Literal, Clause, Prop, And, Or, Implies, Not

class AxiomRegistry:
    """Registry containing standard axiom sets for mathematical theories."""
    
    def __init__(self):
        self._zfc: List[Clause] = []
        self._peano: List[Clause] = []
        self._propositional: List[Implies] = []
        
        self._init_zfc()
        self._init_peano()
        self._init_propositional()

    def _init_zfc(self):
        # Variables
        x, y, z = Var("x"), Var("y"), Var("z")
        
        # Extensionality Axiom Clauses
        # 1. x = y => (z in x => z in y)
        self._zfc.append(Clause([
            Literal(Pred("Equals", [x, y]), False),
            Literal(Pred("Member", [z, x]), False),
            Literal(Pred("Member", [z, y]), True)
        ]))
        # 2. x = y => (z in y => z in x)
        self._zfc.append(Clause([
            Literal(Pred("Equals", [x, y]), False),
            Literal(Pred("Member", [z, y]), False),
            Literal(Pred("Member", [z, x]), True)
        ]))
        # 3. Converse using Skolem function f(x, y) representing the witness to inequality
        # (~Equals(x,y) <=> Exists z. (z in x ^ ~z in y) v (~z in x ^ z in y))
        f_xy = Fn("f", [x, y])
        self._zfc.append(Clause([
            Literal(Pred("Member", [f_xy, x]), True),
            Literal(Pred("Member", [f_xy, y]), True),
            Literal(Pred("Equals", [x, y]), True)
        ]))
        self._zfc.append(Clause([
            Literal(Pred("Member", [f_xy, x]), False),
            Literal(Pred("Member", [f_xy, y]), False),
            Literal(Pred("Equals", [x, y]), True)
        ]))

        # Empty Set Axiom
        # For all x, ~(x in emptyset)
        self._zfc.append(Clause([
            Literal(Pred("Member", [x, Fn("emptyset")]), False)
        ]))

        # Pairing Axiom
        # z in pair(x, y) <=> z = x v z = y
        self._zfc.append(Clause([
            Literal(Pred("Member", [z, Fn("pair", [x, y])]), False),
            Literal(Pred("Equals", [z, x]), True),
            Literal(Pred("Equals", [z, y]), True)
        ]))
        self._zfc.append(Clause([
            Literal(Pred("Equals", [z, x]), False),
            Literal(Pred("Member", [z, Fn("pair", [x, y])]), True)
        ]))
        self._zfc.append(Clause([
            Literal(Pred("Equals", [z, y]), False),
            Literal(Pred("Member", [z, Fn("pair", [x, y])]), True)
        ]))

        # Union Axiom
        # z in union(x) <=> Exists y. (z in y ^ y in x)
        # Skolem function g(z, x) representing y
        g_zx = Fn("g", [z, x])
        self._zfc.append(Clause([
            Literal(Pred("Member", [z, Fn("union", [x])]), False),
            Literal(Pred("Member", [z, g_zx]), True)
        ]))
        self._zfc.append(Clause([
            Literal(Pred("Member", [z, Fn("union", [x])]), False),
            Literal(Pred("Member", [g_zx, x]), True)
        ]))
        self._zfc.append(Clause([
            Literal(Pred("Member", [z, y]), False),
            Literal(Pred("Member", [y, x]), False),
            Literal(Pred("Member", [z, Fn("union", [x])]), True)
        ]))

    def _init_peano(self):
        # Variables
        x, y = Var("x"), Var("y")
        zero = Fn("0")
        
        # 1. 0 is not the successor of any number: ~(S(x) = 0)
        self._peano.append(Clause([
            Literal(Pred("Equals", [Fn("S", [x]), zero]), False)
        ]))
        
        # 2. S(x) = S(y) => x = y
        self._peano.append(Clause([
            Literal(Pred("Equals", [Fn("S", [x]), Fn("S", [y])]), False),
            Literal(Pred("Equals", [x, y]), True)
        ]))
        
        # 3. Addition: x + 0 = x
        self._peano.append(Clause([
            Literal(Pred("Equals", [Fn("plus", [x, zero]), x]), True)
        ]))
        
        # 4. Addition: x + S(y) = S(x + y)
        self._peano.append(Clause([
            Literal(Pred("Equals", [Fn("plus", [x, Fn("S", [y])]), Fn("S", [Fn("plus", [x, y])])]), True)
        ]))
        
        # 5. Multiplication: x * 0 = 0
        self._peano.append(Clause([
            Literal(Pred("Equals", [Fn("times", [x, zero]), zero]), True)
        ]))
        
        # 6. Multiplication: x * S(y) = (x * y) + x
        self._peano.append(Clause([
            Literal(Pred("Equals", [Fn("times", [x, Fn("S", [y])]), Fn("plus", [Fn("times", [x, y]), x])]), True)
        ]))

    def _init_propositional(self):
        P, Q, R = Prop("P"), Prop("Q"), Prop("R")
        
        # Axiom 1: P -> (Q -> P)
        self._propositional.append(Implies(P, Implies(Q, P)))
        
        # Axiom 2: (P -> (Q -> R)) -> ((P -> Q) -> (P -> R))
        self._propositional.append(
            Implies(
                Implies(P, Implies(Q, R)),
                Implies(Implies(P, Q), Implies(P, R))
            )
        )
        
        # Axiom 3: (~P -> ~Q) -> (Q -> P)
        self._propositional.append(
            Implies(
                Implies(Not(P), Not(Q)),
                Implies(Q, P)
            )
        )

    def get_zfc_axioms(self) -> List[Clause]:
        """Returns the set of ZFC axioms in CNF (List of Clauses)."""
        return list(self._zfc)

    def get_peano_axioms(self) -> List[Clause]:
        """Returns the set of Peano arithmetic axioms in CNF (List of Clauses)."""
        return list(self._peano)

    def get_propositional_axioms(self) -> List[Implies]:
        """Returns the Hilbert-style propositional axioms (List of Implies)."""
        return list(self._propositional)
