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
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        try:
            self.model = SAM(self.model_path)
            # Ultralytics 모델은 내부적으로 .predict(device=...)에 장치를 넘기는 걸 권장
            # (self.model.to(self.device)도 가능하긴 하나 predict에 device 넘기는게 확실)
            logger.info(f"MobileSAM loaded: {self.model_path} (device={self.device})")
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
            # Normalize prompt shapes: ensure shape is (1, N, 2) and (1, N)
            pts_in = points
            lbs_in = labels
            try:
                if isinstance(pts_in, list) and len(pts_in) > 0:
                    # If first element is a number -> Nx2, wrap to [Nx2]
                    first = pts_in[0]
                    if isinstance(first, (list, tuple)) and len(first) == 2 and all(
                        isinstance(v, (int, float)) for v in first
                    ):
                        # Now check if it's 2D (Nx2) not 3D
                        if not (isinstance(pts_in[0][0], (list, tuple)) and len(pts_in[0][0]) == 2):
                            pts_in = [pts_in]
                            lbs_in = [labels] if isinstance(labels, list) and (len(labels) > 0 and not isinstance(labels[0], list)) else labels
            except Exception:
                # Fail safe: keep original
                pass

            if isinstance(lbs_in, list) and len(lbs_in) > 0 and not isinstance(lbs_in[0], (list, tuple)):
                # Ensure labels nested when points are nested
                if isinstance(pts_in, list) and len(pts_in) > 0 and isinstance(pts_in[0], list) and len(pts_in[0]) > 0 and isinstance(pts_in[0][0], (list, tuple)):
                    lbs_in = [lbs_in]

            logger.info("SAM.predict inputs -> points groups: %s, points per group: %s, labels groups: %s",
                        len(pts_in) if isinstance(pts_in, list) else 'n/a',
                        len(pts_in[0]) if isinstance(pts_in, list) and len(pts_in) > 0 else 'n/a',
                        len(lbs_in) if isinstance(lbs_in, list) else 'n/a')
            # Ultralytics SAM 추론
            results = self.model.predict(
                source=img_np,
                points=pts_in,
                labels=lbs_in,
                device=self.device,
                save=False,
                show=False,
                verbose=False,
                # 이미지 크기를 강제하고 싶다면 imgsz=1024 같은 옵션 사용 가능
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
