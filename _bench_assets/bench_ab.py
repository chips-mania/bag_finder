#!/usr/bin/env python3
"""
SAM + filter-search timing (client wall-clock), N runs after warmup.

Survives checkout: keep under _bench_assets/
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import requests


def mean(xs: list[float]) -> float:
    return statistics.mean(xs) if xs else 0.0


def client_ms(fn):
    t0 = time.perf_counter()
    out = fn()
    return (time.perf_counter() - t0) * 1000.0, out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", required=True)
    p.add_argument("--image", required=True)
    p.add_argument("--label", default="run")
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--out", default="")
    args = p.parse_args()

    api = args.api_url.rstrip("/")
    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"missing image: {image_path}", file=sys.stderr)
        return 1

    def health():
        r = requests.get(f"{api}/health", timeout=args.timeout)
        r.raise_for_status()
        return r.json()

    def create_session():
        with image_path.open("rb") as f:
            r = requests.post(
                f"{api}/session",
                files={"file": (image_path.name, f, "image/jpeg")},
                timeout=args.timeout,
            )
        r.raise_for_status()
        return r.json()

    def predict(session_id: str, points, reuse: bool = True):
        payload = {
            "session_id": session_id,
            "points": points,
            "labels": [1],
        }
        # older API may ignore unknown fields; newer accepts reuse_embedding
        payload["reuse_embedding"] = reuse
        r = requests.post(f"{api}/predict", json=payload, timeout=args.timeout)
        r.raise_for_status()
        return r.json()

    def search(session_id: str):
        r = requests.post(
            f"{api}/search",
            json={"session_id": session_id, "selected_colors": []},
            timeout=args.timeout,
        )
        r.raise_for_status()
        return r.json()

    def filter_sim(session_id: str):
        r = requests.post(
            f"{api}/filter-search-with-similarity",
            json={
                "session_id": session_id,
                "selected_categories": [],
                "selected_colors": [],
                "min_price": 4900,
                "max_price": 1500000,
                "page": 1,
                "limit": 10,
            },
            timeout=args.timeout,
        )
        r.raise_for_status()
        return r.json()

    h_ms, h = client_ms(health)
    print(f"[{args.label}] health {h_ms:.0f}ms {h}")

    # ── SAM: session + predict per run ──────────────────────────────────────
    def sam_once():
        s_ms, sess = client_ms(create_session)
        info = sess["image_info"]
        pts = [[float(info["width"]) * 0.5, float(info["height"]) * 0.5]]
        p_ms, pred = client_ms(lambda: predict(sess["session_id"], pts, reuse=True))
        return {
            "session_client_ms": round(s_ms, 2),
            "session_server_encode_ms": (sess.get("timing_ms") or {}).get("encode"),
            "predict_client_ms": round(p_ms, 2),
            "predict_server": pred.get("timing_ms"),
            "total_client_ms": round(s_ms + p_ms, 2),
        }

    for i in range(args.warmup):
        print(f"[{args.label}] SAM warmup {i+1}/{args.warmup}")
        print(" ", sam_once())

    sam_rows = []
    for i in range(args.runs):
        row = sam_once()
        sam_rows.append(row)
        print(f"[{args.label}] SAM run {i+1}/{args.runs} {row}")

    # ── Filter: one setup, then N filter calls ──────────────────────────────
    print(f"[{args.label}] filter setup (session+predict+search)...")
    setup_ms, sess = client_ms(create_session)
    info = sess["image_info"]
    pts = [[float(info["width"]) * 0.5, float(info["height"]) * 0.5]]
    _, _ = client_ms(lambda: predict(sess["session_id"], pts, reuse=True))
    search_ms, _ = client_ms(lambda: search(sess["session_id"]))
    print(f"[{args.label}] setup session={setup_ms:.0f}ms search={search_ms:.0f}ms")

    for i in range(args.warmup):
        f_ms, body = client_ms(lambda: filter_sim(sess["session_id"]))
        n = len(body.get("results") or [])
        print(f"[{args.label}] filter warmup {i+1}/{args.warmup} {f_ms:.0f}ms results={n}")

    filter_rows = []
    for i in range(args.runs):
        f_ms, body = client_ms(lambda: filter_sim(sess["session_id"]))
        row = {
            "client_ms": round(f_ms, 2),
            "result_count": len(body.get("results") or []),
        }
        filter_rows.append(row)
        print(f"[{args.label}] filter run {i+1}/{args.runs} {row}")

    summary = {
        "label": args.label,
        "api": api,
        "image": str(image_path),
        "runs": args.runs,
        "sam": {
            "session_client_ms_avg": round(mean([r["session_client_ms"] for r in sam_rows]), 2),
            "predict_client_ms_avg": round(mean([r["predict_client_ms"] for r in sam_rows]), 2),
            "total_client_ms_avg": round(mean([r["total_client_ms"] for r in sam_rows]), 2),
            "runs": sam_rows,
        },
        "filter": {
            "client_ms_avg": round(mean([r["client_ms"] for r in filter_rows]), 2),
            "setup_search_client_ms": round(search_ms, 2),
            "runs": filter_rows,
        },
    }
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
