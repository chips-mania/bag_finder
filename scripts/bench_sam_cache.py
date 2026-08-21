#!/usr/bin/env python3
"""
SAM encode cache before/after benchmark.

After (reuse_embedding=True):  /session encode 1회 + /predict decode만
Before (reuse_embedding=False): /predict마다 encode+decode

Usage:
  python scripts/bench_sam_cache.py --api-url https://YOUR.up.railway.app --image path/to.jpg --runs 1
  python scripts/bench_sam_cache.py --api-url https://YOUR.up.railway.app --image path/to.jpg --runs 10 --warmup 1
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import requests


def mean(xs: list[float]) -> float:
    return statistics.mean(xs) if xs else 0.0


def create_session(api: str, image_path: Path) -> dict:
    with image_path.open("rb") as f:
        r = requests.post(
            f"{api}/session",
            files={"file": (image_path.name, f, "image/jpeg")},
            timeout=300,
        )
    r.raise_for_status()
    return r.json()


def predict(
    api: str,
    session_id: str,
    points: list[list[float]],
    labels: list[int],
    reuse_embedding: bool,
) -> dict:
    r = requests.post(
        f"{api}/predict",
        json={
            "session_id": session_id,
            "points": points,
            "labels": labels,
            "reuse_embedding": reuse_embedding,
        },
        timeout=300,
    )
    r.raise_for_status()
    return r.json()


def click_point(session: dict) -> list[list[float]]:
    info = session["image_info"]
    w = float(info["width"])
    h = float(info["height"])
    # 이미지 중앙 클릭 (가방이 중앙에 있다고 가정)
    return [[w * 0.5, h * 0.5]]


def run_mode(
    api: str,
    image_path: Path,
    runs: int,
    reuse: bool,
    label: str,
) -> dict:
    session_encodes: list[float] = []
    predict_encodes: list[float] = []
    predict_decodes: list[float] = []
    predict_totals: list[float] = []

    for i in range(runs):
        sess = create_session(api, image_path)
        te = (sess.get("timing_ms") or {}).get("encode")
        if te is not None:
            session_encodes.append(float(te))

        pts = click_point(sess)
        pred = predict(api, sess["session_id"], pts, [1], reuse_embedding=reuse)
        tm = pred.get("timing_ms") or {}
        predict_encodes.append(float(tm.get("encode", 0.0)))
        predict_decodes.append(float(tm.get("decode", 0.0)))
        predict_totals.append(float(tm.get("total", 0.0)))
        print(
            f"[{label}] run {i + 1}/{runs} "
            f"session_encode={te} "
            f"predict_encode={tm.get('encode')} "
            f"predict_decode={tm.get('decode')} "
            f"predict_total={tm.get('total')}"
        )

    return {
        "label": label,
        "reuse_embedding": reuse,
        "runs": runs,
        "session_encode_ms_avg": round(mean(session_encodes), 2),
        "predict_encode_ms_avg": round(mean(predict_encodes), 2),
        "predict_decode_ms_avg": round(mean(predict_decodes), 2),
        "predict_total_ms_avg": round(mean(predict_totals), 2),
        "predict_total_ms_all": [round(x, 2) for x in predict_totals],
        # 클릭 N회 시나리오 (같은 세션에서 N번 클릭했다고 가정):
        # After: session_encode + N * decode
        # Before: session_encode(무시 가능) + N * (encode+decode) ≈ N * predict_total
        "five_clicks_estimate_ms": round(
            (
                mean(session_encodes) + 5 * mean(predict_decodes)
                if reuse
                else 5 * mean(predict_totals)
            ),
            2,
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Benchmark SAM embedding cache")
    p.add_argument("--api-url", required=True, help="Backend base URL (no trailing slash)")
    p.add_argument("--image", required=True, help="Path to a test bag image")
    p.add_argument("--runs", type=int, default=1, help="Measured runs (default 1)")
    p.add_argument("--warmup", type=int, default=0, help="Warmup runs discarded (default 0)")
    args = p.parse_args()

    api = args.api_url.rstrip("/")
    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"Image not found: {image_path}", file=sys.stderr)
        return 1

    health = requests.get(f"{api}/health", timeout=60)
    health.raise_for_status()
    print("health:", health.json())

    for i in range(args.warmup):
        print(f"[warmup] {i + 1}/{args.warmup}")
        sess = create_session(api, image_path)
        predict(api, sess["session_id"], click_point(sess), [1], reuse_embedding=True)

    after = run_mode(api, image_path, args.runs, reuse=True, label="AFTER(cache)")
    before = run_mode(api, image_path, args.runs, reuse=False, label="BEFORE(no-cache)")

    summary = {"after": after, "before": before}
    if after["predict_total_ms_avg"] > 0:
        speedup = before["predict_total_ms_avg"] / after["predict_total_ms_avg"]
        summary["predict_speedup_x"] = round(speedup, 2)
        summary["predict_reduction_pct"] = round(
            (1 - after["predict_total_ms_avg"] / before["predict_total_ms_avg"]) * 100, 1
        )

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
