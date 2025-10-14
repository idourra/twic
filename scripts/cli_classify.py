#!/usr/bin/env python3
"""Batch classify utility.

Reads newline-delimited queries (plain text or JSONL with a 'query' field) and outputs JSONL
with prediction / alternatives.

Usage:
  python scripts/cli_classify.py --input queries.txt --output results.jsonl \
      --url http://localhost:8000 --lang es --top-k 5

Features:
- Auto-detect JSONL vs plain text.
- Concurrency via asyncio + httpx.
- Rate pacing (--max-rps) to avoid tripping rate limiter.
- Retries with exponential backoff on 429/5xx.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

DEFAULT_TIMEOUT = 15.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch classify queries against the API")
    p.add_argument("--input", required=True, help="Input file: .txt (one query per line) or JSONL")
    p.add_argument("--output", required=True, help="Output JSONL file path")
    p.add_argument("--url", default="http://localhost:8000", help="Base URL of service")
    p.add_argument("--lang", default="es", help="Language code")
    p.add_argument("--top-k", type=int, default=5, dest="top_k", help="Alternatives top-k for API")
    p.add_argument("--concurrency", type=int, default=10, help="Max in-flight requests")
    p.add_argument(
        "--max-rps",
        type=float,
        default=0,
        help="Max requests per second (0 = unlimited)",
    )
    p.add_argument("--retries", type=int, default=3, help="Retry attempts on transient errors")
    return p.parse_args()


def load_queries(path: Path) -> list[str]:
    queries: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        first = f.readline()
        if not first:
            return []
        is_jsonl = False
        try:
            json.loads(first)
            is_jsonl = True
        except Exception:
            queries.append(first.strip())
        if is_jsonl:
            # Rewind to start to process uniformly
            f.seek(0)
            for line in f:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    q = obj.get("query")
                    if q:
                        queries.append(str(q))
                except Exception:
                    continue
        else:
            for line in f:
                if not line.strip():
                    continue
                queries.append(line.strip())
    return queries


async def worker(
    name: int,
    queue: asyncio.Queue[str],
    client: httpx.AsyncClient,
    args: argparse.Namespace,
    out_f,
):
    backoff_base = 0.3
    while True:
        try:
            q = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        attempt = 0
        while True:
            try:
                resp = await client.post(
                    f"{args.url}/classify",
                    json={"query": q, "lang": args.lang, "top_k": args.top_k},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    out = {"query": q, **data}
                    out_f.write(json.dumps(out, ensure_ascii=False) + "\n")
                    out_f.flush()
                    break
                if resp.status_code in (429, 500, 503) and attempt < args.retries:
                    await asyncio.sleep(backoff_base * (2 ** attempt))
                    attempt += 1
                    continue
                out_f.write(
                    json.dumps(
                        {"query": q, "error": resp.status_code, "detail": resp.text}
                    )
                    + "\n"
                )
                out_f.flush()
                break
            except Exception as e:  # network or JSON error
                if attempt < args.retries:
                    await asyncio.sleep(backoff_base * (2 ** attempt))
                    attempt += 1
                    continue
                out_f.write(json.dumps({"query": q, "error": "exception", "detail": str(e)}) + "\n")
                out_f.flush()
                break
        if args.max_rps > 0:
            await asyncio.sleep(1.0 / args.max_rps)


def main():
    args = parse_args()
    queries = load_queries(Path(args.input))
    if not queries:
        print("No queries loaded", file=sys.stderr)
        return 1
    start = time.time()
    queue: asyncio.Queue[str] = asyncio.Queue()
    for q in queries:
        queue.put_nowait(q)
    concurrency = max(1, args.concurrency)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as out_f:
        async def run():
            limits = httpx.Limits(
                max_keepalive_connections=concurrency, max_connections=concurrency
            )
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, limits=limits) as client:
                tasks = [
                    asyncio.create_task(worker(i, queue, client, args, out_f))
                    for i in range(concurrency)
                ]
                await asyncio.gather(*tasks)
        asyncio.run(run())
    dur = time.time() - start
    print(f"Processed {len(queries)} queries in {dur:.2f}s ({len(queries)/dur:.2f} QPS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
