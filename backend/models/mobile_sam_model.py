import logging
import os
import threading
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from PIL import Image

logger = logging.getLogger(__name__)

PIXEL_MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float32)
PIXEL_STD = np.array([58.395, 57.12, 57.375], dtype=np.float32)
HF_REPO = "vietanhdev/segment-anything-onnx-models"
HF_ZIP = "mobile_sam_20230629.zip"


class MobileSAMModel:
    """ONNX MobileSAM: encode image once, decode masks from click prompts."""

    def __init__(self, model_path: str = "", device: str = "cpu"):
        self.model_path = model_path
        self.device = device
        self.target_size = 1024
        self._lock = threading.Lock()
        self.encoder_session: Optional[ort.InferenceSession] = None
        self.decoder_session: Optional[ort.InferenceSession] = None
        self.encoder_input_name = "input_image"
        self._load_model()

    def _load_model(self) -> None:
        encoder_path, decoder_path = self._ensure_onnx_files()
        providers = [p for p in ort.get_available_providers() if p != "TensorrtExecutionProvider"]
        if "CPUExecutionProvider" not in providers:
            providers.append("CPUExecutionProvider")
        so = ort.SessionOptions()
        so.intra_op_num_threads = int(os.getenv("ORT_INTRA_OP_THREADS", "4"))
        self.encoder_session = ort.InferenceSession(encoder_path, sess_options=so, providers=providers)
        self.decoder_session = ort.InferenceSession(decoder_path, sess_options=so, providers=providers)
        self.encoder_input_name = self.encoder_session.get_inputs()[0].name
        enc_in = self.encoder_session.get_inputs()[0]
        dec_ins = [(i.name, i.shape) for i in self.decoder_session.get_inputs()]
        logger.info("MobileSAM ONNX encoder input: %s %s", enc_in.name, enc_in.shape)
        logger.info("MobileSAM ONNX decoder inputs: %s", dec_ins)
        logger.info("MobileSAM ONNX loaded (device=%s providers=%s)", self.device, providers)

    def _ensure_onnx_files(self) -> Tuple[str, str]:
        cache_dir = Path(os.getenv("MODEL_DIR", "models")) / "mobile_sam_onnx"
        cache_dir.mkdir(parents=True, exist_ok=True)
        encoder = self._find_onnx(cache_dir, "encoder")
        decoder = self._find_onnx(cache_dir, "decoder")
        if encoder and decoder:
            return str(encoder), str(decoder)

        logger.info("Downloading MobileSAM ONNX from Hugging Face (%s)", HF_ZIP)
        zip_path = hf_hub_download(repo_id=HF_REPO, filename=HF_ZIP)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(cache_dir)
        encoder = self._find_onnx(cache_dir, "encoder")
        decoder = self._find_onnx(cache_dir, "decoder")
        if not encoder or not decoder:
            raise FileNotFoundError(f"ONNX encoder/decoder not found under {cache_dir}")
        return str(encoder), str(decoder)

    @staticmethod
    def _find_onnx(root: Path, kind: str) -> Optional[Path]:
        matches = sorted(root.rglob(f"*{kind}*.onnx"))
        return matches[0] if matches else None

    @staticmethod
    def get_preprocess_shape(oldh: int, oldw: int, long_side_length: int) -> Tuple[int, int]:
        scale = long_side_length * 1.0 / max(oldh, oldw)
        newh = int(oldh * scale + 0.5)
        neww = int(oldw * scale + 0.5)
        return newh, neww

    def _preprocess_nchw(self, rgb: np.ndarray) -> np.ndarray:
        h, w = rgb.shape[:2]
        new_h, new_w = self.get_preprocess_shape(h, w, self.target_size)
        im = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        x = (im.astype(np.float32) - PIXEL_MEAN) / PIXEL_STD
        pad_h = self.target_size - new_h
        pad_w = self.target_size - new_w
        x = np.pad(x, ((0, pad_h), (0, pad_w), (0, 0)))
        return x.transpose(2, 0, 1)[None].astype(np.float32)

    def encode_image(self, image: Image.Image) -> Dict[str, Any]:
        if self.encoder_session is None:
            raise RuntimeError("Model not loaded")
        rgb = np.array(image.convert("RGB"))
        h, w = rgb.shape[:2]
        tensor = self._preprocess_nchw(rgb)
        inp = self.encoder_session.get_inputs()[0]
        shape = list(inp.shape)
        if len(shape) == 3 or (len(shape) == 4 and shape[-1] == 3):
            hwc = cv2.resize(rgb, (self.target_size, self.target_size), interpolation=cv2.INTER_LINEAR)
            arr = hwc.astype(np.float32)
            feed = {self.encoder_input_name: np.expand_dims(arr, 0) if len(shape) == 4 else arr}
        else:
            feed = {self.encoder_input_name: tensor}
        with self._lock:
            embedding = self.encoder_session.run(None, feed)[0]
        logger.info("SAM encoder done: image=%sx%s embedding=%s", w, h, getattr(embedding, "shape", None))
        return {
            "image_embedding": embedding,
            "original_size": (h, w),
        }

    def apply_coords(self, coords: np.ndarray, original_size: Tuple[int, int]) -> np.ndarray:
        old_h, old_w = original_size
        new_h, new_w = self.get_preprocess_shape(old_h, old_w, self.target_size)
        coords = deepcopy(coords).astype(np.float32)
        coords[..., 0] *= new_w / old_w
        coords[..., 1] *= new_h / old_h
        return coords

    def predict_from_embedding(
        self,
        embedding: Dict[str, Any],
        points: List[List[float]],
        labels: List[int],
    ) -> Tuple[np.ndarray, Optional[float]]:
        if self.decoder_session is None:
            raise RuntimeError("Model not loaded")
        pts, lbs = self._normalize_prompts(points, labels)
        original_size = tuple(embedding["original_size"])
        image_embedding = embedding["image_embedding"]

        input_points = np.array(pts, dtype=np.float32)
        input_labels = np.array(lbs, dtype=np.float32)
        onnx_coord = np.concatenate([input_points, np.array([[0.0, 0.0]], dtype=np.float32)], axis=0)[None, :, :]
        onnx_label = np.concatenate([input_labels, np.array([-1], dtype=np.float32)], axis=0)[None, :]
        onnx_coord = self.apply_coords(onnx_coord, original_size)

        decoder_inputs = {
            "image_embeddings": image_embedding,
            "point_coords": onnx_coord.astype(np.float32),
            "point_labels": onnx_label.astype(np.float32),
            "mask_input": np.zeros((1, 1, 256, 256), dtype=np.float32),
            "has_mask_input": np.zeros(1, dtype=np.float32),
            "orig_im_size": np.array(original_size, dtype=np.float32),
        }
        names = {i.name for i in self.decoder_session.get_inputs()}
        feed = {k: v for k, v in decoder_inputs.items() if k in names}
        with self._lock:
            masks, iou_preds, *_rest = self.decoder_session.run(None, feed)

        # masks: (1, K, H, W) logits
        iou = None
        mask_idx = 0
        try:
            iou_arr = np.array(iou_preds).reshape(-1)
            mask_idx = int(np.argmax(iou_arr))
            iou = float(iou_arr[mask_idx])
        except Exception:
            pass
        m = np.array(masks)
        if m.ndim == 4:
            mask_bin = (m[0, mask_idx] > 0).astype(np.uint8)
        elif m.ndim == 3:
            mask_bin = (m[0] > 0).astype(np.uint8)
        else:
            mask_bin = (m > 0).astype(np.uint8)

        orig_h, orig_w = int(original_size[0]), int(original_size[1])
        if mask_bin.shape != (orig_h, orig_w):
            mask_bin = cv2.resize(mask_bin, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
        return mask_bin, iou

    def predict_mask(
        self,
        image: Image.Image,
        points: List[List[int]] | List[List[float]] | List[List[List[float]]],
        labels: List[int] | List[List[int]],
        multimask_output: bool = False,
        embedding: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Optional[float]]:
        if embedding is None:
            embedding = self.encode_image(image)
        return self.predict_from_embedding(embedding, points, labels)  # type: ignore[arg-type]

    @staticmethod
    def _normalize_prompts(points, labels) -> Tuple[List[List[float]], List[int]]:
        pts = points
        lbs = labels
        if isinstance(pts, list) and pts:
            first = pts[0]
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
