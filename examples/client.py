"""Call a running gateway: `axiomatic serve` then `python examples/client.py`."""

import json
import urllib.request


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:8000{path}", json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


if __name__ == "__main__":
    res = post("/prove", {"axioms": ["~man(X) | mortal(X)", "man(socrates)"], "goal": "mortal(socrates)"})
    print(res["status"], "verified:", res["verified"])
    for step in res["proof"]:
        print(f"  {step['id']:>3} {step['clause']:30s} {step['rule']} {step['parents']}")
    print(post("/solve/sat", {"num_vars": 3, "clauses": [[1, 2], [-1, 3], [-3]]}))
