import os
import logging
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image
from ultralytics import SAM

logger = logging.getLogger(__name__)

class MobileSAMModel:
    """
    Ultralytics 기반 Mobile SAM 래퍼.
    - ONNX 사용 X, PyTorch 가중치(.pt) 직접 로드
    - set_image(), 임베딩 추출 X
    - 항상 predict(image, points, labels)로 마스크 생성
    """

    def __init__(self, model_path: str, device: str = "cpu"):
        self.model_path = model_path
        self.device = device
        self.model: Optional[SAM] = None
        self._load_model()

    def _load_model(self) -> None:
        try:
            # Local path if present; otherwise bare name so Ultralytics auto-downloads
            # official assets (e.g. mobile_sam.pt) on first startup.
            weight = self.model_path
            if not os.path.exists(weight):
                weight = os.path.basename(weight) or "mobile_sam.pt"
                logger.info(
                    "Local weights not found at %s; Ultralytics will download %s",
                    self.model_path,
                    weight,
                )
            self.model = SAM(weight)
            # Ultralytics prefers device via predict(...); keep path for logging
            logger.info(f"MobileSAM loaded: {weight} (device={self.device})")
        except Exception as e:
            logger.exception("Failed to load MobileSAM")
            raise

    @staticmethod
    def _pil_to_numpy_rgb(image: Image.Image) -> np.ndarray:
        """PIL -> numpy RGB(H,W,3)"""
        if image.mode != "RGB":
            image = image.convert("RGB")
        arr = np.array(image)  # uint8 HWC
        return arr

    @staticmethod
    def _normalize_prompts(points, labels) -> Tuple[List[List[float]], List[int]]:
        """Flatten to [[x, y], ...] and [1, 0, ...]."""
        pts = points
        lbs = labels
        if isinstance(pts, list) and pts:
            first = pts[0]
            # [[[x, y], ...]] -> [[x, y], ...]
            if isinstance(first, (list, tuple)) and first and isinstance(first[0], (list, tuple)):
                pts = first
                if isinstance(lbs, list) and lbs and isinstance(lbs[0], (list, tuple)):
                    lbs = lbs[0]
        if not isinstance(pts, list) or not pts:
            raise ValueError("points must be a non-empty list of [x, y]")
        flat_pts: List[List[float]] = [[float(p[0]), float(p[1])] for p in pts]
        if isinstance(lbs, list) and lbs and isinstance(lbs[0], (list, tuple)):
            lbs = lbs[0]
        if not isinstance(lbs, list):
            lbs = [int(lbs)] * len(flat_pts)
        flat_lbs = [int(v) for v in lbs]
        if len(flat_lbs) != len(flat_pts):
            raise ValueError(f"points/labels length mismatch: {len(flat_pts)} vs {len(flat_lbs)}")
        return flat_pts, flat_lbs

    def predict_mask(
        self,
        image: Image.Image,
        points: List[List[int]] | List[List[float]] | List[List[List[float]]],
        labels: List[int] | List[List[int]],
        multimask_output: bool = False,
    ) -> Tuple[np.ndarray, Optional[float]]:
        """
        image: PIL.Image (원본/리사이즈 모두 OK)
        points: [[x,y], [x,y], ...] 또는 [[[x,y], [x,y], ...]] (Ultralytics가 둘 다 지원)
        labels: [1,0,...] 또는 [[1,0,...]] (1=foreground, 0=background)
        return: (mask, iou)  where mask shape is (H, W) uint8 (0/1)
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        img_np = self._pil_to_numpy_rgb(image)

        try:
            # Ultralytics SAM expects points (N, 2) and labels (N,).
            # Extra wrapping to (1, N, 2) makes internals 4D vs 3D.
            pts, lbs = self._normalize_prompts(points, labels)
            logger.info(
                "SAM.predict inputs -> n_points=%s labels=%s",
                len(pts),
                lbs,
            )
            results = self.model.predict(
                source=img_np,
                points=pts,
                labels=lbs,
                device=self.device,
                save=False,
                show=False,
                verbose=False,
            )

            if not results:
                return np.zeros((image.height, image.width), dtype=np.uint8), None

            r = results[0]

            # 마스크 추출: 다중 마스크가 올 수도 있으므로 첫 마스크 사용(필요시 선택 로직 추가)
            if r.masks is None or len(r.masks) == 0:
                return np.zeros((image.height, image.width), dtype=np.uint8), None

            # r.masks.data: (N, H, W) float tensor
            m = r.masks.data[0].cpu().numpy()  # 첫 번째 마스크
            mask_bin = (m > 0).astype(np.uint8)  # 0/1 이진 마스크

            # 마스크 크기가 입력 이미지와 다른 경우 리사이즈
            if mask_bin.shape != (image.height, image.width):
                logger.warning(f"Mask size {mask_bin.shape} != image size {(image.height, image.width)}, resizing...")
                from PIL import Image as PILImage
                mask_pil = PILImage.fromarray(mask_bin)
                mask_pil = mask_pil.resize((image.width, image.height), PILImage.NEAREST)
                mask_bin = np.array(mask_pil)

            # 품질 점수(IOU 예측치)가 있을 수도/없을 수도 있어 방어적으로 처리
            iou = None
            if getattr(r, "probs", None) is not None and getattr(r.probs, "data", None) is not None:
                try:
                    iou = float(r.probs.data[0])
                except Exception:
                    iou = None

            return mask_bin, iou

        except Exception as e:
            logger.exception("Failed to predict mask")
            # 호출부에서 500 처리하도록 예외 전파
            raise
