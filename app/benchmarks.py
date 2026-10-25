"""Reproducible benchmarks: ``python -m app bench --out docs/assets``.

1. Prover suite: v1 (verbatim legacy code) vs v2 on problems with known answers.
2. Built-in DPLL on random 3-SAT at the phase transition (m/n = 4.26).
3. In-process API latency for /prove (cold vs cache hit).
"""

from __future__ import annotations

import json
import logging
import platform
import random
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List

from app.legacy import LegacyProver
from app.logic import Clause
from app.problems import suite
from app.prover import prove
from app.sat import solve_dpll

log = logging.getLogger(__name__)


def _timed(fn: Any, reps: int) -> tuple[Any, float]:
    out, times = None, []
    for _ in range(reps):
        t0 = time.perf_counter()
        out = fn()
        times.append(time.perf_counter() - t0)
    return out, statistics.median(times) * 1e3


def bench_prover(timeout_s: float = 10.0) -> List[Dict[str, Any]]:
    rows = []
    for name, p in suite().items():
        slow = name.startswith("php_4") or name.startswith("php_5")
        reps = 1 if slow else 5
        v2, t2 = _timed(lambda p=p: prove(p.axioms, p.goal, timeout_s=timeout_s), reps)
        v1, t1 = _timed(lambda p=p: LegacyProver.prove_resolution(p.axioms, p.goal or Clause([])), reps)
        v1_status = "proved" if v1 else "not proved"
        rows.append(
            {
                "problem": name,
                "expected": p.expected,
                "v1_answer": v1_status,
                "v1_correct": (v1_status == "proved") == (p.expected == "proved"),
                "v1_ms": round(t1, 2),
                "v2_status": v2.status,
                "v2_correct": v2.status == p.expected,
                "v2_verified": v2.verified,
                "v2_iterations": v2.iterations,
                "v2_ms": round(t2, 2),
            }
        )
        log.info("%s: v1=%s (%.1f ms) v2=%s (%.1f ms)", name, v1_status, t1, v2.status, t2)
    return rows


def random_3sat(n: int, ratio: float, rng: random.Random) -> List[List[int]]:
    return [[v * rng.choice((-1, 1)) for v in rng.sample(range(1, n + 1), 3)] for _ in range(round(ratio * n))]


def bench_sat(sizes: tuple[int, ...] = (20, 30, 40, 50), instances: int = 10, seed: int = 0) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    rows = []
    for n in sizes:
        times, sat = [], 0
        for _ in range(instances):
            cnf = random_3sat(n, 4.26, rng)
            r = solve_dpll(n, cnf, timeout_s=30)
            times.append(r.elapsed_ms)
            sat += r.status == "SAT"
        rows.append(
            {
                "n": n,
                "m": round(4.26 * n),
                "instances": instances,
                "sat": sat,
                "median_ms": round(statistics.median(times), 2),
                "max_ms": round(max(times), 2),
            }
        )
    return rows


def bench_api(reps: int = 200) -> Dict[str, Any]:
    from fastapi.testclient import TestClient

    from app.main import app, cache

    client = TestClient(app)
    cache.clear()
    cold, warm = [], []
    for i in range(reps):
        body = {"axioms": ["~man(X) | mortal(X)", f"man(s{i})"], "goal": f"mortal(s{i})"}
        t0 = time.perf_counter()
        assert client.post("/prove", json=body).json()["status"] == "proved"
        cold.append((time.perf_counter() - t0) * 1e3)
        t0 = time.perf_counter()
        assert client.post("/prove", json=body).json()["cached"] is True
        warm.append((time.perf_counter() - t0) * 1e3)

    def q(xs: List[float], p: float) -> float:
        return round(sorted(xs)[int(p * (len(xs) - 1))], 3)

    return {
        "reps": reps,
        "cold_p50_ms": q(cold, 0.5),
        "cold_p95_ms": q(cold, 0.95),
        "cached_p50_ms": q(warm, 0.5),
        "cached_p95_ms": q(warm, 0.95),
    }


def run(quick: bool = False) -> Dict[str, Any]:
    t0 = time.perf_counter()
    res: Dict[str, Any] = {
        "env": {"python": platform.python_version(), "machine": platform.machine(), "processor": platform.processor()},
        "prover": bench_prover(timeout_s=2.0 if quick else 10.0),
        "sat": bench_sat(sizes=(20, 30) if quick else (20, 30, 40, 50), instances=3 if quick else 10),
        "api": bench_api(reps=20 if quick else 200),
    }
    res["total_s"] = round(time.perf_counter() - t0, 1)
    return res


def to_markdown(res: Dict[str, Any]) -> str:
    lines = [
        "| problem | expected | v1 answer | v1 ms | v2 status | verified | v2 ms |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in res["prover"]:
        mark1 = "" if r["v1_correct"] else " ✗"
        mark2 = "" if r["v2_correct"] else (" (budget)" if r["v2_status"] == "unknown" else " ✗")
        lines.append(
            f"| {r['problem']} | {r['expected']} | {r['v1_answer']}{mark1} | {r['v1_ms']} | "
            f"{r['v2_status']}{mark2} | {r['v2_verified']} | {r['v2_ms']} |"
        )
    lines += ["", "| n | m | SAT/instances | median ms | max ms |", "|---|---|---|---|---|"]
    for r in res["sat"]:
        lines.append(f"| {r['n']} | {r['m']} | {r['sat']}/{r['instances']} | {r['median_ms']} | {r['max_ms']} |")
    a = res["api"]
    lines += [
        "",
        f"/prove latency (in-process TestClient, {a['reps']} reps): cold p50 {a['cold_p50_ms']} ms / "
        f"p95 {a['cold_p95_ms']} ms; cache hit p50 {a['cached_p50_ms']} ms / p95 {a['cached_p95_ms']} ms",
    ]
    return "\n".join(lines)


def plot(res: Dict[str, Any], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = res["prover"]
    names = [r["problem"] for r in rows]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    xs = range(len(rows))
    w = 0.4
    ax.bar([x - w / 2 for x in xs], [max(r["v1_ms"], 0.01) for r in rows], w, label="v1 (legacy)", color="#bbbbbb")
    ax.bar(
        [x + w / 2 for x in xs], [max(r["v2_ms"], 0.01) for r in rows], w, label="v2 (given-clause)", color="#2b6cb0"
    )
    for x, r in zip(xs, rows, strict=True):
        if not r["v1_correct"]:
            ax.text(x - w / 2, max(r["v1_ms"], 0.01) * 1.3, "✗", ha="center", color="#c53030", fontsize=12)
        if not r["v2_correct"]:
            ax.text(x + w / 2, max(r["v2_ms"], 0.01) * 1.3, "?", ha="center", color="#c05621", fontsize=12)
    ax.set_yscale("log")
    ax.set_xticks(list(xs))
    ax.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("wall time (ms, log)")
    ax.set_title("Resolution prover: v1 vs v2 (✗ = wrong answer, ? = budget exhausted)")
    ax.legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def save(res: Dict[str, Any], out_dir: Path, make_plot: bool = True) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bench.json").write_text(json.dumps(res, indent=2))
    (out_dir / "bench.md").write_text(to_markdown(res) + "\n")
    if make_plot:
        plot(res, out_dir / "prover_bench.png")
