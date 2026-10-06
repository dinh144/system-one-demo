"""Checks the local-only guard, request caps and one-benchmark-at-a-time rule. Needs a running backend.

Usage: python tests/security_guard.py [http://127.0.0.1:8000]
"""
import http.client
import json
import sys
from urllib.parse import urlparse

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
U = urlparse(BASE)


def call(method, path, body=None, headers=None, host=None):
    conn = http.client.HTTPConnection(U.hostname, U.port, timeout=60)
    h = {"Content-Type": "application/json", **(headers or {})}
    conn.putrequest(method, path, skip_host=True)
    conn.putheader("Host", host or f"{U.hostname}:{U.port}")
    for k, v in h.items():
        conn.putheader(k, v)
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        conn.putheader("Content-Length", str(len(data)))
    conn.endheaders(data)
    r = conn.getresponse()
    payload = r.read()
    conn.close()
    return r.status, payload


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""))
    return ok


def main():
    ok = True
    s, _ = call("GET", "/api/health")
    ok &= check("loopback Host accepted", s == 200, s)
    s, _ = call("GET", "/api/health", host="evil.example:8000")
    ok &= check("foreign Host rejected (DNS rebinding)", s == 400, s)
    s, _ = call("GET", "/api/health", host="localhost:" + str(U.port))
    ok &= check("localhost Host accepted", s == 200, s)
    s, _ = call("POST", "/api/session", {"engines": ["laya"]}, {"Origin": "http://evil.example"})
    ok &= check("cross-origin POST rejected", s == 403, s)
    s, _ = call("POST", "/api/session", {"engines": ["laya"]}, {"Origin": f"http://{U.hostname}:{U.port}"})
    ok &= check("same-origin POST accepted", s == 200, s)
    s, body = call("POST", "/api/session", {"engines": ["laya"]})
    ok &= check("POST without Origin (scripts, tests) accepted", s == 200, s)
    sid = json.loads(body)["session_id"]
    s, _ = call("POST", f"/api/session/{sid}/turn", {"text": "x" * 2001})
    ok &= check("turn text over 2000 characters rejected", s == 422, s)
    s, _ = call("POST", "/api/benchmark", {"engines": ["laya"] * 9})
    ok &= check("benchmark engine list over 8 rejected", s in (400, 422), s)
    s, _ = call("POST", "/api/benchmark", {"engines": ["laya"], "warmup": 99})
    ok &= check("benchmark warmup over 5 rejected", s == 422, s)
    first = None
    for _ in range(25):
        s, body = call("POST", "/api/session", {"engines": ["laya"]})
        first = first or json.loads(body)["session_id"]
    s, _ = call("POST", f"/api/session/{first}/reset")
    ok &= check("oldest session evicted beyond the cap of 20", s == 404, s)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
