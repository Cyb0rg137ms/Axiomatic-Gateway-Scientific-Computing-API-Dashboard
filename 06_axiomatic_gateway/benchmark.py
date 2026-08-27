"""
benchmark.py
============
Performance benchmark script for Axiomatic Gateway logical engines.
Runs the resolution prover and backward-chaining search to measure execution speed.
"""

import sys
import os
import time

# Ensure backend folder is in Python search path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.logic import Var, Fn, Pred, Literal, Clause
from app.axioms import AxiomRegistry
from app.proof import DerivationEngine

def benchmark_resolution_prover():
    # Prove that S(0) != 0 in Peano arithmetic
    registry = AxiomRegistry()
    peano = registry.get_peano_axioms()
    theorem = Clause([Literal(Pred("Equals", [Fn("S", [Fn("0")]), Fn("0")]), False)])
    
    t0 = time.perf_counter()
    iterations = 50
    for _ in range(iterations):
        result = DerivationEngine.prove_resolution(peano, theorem)
        assert result is True
    elapsed = (time.perf_counter() - t0) / iterations
    print(f"Resolution Proving Time Ms: {elapsed * 1000.0:.3f}")

def benchmark_backward_chaining():
    # Setup simple rule database
    # P(x) <- Q(x). Facts: Q(c_0) ... Q(c_9)
    # Target: P(c_5)
    database = [
        Clause([Literal(Pred("P", [Var("x")]), True), Literal(Pred("Q", [Var("x")]), False)])
    ]
    for i in range(10):
        database.append(Clause([Literal(Pred("Q", [Fn(f"c_{i}")]), True)]))
        
    goals = [Literal(Pred("P", [Fn("c_5")]), True)]
    
    t0 = time.perf_counter()
    iterations = 500
    for _ in range(iterations):
        solutions = DerivationEngine.prove_backward(goals, database)
        assert len(solutions) > 0
    elapsed = (time.perf_counter() - t0) / iterations
    print(f"Backward Chaining Time Ms: {elapsed * 1000.0:.4f}")

if __name__ == "__main__":
    print("Running Axiomatic Gateway benchmarks...")
    benchmark_resolution_prover()
    benchmark_backward_chaining()
