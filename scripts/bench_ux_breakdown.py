#!/usr/bin/env python3
"""
End-to-end UX timing breakdown against a live backend (e.g. Railway).

Measures wall-clock (client) vs server timing_ms where available:
  health (cold/warm) → /session → /predict → /search

Usage:
  python scripts/bench_ux_breakdown.py \\
    --api-url https://bagfinder-production.up.railway.app \\
    --image frontend/public/onboarding/3.jpg

  # After Railway has been idle (sleep), first health ≈ cold start:
  python scripts/bench_ux_breakdown.py --api-url ... --image ... --probe-cold
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests


def client_ms(fn) -> tuple[float, object]:
    t0 = time.perf_counter()
    out = fn()
    return (time.perf_counter() - t0) * 1000.0, out


def net_overhead(client: float, server: float | None) -> float | None:
    if server is None:
        return None
    return round(max(0.0, client - server), 2)


def main() -> int:
    p = argparse.ArgumentParser(description="UX timing breakdown (session/predict/search)")
    p.add_argument("--api-url", required=True)
    p.add_argument("--image", required=True)
    p.add_argument(
        "--probe-cold",
        action="store_true",
        help="Treat first /health as cold (run after Railway idle/sleep)",
    )
    p.add_argument("--timeout", type=int, default=300)
    args = p.parse_args()

    api = args.api_url.rstrip("/")
    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"Image not found: {image_path}", file=sys.stderr)
        return 1

    summary: dict = {"api": api, "image": str(image_path)}

    # ── health ──────────────────────────────────────────────────────────────
    def get_health():
        r = requests.get(f"{api}/health", timeout=args.timeout)
        r.raise_for_status()
        return r.json()

    if args.probe_cold:
        cold_ms, cold_body = client_ms(get_health)
        summary["health_cold"] = {
            "client_ms": round(cold_ms, 2),
            "body": cold_body,
            "note": "first /health after idle; includes Railway wake if slept",
        }
        print(f"[health cold] client={cold_ms:.1f}ms body={cold_body}")

    warm_ms, warm_body = client_ms(get_health)
    summary["health_warm"] = {
        "client_ms": round(warm_ms, 2),
        "body": warm_body,
    }
    print(f"[health warm] client={warm_ms:.1f}ms body={warm_body}")

    # ── session (upload + SAM encode) ───────────────────────────────────────
    def create_session():
        with image_path.open("rb") as f:
            r = requests.post(
                f"{api}/session",
                files={"file": (image_path.name, f, "image/jpeg")},
                timeout=args.timeout,
            )
        r.raise_for_status()
        return r.json()

    sess_ms, sess = client_ms(create_session)
    sess_server = (sess.get("timing_ms") or {}).get("encode")
    summary["session"] = {
        "client_ms": round(sess_ms, 2),
        "server_encode_ms": sess_server,
        "network_overhead_ms": net_overhead(sess_ms, sess_server),
        "session_id": sess.get("session_id"),
        "image_info": sess.get("image_info"),
    }
    print(
        f"[session] client={sess_ms:.1f}ms server_encode={sess_server} "
        f"net~={summary['session']['network_overhead_ms']}"
    )

    info = sess["image_info"]
    point = [[float(info["width"]) * 0.5, float(info["height"]) * 0.5]]

    # ── predict (cached decode) ─────────────────────────────────────────────
    def predict():
        r = requests.post(
            f"{api}/predict",
            json={
                "session_id": sess["session_id"],
                "points": point,
                "labels": [1],
                "reuse_embedding": True,
            },
            timeout=args.timeout,
        )
        r.raise_for_status()
        return r.json()

    pred_ms, pred = client_ms(predict)
    pt = pred.get("timing_ms") or {}
    pred_server = pt.get("total")
    summary["predict"] = {
        "client_ms": round(pred_ms, 2),
        "server_encode_ms": pt.get("encode"),
        "server_decode_ms": pt.get("decode"),
        "server_total_ms": pred_server,
        "network_overhead_ms": net_overhead(pred_ms, pred_server),
        "iou": pred.get("iou"),
    }
    print(
        f"[predict] client={pred_ms:.1f}ms server_total={pred_server} "
        f"encode={pt.get('encode')} decode={pt.get('decode')} "
        f"net~={summary['predict']['network_overhead_ms']}"
    )

    # ── search (CLIP + vector + meta) ───────────────────────────────────────
    def search():
        r = requests.post(
            f"{api}/search",
            json={"session_id": sess["session_id"], "selected_colors": []},
            timeout=args.timeout,
        )
        r.raise_for_status()
        return r.json()

    search_ms, search_body = client_ms(search)
    st = search_body.get("timing_ms") or {}
    search_server = st.get("total")
    summary["search"] = {
        "client_ms": round(search_ms, 2),
        "server_preprocess_ms": st.get("preprocess"),
        "server_clip_ms": st.get("clip"),
        "server_vector_ms": st.get("vector"),
        "server_meta_ms": st.get("meta"),
        "server_total_ms": search_server,
        "network_overhead_ms": net_overhead(search_ms, search_server),
        "top5_count": len(search_body.get("top5") or []),
        "note": None
        if st
        else "timing_ms missing — deploy backend with /search timing first",
    }
    print(
        f"[search] client={search_ms:.1f}ms server_total={search_server} "
        f"clip={st.get('clip')} vector={st.get('vector')} "
        f"net~={summary['search']['network_overhead_ms']}"
    )

    # ── totals ──────────────────────────────────────────────────────────────
    pieces = [
        ("session", summary["session"]["client_ms"]),
        ("predict", summary["predict"]["client_ms"]),
        ("search", summary["search"]["client_ms"]),
    ]
    ux_total = sum(v for _, v in pieces)
    summary["ux_click_to_results_ms"] = round(ux_total, 2)
    summary["ux_breakdown_pct"] = {
        k: round(100.0 * v / ux_total, 1) if ux_total else 0.0 for k, v in pieces
    }
    if args.probe_cold:
        summary["ux_including_cold_health_ms"] = round(
            summary["health_cold"]["client_ms"] + ux_total, 2
        )

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(
        f"\nUX (session+predict+search) ~ {ux_total:.0f}ms | "
        f"share={summary['ux_breakdown_pct']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
