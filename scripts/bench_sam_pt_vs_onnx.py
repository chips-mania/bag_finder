#!/usr/bin/env python3
"""
MobileSAM Ultralytics (.pt) vs ONNXRuntime benchmark on the same image/click.

Runs locally (same machine) so the comparison is fair.
Railway production stays ONNX-only.

Usage:
  cd bag_finder
  python scripts/bench_sam_pt_vs_onnx.py --image frontend/public/onboarding/3.jpg --runs 1 --warmup 1
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def mean(xs: list[float]) -> float:
    return statistics.mean(xs) if xs else 0.0


def load_rgb(path: Path, max_size: int = 1024) -> Image.Image:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    scale = min(1.0, max_size / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.BILINEAR)
    return img


def bench_pt(img: Image.Image, point: list[float], runs: int, warmup: int) -> dict:
    from ultralytics import SAM

    model = SAM("mobile_sam.pt")  # auto-download if missing
    img_np = np.array(img)
    pts = [point]
    lbs = [1]

    def once() -> float:
        t0 = time.perf_counter()
        _ = model.predict(
            source=img_np,
            points=pts,
            labels=lbs,
            device="cpu",
            save=False,
            show=False,
            verbose=False,
        )
        return (time.perf_counter() - t0) * 1000.0

    for i in range(warmup):
        ms = once()
        print(f"[pt warmup] {i + 1}/{warmup} total={ms:.1f}ms")

    totals: list[float] = []
    for i in range(runs):
        ms = once()
        totals.append(ms)
        print(f"[pt] run {i + 1}/{runs} total={ms:.1f}ms")

    return {
        "backend": "ultralytics_pt_cpu",
        "runs": runs,
        "total_ms_avg": round(mean(totals), 2),
        "total_ms_all": [round(x, 2) for x in totals],
        "note": "each call encodes+decodes (old per-click path)",
    }


def bench_onnx(img: Image.Image, point: list[float], runs: int, warmup: int) -> dict:
    from models.mobile_sam_model import MobileSAMModel

    model = MobileSAMModel(model_path="mobile_sam.pt", device="cpu")

    def once_full() -> tuple[float, float, float]:
        t0 = time.perf_counter()
        emb = model.encode_image(img)
        encode_ms = (time.perf_counter() - t0) * 1000.0
        t1 = time.perf_counter()
        _mask, _iou = model.predict_mask(
            image=img,
            points=[point],
            labels=[1],
            embedding=emb,
        )
        decode_ms = (time.perf_counter() - t1) * 1000.0
        return encode_ms, decode_ms, encode_ms + decode_ms

    for i in range(warmup):
        e, d, tot = once_full()
        print(f"[onnx warmup] {i + 1}/{warmup} encode={e:.1f} decode={d:.1f} total={tot:.1f}ms")

    encodes: list[float] = []
    decodes: list[float] = []
    totals: list[float] = []
    for i in range(runs):
        e, d, tot = once_full()
        encodes.append(e)
        decodes.append(d)
        totals.append(tot)
        print(f"[onnx full] run {i + 1}/{runs} encode={e:.1f} decode={d:.1f} total={tot:.1f}ms")

    # Cached click path: encode once, then decode-only (production UX after /session)
    emb = model.encode_image(img)
    cached: list[float] = []
    for i in range(runs):
        t0 = time.perf_counter()
        _mask, _iou = model.predict_mask(
            image=img,
            points=[point],
            labels=[1],
            embedding=emb,
        )
        ms = (time.perf_counter() - t0) * 1000.0
        cached.append(ms)
        print(f"[onnx cached] run {i + 1}/{runs} decode={ms:.1f}ms")

    return {
        "backend": "onnxruntime_cpu",
        "runs": runs,
        "encode_ms_avg": round(mean(encodes), 2),
        "decode_ms_avg": round(mean(decodes), 2),
        "total_ms_avg": round(mean(totals), 2),
        "total_ms_all": [round(x, 2) for x in totals],
        "cached_click_ms_avg": round(mean(cached), 2),
        "cached_click_ms_all": [round(x, 2) for x in cached],
        "note": "full=encode+decode; cached=decode only (after session encode)",
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Benchmark MobileSAM .pt vs ONNX")
    p.add_argument("--image", required=True)
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--warmup", type=int, default=1)
    p.add_argument("--max-size", type=int, default=1024)
    p.add_argument("--skip-pt", action="store_true")
    p.add_argument("--skip-onnx", action="store_true")
    args = p.parse_args()

    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"Image not found: {image_path}", file=sys.stderr)
        return 1

    img = load_rgb(image_path, max_size=args.max_size)
    w, h = img.size
    point = [w * 0.5, h * 0.5]
    print(f"image={image_path} size={w}x{h} click={point}")

    summary: dict = {"image": str(image_path), "size": [w, h], "click": point}

    if not args.skip_pt:
        summary["pt"] = bench_pt(img, point, args.runs, args.warmup)
    if not args.skip_onnx:
        summary["onnx"] = bench_onnx(img, point, args.runs, args.warmup)

    if "pt" in summary and "onnx" in summary:
        pt_t = summary["pt"]["total_ms_avg"]
        onnx_full = summary["onnx"]["total_ms_avg"]
        onnx_cached = summary["onnx"].get("cached_click_ms_avg")
        if onnx_full > 0:
            summary["speedup_full_x"] = round(pt_t / onnx_full, 2)
            summary["reduction_full_pct"] = round((1 - onnx_full / pt_t) * 100, 1)
        if onnx_cached and onnx_cached > 0:
            summary["speedup_cached_click_x"] = round(pt_t / onnx_cached, 2)
            summary["reduction_cached_click_pct"] = round((1 - onnx_cached / pt_t) * 100, 1)

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
