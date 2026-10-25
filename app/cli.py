"""Command line: ``python -m app {serve,prove,sat,bench}``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="axiomatic", description="Axiomatic Gateway")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the HTTP API with uvicorn")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    p = sub.add_parser("prove", help="prove a goal from a clause file (one clause per line)")
    p.add_argument("file", type=Path)
    p.add_argument("--goal", default=None)
    p.add_argument("--timeout", type=float, default=10.0)
    p.add_argument("--json", action="store_true")
    p2 = sub.add_parser("problem", help="run a built-in suite problem")
    p2.add_argument("name", nargs="?")
    q = sub.add_parser("sat", help="solve a DIMACS CNF file")
    q.add_argument("file", type=Path)
    b = sub.add_parser("bench", help="run benchmarks")
    b.add_argument("--out", type=Path, default=None)
    b.add_argument("--quick", action="store_true")
    b.add_argument("--no-plot", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if a.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )

    if a.cmd == "serve":
        import uvicorn

        uvicorn.run("app.main:app", host=a.host, port=a.port)
        return 0
    if a.cmd in ("prove", "problem"):
        from app.parser import parse_clause, parse_clauses
        from app.problems import suite
        from app.prover import prove

        if a.cmd == "problem":
            probs = suite()
            if a.name is None:
                for n, pr in probs.items():
                    print(f"{n:28s} {pr.expected:10s} {pr.description}")
                return 0
            pr = probs[a.name]
            res = prove(pr.axioms, pr.goal)
        else:
            axioms = parse_clauses(a.file.read_text().splitlines())
            res = prove(axioms, parse_clause(a.goal) if a.goal else None, timeout_s=a.timeout)
        if getattr(a, "json", False):
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print(
                f"status: {res.status} ({res.reason}); verified={res.verified}; "
                f"{res.iterations} iterations, {res.elapsed_s * 1e3:.1f} ms"
            )
            for d in res.proof:
                print(f"  {d.id:>4}  {d.clause!s:40s} {d.rule} {list(d.parents) or ''}")
        return 0 if res.status != "unknown" else 2
    if a.cmd == "sat":
        from app.engines import solve_sat

        num_vars = 0
        clauses: List[List[int]] = []
        cur: List[int] = []
        for line in a.file.read_text().splitlines():
            t = line.split()
            if not t or t[0] in ("c", "%"):
                continue
            if t[0] == "p":
                num_vars = int(t[2])
                continue
            for x in map(int, t):
                if x == 0:
                    clauses.append(cur)
                    cur = []
                else:
                    cur.append(x)
        print(json.dumps(solve_sat(num_vars, clauses)))
        return 0
    if a.cmd == "bench":
        from app import benchmarks

        bres = benchmarks.run(quick=a.quick)
        print(benchmarks.to_markdown(bres))
        print(f"total {bres['total_s']} s")
        if a.out:
            benchmarks.save(bres, a.out, make_plot=not a.no_plot)
        return 0
    return 1  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
