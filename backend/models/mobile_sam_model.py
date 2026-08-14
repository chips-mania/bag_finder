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
        self.encoder_hw = (1024, 1024)  # (H, W)
        self.encoder_layout = "nchw"  # nchw | hwc
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
        enc_in = self.encoder_session.get_inputs()[0]
        self.encoder_input_name = enc_in.name
        self.encoder_hw, self.encoder_layout = self._infer_encoder_spec(enc_in.shape)
        dec_ins = [(i.name, list(i.shape), i.type) for i in self.decoder_session.get_inputs()]
        dec_outs = [(o.name, list(o.shape)) for o in self.decoder_session.get_outputs()]
        logger.info(
            "[SAM] encoder file=%s input=%s shape=%s layout=%s canvas_hw=%s",
            encoder_path,
            enc_in.name,
            list(enc_in.shape),
            self.encoder_layout,
            self.encoder_hw,
        )
        logger.info("[SAM] decoder inputs=%s outputs=%s", dec_ins, dec_outs)
        logger.info("[SAM] providers=%s", providers)

    @staticmethod
    def _infer_encoder_spec(shape) -> Tuple[Tuple[int, int], str]:
        dims = [d if isinstance(d, int) and d > 0 else None for d in shape]
        if len(dims) == 4 and dims[-1] == 3:
            h = dims[1] or 1024
            w = dims[2] or 1024
            return (h, w), "hwc"
        if len(dims) == 4:
            h = dims[2] or 1024
            w = dims[3] or 1024
            return (h, w), "nchw"
        if len(dims) == 3 and dims[-1] == 3:
            return (dims[0] or 1024, dims[1] or 1024), "hwc"
        if len(dims) == 3:
            return (dims[1] or 1024, dims[2] or 1024), "nchw"
        return (1024, 1024), "nchw"

    def _ensure_onnx_files(self) -> Tuple[str, str]:
        cache_dir = Path(os.getenv("MODEL_DIR", "models")) / "mobile_sam_onnx"
        cache_dir.mkdir(parents=True, exist_ok=True)
        encoder = self._find_onnx(cache_dir, "encoder")
        decoder = self._find_onnx(cache_dir, "decoder")
        if encoder and decoder:
            return str(encoder), str(decoder)

        logger.info("[SAM] downloading ONNX zip %s", HF_ZIP)
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

    def _warp_to_encoder(self, rgb: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
        """Uniform scale (no stretch) onto encoder canvas. Returns canvas RGB, 3x3 matrix, scale."""
        orig_h, orig_w = rgb.shape[:2]
        canvas_h, canvas_w = self.encoder_hw
        scale = min(canvas_w / orig_w, canvas_h / orig_h)
        matrix = np.array([[scale, 0.0, 0.0], [0.0, scale, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
        canvas = cv2.warpAffine(
            rgb,
            matrix[:2],
            (canvas_w, canvas_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
        return canvas, matrix, float(scale)

    def encode_image(self, image: Image.Image) -> Dict[str, Any]:
        if self.encoder_session is None:
            raise RuntimeError("Model not loaded")
        rgb = np.array(image.convert("RGB"))
        orig_h, orig_w = rgb.shape[:2]
        canvas, matrix, scale = self._warp_to_encoder(rgb)

        if self.encoder_layout == "hwc":
            # samexporter: warped image as float32; BGR matches cv2.imread exports
            hwc = cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR).astype(np.float32)
            feed_arr = hwc if len(self.encoder_session.get_inputs()[0].shape) == 3 else np.expand_dims(hwc, 0)
        else:
            x = (canvas.astype(np.float32) - PIXEL_MEAN) / PIXEL_STD
            feed_arr = x.transpose(2, 0, 1)[None].astype(np.float32)

        feed = {self.encoder_input_name: feed_arr}
        with self._lock:
            embedding = self.encoder_session.run(None, feed)[0]

        logger.info(
            "[SAM encode] orig_hw=%s canvas_hw=%s scale=%.6f layout=%s feed=%s embed=%s",
            (orig_h, orig_w),
            self.encoder_hw,
            scale,
            self.encoder_layout,
            tuple(feed_arr.shape),
            tuple(embedding.shape),
        )
        return {
            "image_embedding": embedding,
            "original_size": (orig_h, orig_w),
            "transform_matrix": matrix,
            "scale": scale,
        }

    def predict_from_embedding(
        self,
        embedding: Dict[str, Any],
        points: List[List[float]],
        labels: List[int],
    ) -> Tuple[np.ndarray, Optional[float]]:
        if self.decoder_session is None:
            raise RuntimeError("Model not loaded")
        pts, lbs = self._normalize_prompts(points, labels)
        orig_h, orig_w = (int(embedding["original_size"][0]), int(embedding["original_size"][1]))
        image_embedding = embedding["image_embedding"]
        matrix: np.ndarray = embedding["transform_matrix"]
        scale = float(embedding.get("scale", matrix[0, 0]))
        canvas_h, canvas_w = self.encoder_hw

        input_points = np.array(pts, dtype=np.float32)
        input_labels = np.array(lbs, dtype=np.float32)
        onnx_coord = np.concatenate([input_points, np.array([[0.0, 0.0]], dtype=np.float32)], axis=0)[None, :, :]
        onnx_label = np.concatenate([input_labels, np.array([-1], dtype=np.float32)], axis=0)[None, :]

        ones = np.ones((1, onnx_coord.shape[1], 1), dtype=np.float32)
        homog = np.concatenate([onnx_coord, ones], axis=2)
        onnx_coord = np.matmul(homog, matrix.T)[:, :, :2].astype(np.float32)

        names = {i.name: i for i in self.decoder_session.get_inputs()}
        has_mask = np.zeros((1,), dtype=np.float32)
        if "has_mask_input" in names and len(names["has_mask_input"].shape) == 2:
            has_mask = np.zeros((1, 1), dtype=np.float32)

        # Decoder generates a mask on the encoder canvas, then we warp back.
        orig_im_size = np.array([canvas_h, canvas_w], dtype=np.float32)
        decoder_inputs = {
            "image_embeddings": image_embedding,
            "image_embedding": image_embedding,
            "point_coords": onnx_coord,
            "point_labels": onnx_label.astype(np.float32),
            "mask_input": np.zeros((1, 1, 256, 256), dtype=np.float32),
            "has_mask_input": has_mask,
            "orig_im_size": orig_im_size,
        }
        feed = {k: v for k, v in decoder_inputs.items() if k in names}

        logger.info(
            "[SAM decode] orig_hw=%s canvas_hw=%s scale=%.6f pts_orig=%s pts_canvas=%s labels=%s orig_im_size=%s feed_keys=%s",
            (orig_h, orig_w),
            (canvas_h, canvas_w),
            scale,
            pts,
            onnx_coord[:, :-1, :].tolist(),
            lbs,
            orig_im_size.tolist(),
            list(feed.keys()),
        )

        with self._lock:
            raw_outs = self.decoder_session.run(None, feed)
        out_meta = [(o.name, tuple(np.array(v).shape)) for o, v in zip(self.decoder_session.get_outputs(), raw_outs)]
        logger.info("[SAM decode] raw outputs=%s", out_meta)

        by_name = {o.name: v for o, v in zip(self.decoder_session.get_outputs(), raw_outs)}
        masks = by_name.get("masks", raw_outs[0])
        iou_preds = by_name.get("iou_predictions", raw_outs[1] if len(raw_outs) > 1 else None)

        iou = None
        mask_idx = 0
        if iou_preds is not None:
            iou_arr = np.array(iou_preds).reshape(-1)
            if iou_arr.size:
                mask_idx = int(np.argmax(iou_arr))
                iou = float(iou_arr[mask_idx])
                logger.info("[SAM decode] iou=%s idx=%s", iou_arr.tolist(), mask_idx)

        m = np.array(masks)
        if m.ndim == 4:
            mask_canvas = (m[0, min(mask_idx, m.shape[1] - 1)] > 0).astype(np.uint8)
        elif m.ndim == 3:
            mask_canvas = (m[min(mask_idx, m.shape[0] - 1)] > 0).astype(np.uint8)
        else:
            mask_canvas = (m > 0).astype(np.uint8)

        if mask_canvas.shape != (canvas_h, canvas_w):
            logger.info("[SAM decode] resize mask %s -> canvas %s", mask_canvas.shape, (canvas_h, canvas_w))
            mask_canvas = cv2.resize(mask_canvas, (canvas_w, canvas_h), interpolation=cv2.INTER_NEAREST)

        inv = np.linalg.inv(matrix)
        mask_bin = cv2.warpAffine(
            mask_canvas,
            inv[:2],
            (orig_w, orig_h),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        logger.info(
            "[SAM decode] mask_canvas=%s mask_out=%s foreground=%s",
            mask_canvas.shape,
            mask_bin.shape,
            int(mask_bin.sum()),
        )
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
