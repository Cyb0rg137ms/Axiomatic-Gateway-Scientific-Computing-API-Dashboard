"""Tests for the v2 prover, checker fixes, parser, SAT fallback, cache, jobs and API."""

from __future__ import annotations

import random
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app import engines
from app.cache import TelemetryCache, stable_key
from app.legacy import LegacyProver
from app.logic import Clause, Fn, Literal, Pred, Var, is_instance, negate_goal, subsumes
from app.main import app
from app.parser import ClauseSyntaxError, parse_clause
from app.problems import pigeonhole, suite
from app.proof import DerivationEngine, ProofChecker, ProofStep
from app.prover import prove, verify_proof
from app.registry import SimulationRegistry
from app.sat import check_model, solve_dpll

client = TestClient(app)


def P(*args: object, sign: bool = True, name: str = "P") -> Literal:
    return Literal(Pred(name, list(args)), sign)  # type: ignore[arg-type]


# --- soundness bugs found in v1 -------------------------------------------------


def test_checker_rejects_generalised_axiom_instance() -> None:
    ax = Clause([P(Fn("a"))])
    ok, msg = ProofChecker.verify_proof([ProofStep(1, Clause([P(Var("x"))]), "Axiom")], axioms=[ax])
    assert not ok and "not a valid axiom instance" in msg
    ok, _ = ProofChecker.verify_proof([ProofStep(1, Clause([P(Fn("a"))]), "Axiom")], axioms=[Clause([P(Var("x"))])])
    assert ok


def test_subsumption_is_one_way_matching() -> None:
    general = Clause([P(Var("x"), Fn("b"))])
    assert not subsumes(general, Clause([P(Fn("a"), Var("y"))]))
    assert subsumes(general, Clause([P(Fn("a"), Fn("b"))]))
    assert not ProofChecker.check_subsumes(general, Clause([P(Fn("a"), Var("y"))]))


def test_is_instance_handles_self_referential_matches() -> None:
    assert is_instance(Clause([P(Var("x"))]), Clause([P(Fn("S", [Var("x")]))]))


def test_goal_with_variables_is_skolemized() -> None:
    neg = negate_goal(Clause([P(Var("X"))]))
    assert str(neg[0]) == "~P(sk_X)"
    res = prove([Clause([P(Fn("a"))])], Clause([P(Var("X"))]))
    assert res.status == "saturated"
    assert LegacyProver.prove_resolution([Clause([P(Fn("a"))])], Clause([P(Var("X"))])) is True  # the v1 bug


def test_factoring_makes_refutation_possible() -> None:
    p = suite()["needs_factoring"]
    assert prove(p.axioms, p.goal).status == "proved"
    assert LegacyProver.prove_resolution(p.axioms, Clause([])) is False


# --- prover --------------------------------------------------------------------


@pytest.mark.parametrize("name", [n for n in suite() if n != "php_5_4"])
def test_suite_expected_outcomes(name: str) -> None:
    p = suite()[name]
    res = prove(p.axioms, p.goal, timeout_s=20)
    assert res.status == p.expected, res.reason
    if res.status == "proved":
        assert res.verified is True
        assert res.proof[-1].clause.is_empty()


def test_budget_gives_unknown_not_false() -> None:
    p = pigeonhole(4)
    res = prove(p.axioms, None, max_iterations=20)
    assert res.status == "unknown" and "budget" in res.reason


def test_tampered_proof_fails_verification() -> None:
    p = suite()["syllogism"]
    res = prove(p.axioms, p.goal)
    assert verify_proof(res.proof, p.axioms, p.goal)
    assert not verify_proof(res.proof, p.axioms[:1], p.goal)  # drop an axiom -> step no longer justified


def test_wrapper_back_compat() -> None:
    p = suite()["peano_s0_ne_0"]
    assert DerivationEngine.prove_resolution(p.axioms, p.goal) is True  # type: ignore[arg-type]


def test_backward_chaining_finds_binding() -> None:
    db = [Clause([P(Var("x"), name="Q"), P(Var("x"), sign=False)])] + [Clause([P(Fn(f"c{i}"))]) for i in range(3)]
    sols = DerivationEngine.prove_backward([P(Var("z"), name="Q")], db)
    assert len(sols) == 3


# --- parser ----------------------------------------------------------------------


def test_parser_roundtrip_and_errors() -> None:
    c = parse_clause("~man(X) | mortal(f(X, a))")
    assert {str(lit) for lit in c.literals} == {"~man(X)", "mortal(f(X, a))"}
    man = next(lit for lit in c.literals if lit.pred.name == "man")
    assert isinstance(man.pred.args[0], Var) and not man.sign
    assert parse_clause("$false").is_empty()
    for bad in ["", "p(", "p | ", "p q", "p(X,)"]:
        with pytest.raises(ClauseSyntaxError):
            parse_clause(bad)


# --- SAT -------------------------------------------------------------------------


def test_dpll_matches_brute_force() -> None:
    rng = random.Random(0)
    for _ in range(60):
        n = rng.randint(1, 8)
        cls = [[rng.choice([-1, 1]) * rng.randint(1, n) for _ in range(3)] for _ in range(rng.randint(1, 30))]
        brute = any(check_model(cls, [v if (m >> (v - 1)) & 1 else -v for v in range(1, n + 1)]) for m in range(2**n))
        r = solve_dpll(n, cls)
        assert (r.status == "SAT") == brute
        if r.model is not None:
            assert check_model(cls, r.model)


def test_dpll_rejects_bad_literals() -> None:
    with pytest.raises(ValueError):
        solve_dpll(2, [[3]])


# --- cache / registry ------------------------------------------------------------


def test_cache_ttl_lru_and_threads() -> None:
    now = [0.0]
    c = TelemetryCache(max_entries=2, clock=lambda: now[0])
    c.set("a", 1, ttl_seconds=10)
    c.set("b", 2)
    c.get("a")
    c.set("c", 3)  # evicts LRU "b"
    assert c.get("b") is None and c.get("a") == 1
    now[0] = 11
    assert c.get("a") is None
    big = TelemetryCache(max_entries=10_000)
    threads = [threading.Thread(target=lambda k=k: [big.set(f"{k}-{i}", i) for i in range(500)]) for k in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(big) == 4000
    assert stable_key("x", {"b": 1, "a": 2}) == stable_key("x", {"a": 2, "b": 1})


def test_registry_runs_real_jobs_and_records_failures() -> None:
    reg = SimulationRegistry(max_workers=1)
    ok = reg.submit("ok", {}, lambda: 41 + 1)
    bad = reg.submit("bad", {}, lambda: 1 / 0)
    reg.shutdown()
    assert ok.status == "completed" and ok.result == 42
    assert bad.status == "failed" and "ZeroDivisionError" in (bad.error or "")


# --- API -------------------------------------------------------------------------


def test_api_prove_and_cache() -> None:
    body = {"axioms": ["~man(X) | mortal(X)", "man(socrates)"], "goal": "mortal(socrates)"}
    r1 = client.post("/prove", json=body).json()
    assert r1["status"] == "proved" and r1["verified"] is True and r1["cached"] is False
    assert client.post("/prove", json=body).json()["cached"] is True
    r = client.post("/prove", json={"axioms": ["p(a)"], "goal": "p(X)"}).json()
    assert r["status"] == "saturated"


def test_api_validation_errors() -> None:
    assert client.post("/prove", json={"axioms": ["p("]}).status_code == 422
    assert client.post("/prove", json={"axioms": [], "timeout_s": 999}).status_code == 422
    assert client.post("/solve/sat", json={"num_vars": 1, "clauses": [[2]]}).status_code == 422
    assert client.post("/solve/quantum", json={"n_registers": 0, "dimension": 2, "bond_dim": 2}).status_code == 422


def test_api_sat_builtin_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engines, "_has", lambda m: False)
    r = client.post("/solve/sat", json={"num_vars": 3, "clauses": [[1, 2], [-1, 3], [-3]]}).json()
    assert r["engine"] == "builtin_dpll" and r["status"] == "SAT" and r["model_verified"] is True
    r = client.post("/solve/sat", json={"num_vars": 1, "clauses": [[1], [-1]]}).json()
    assert r["status"] == "UNSAT"


def test_api_missing_engines_return_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engines, "_has", lambda m: False)
    r = client.post("/solve/quantum", json={"n_registers": 3, "dimension": 2, "bond_dim": 4})
    assert r.status_code == 503
    assert client.get("/").json()["engines"]["quantum_emulator"] == "unavailable"


def test_api_background_prove_job_completes() -> None:
    p = {"axioms": ["~p | q", "p"], "goal": "q"}
    tid = client.post("/simulation", json={"name": "prove", "params": p}).json()["task_id"]
    deadline = time.time() + 10
    data: dict = {}
    while time.time() < deadline:
        data = client.get(f"/simulation/{tid}").json()
        if data["status"] in ("completed", "failed"):
            break
        time.sleep(0.01)
    assert data["status"] == "completed" and data["result"]["status"] == "proved"
    assert client.post("/simulation", json={"name": "prove", "params": {"axioms": ["p("]}}).status_code == 422
    assert client.get("/simulation/nope").status_code == 404


def test_api_problems_and_metrics() -> None:
    names = {p["name"] for p in client.get("/problems").json()}
    assert {"syllogism", "needs_factoring", "php_4_3"} <= names
    assert "cache" in client.get("/metrics").json()
