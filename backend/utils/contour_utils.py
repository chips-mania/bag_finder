# utils/contour_utils.py
"""
컨투어 추출/단순화 유틸리티 (AnyLabeling 스타일)
- 이진화: > 0 → 전경(255)
- 컨투어: RETR_EXTERNAL + CHAIN_APPROX_NONE
- 단순화: epsilon = 0.001 * arcLength (아주 미세)
- 필터: (컨투어 2개 이상) 이미지 90% 초과 제거 → 평균의 20% 미만 제거
- 입력 차원/타입 정규화 유지
"""
from typing import List, Literal
import numpy as np
import cv2

RetrMode = Literal["external", "tree", "list", "ccomp"]

def _normalize_mask_2d(mask: np.ndarray) -> np.ndarray:
    if mask is None:
        raise ValueError("mask is None")
    arr = np.asarray(mask)
    while arr.ndim > 2 and (arr.shape[0] == 1 or arr.shape[-1] == 1):
        arr = np.squeeze(arr, axis=0 if arr.shape[0] == 1 else -1)
    if arr.ndim != 2:
        raise ValueError(f"Expected 2D mask after squeeze, got shape={arr.shape}")
    return arr

def _binarize_like_anylabeling(mask_2d: np.ndarray) -> np.ndarray:
    m = mask_2d
    if np.issubdtype(m.dtype, np.floating):
        return (m > 0.0).astype(np.uint8) * 255
    if m.dtype == bool:
        return (m.astype(np.uint8)) * 255
    return (m > 0).astype(np.uint8) * 255

def _cv_retr_mode(mode: RetrMode) -> int:
    return {
        "external": cv2.RETR_EXTERNAL,
        "tree": cv2.RETR_TREE,
        "list": cv2.RETR_LIST,
        "ccomp": cv2.RETR_CCOMP,
    }.get(mode, cv2.RETR_EXTERNAL)

def extract_contours(
    mask: np.ndarray,
    *,
    retr_mode: RetrMode = "external",            # AnyLabeling: 외곽선만
    chain_approx: int = cv2.CHAIN_APPROX_NONE,   # AnyLabeling: 점 폐기 없음
    apply_area_filters: bool = True,             # AnyLabeling식 면적 필터
) -> List[List[List[float]]]:
    m2d = _normalize_mask_2d(mask)
    mask_u8 = _binarize_like_anylabeling(m2d)

    contours, _ = cv2.findContours(mask_u8, _cv_retr_mode(retr_mode), chain_approx)

    polys: List[List[List[float]]] = []
    for cnt in contours:
        if cnt.ndim == 3 and cnt.shape[1] == 1 and cnt.shape[2] == 2:
            pts = cnt.reshape(-1, 2)
        elif cnt.ndim == 2 and cnt.shape[1] == 2:
            pts = cnt
        else:
            continue
        if pts.shape[0] >= 3:
            polys.append(pts.astype(float).tolist())

    if apply_area_filters and len(polys) > 1:
        h, w = m2d.shape
        image_size = float(h * w)
        areas = [float(cv2.contourArea(np.asarray(p, dtype=np.float32))) for p in polys]
        # 90% 초과 제거
        filtered = [p for p, a in zip(polys, areas) if a < image_size * 0.9]
        if filtered:
            polys = filtered
            areas = [float(cv2.contourArea(np.asarray(p, dtype=np.float32))) for p in polys]
        # 평균의 20% 미만 제거
        if len(polys) > 1 and areas:
            avg_area = float(np.mean(areas))
            polys = [p for p, a in zip(polys, areas) if a > avg_area * 0.2]

    return polys

def simplify_contours(
    contours: List[List[List[float]]],
    *,
    epsilon_factor: float = 0.001,   # AnyLabeling: 매우 작게
) -> List[List[List[float]]]:
    simplified: List[List[List[float]]] = []
    for poly in contours:
        if not poly or len(poly) < 3:
            continue
        arr = np.asarray(poly, dtype=np.float32).reshape(-1, 1, 2)
        perim = float(cv2.arcLength(arr, True))
        eps = perim * float(epsilon_factor)  # 아주 미세하게만 단순화
        approx = cv2.approxPolyDP(arr, eps, True)  # (M,1,2)
        pts = approx.reshape(-1, 2).astype(float).tolist()
        if len(pts) >= 3:
            simplified.append(pts)
    return simplified
