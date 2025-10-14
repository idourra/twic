#!/usr/bin/env python
"""Smoke tests para producción.

Uso:
  python scripts/smoke.py --base-url http://localhost:8000 --lang es --query "iphone 13 128gb"
Exit codes:
  0 = OK
  1 = Health FAIL
  2 = Classify FAIL
  3 = Metrics FAIL (si --check-metrics especificado)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from urllib import error, request


def fetch(url: str, timeout: float = 5.0) -> tuple[int, str]:
    req = request.Request(url)
    try:
        with request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as e:  # pragma: no cover - network
        return e.code, e.read().decode("utf-8", errors="replace")
    except (error.URLError, TimeoutError):  # pragma: no cover - network
        return 0, ""


def post_json(url: str, payload: dict, timeout: float = 5.0) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = request.Request(url, data=data, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as e:  # pragma: no cover
        return e.code, e.read().decode("utf-8", errors="replace")
    except (error.URLError, TimeoutError):  # pragma: no cover
        return 0, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--query", default="iphone 13 128gb")
    ap.add_argument("--lang", default="es")
    ap.add_argument("--check-metrics", action="store_true")
    args = ap.parse_args()

    # Health
    code, body = fetch(f"{args.base_url}/health")
    if code != 200:
        print("[FAIL] /health status", code)
        return 1
    try:
        meta = json.loads(body)
    except json.JSONDecodeError:
        print("[FAIL] /health json parse")
        return 1
    if meta.get("status") != "ok":
        print("[FAIL] /health status field != ok")
        return 1
    print("[OK] /health")

    # Classify
    start = time.time()
    c_code, c_body = post_json(
        f"{args.base_url}/classify",
        {"query": args.query, "lang": args.lang, "top_k": 3},
    )
    latency_ms = int((time.time() - start) * 1000)
    if c_code != 200:
        print("[FAIL] /classify status", c_code)
        return 2
    try:
        c_json = json.loads(c_body)
    except json.JSONDecodeError:
        print("[FAIL] /classify json parse")
        return 2
    if "abstained" not in c_json:
        print("[FAIL] /classify missing abstained field")
        return 2
    print(f"[OK] /classify latency={latency_ms}ms abstained={c_json['abstained']}")

    if args.check_metrics:
        m_code, m_body = fetch(f"{args.base_url}/metrics")
        if m_code != 200:
            print("[FAIL] /metrics status", m_code)
            return 3
        # quick presence checks
        if "twic_request_latency_seconds" not in m_body:
            print("[FAIL] metrics missing latency histogram")
            return 3
        print("[OK] /metrics")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
