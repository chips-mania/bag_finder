# backend/main.py
import os
import io
import logging
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, Any, List

from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from PIL import Image
from dotenv import load_dotenv
import uvicorn
import numpy as np

# 내부 모듈
from models.mobile_sam_model import MobileSAMModel
from services.session_cache import SessionCache
from utils.image_utils import (
    validate_image_file,
    resize_image,
    convert_to_rgb,
    get_image_info,
)
from utils.contour_utils import extract_contours, simplify_contours

# ──────────────────────────────────────────────────────────────────────────────
# 환경 변수 & 로깅
# ──────────────────────────────────────────────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main")

# ──────────────────────────────────────────────────────────────────────────────
# 전역 상태 (lifespan에서 초기화)
# ──────────────────────────────────────────────────────────────────────────────
mobile_sam_model: MobileSAMModel | None = None
session_cache: SessionCache | None = None
SESS_DIR = Path("sessions")
SESS_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# Pydantic 모델
# ──────────────────────────────────────────────────────────────────────────────
class SessionResponse(BaseModel):
    session_id: str
    image_info: Dict[str, Any]  # {"width": int, "height": int, "format": str}

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    session_count: int

class PredictBody(BaseModel):
    session_id: str
    points: List[List[float]] | List[List[List[float]]]  # [[x,y],...] or [[[x,y],...]]
    labels: List[int] | List[List[int]]                  # [1,0,...] or [[1,0,...]]

class PredictResponse(BaseModel):
    contours: List[List[List[float]]]  # [[[x,y],...], ...]
    width: int
    height: int
    iou: float | None

# ──────────────────────────────────────────────────────────────────────────────
# Lifespan
# ──────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global mobile_sam_model, session_cache
    logger.info("Starting application...")

    try:
        model_path = os.getenv("MODEL_PATH", "models/mobile_sam.pt")
        mobile_sam_model = MobileSAMModel(model_path)
        logger.info("Mobile SAM model loaded successfully")

        ttl_minutes = int(os.getenv("SESSION_TTL_MINUTES", "10"))
        session_cache = SessionCache(ttl_minutes)
        logger.info("Session cache initialized (TTL=%s min)", ttl_minutes)

        # (선택) 성능 환경 변수
        os.environ["OMP_NUM_THREADS"] = os.getenv("OMP_NUM_THREADS", "4")
        os.environ["OPENBLAS_NUM_THREADS"] = os.getenv("OPENBLAS_NUM_THREADS", "1")
        os.environ["MKL_NUM_THREADS"] = os.getenv("MKL_NUM_THREADS", "4")

    except Exception:
        logger.exception("Failed to initialize application")
        raise

    try:
        yield
    finally:
        logger.info("Shutting down application...")

# ──────────────────────────────────────────────────────────────────────────────
# FastAPI 앱
# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Mobile SAM Image Search API",
    description="Mobile SAM을 사용한 이미지 세그멘테이션 및 검색 서비스",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
env_origins = os.getenv("CORS_ORIGINS")  # 콤마 구분
if env_origins:
    allow_origins = [o.strip() for o in env_origins.split(",") if o.strip()]
else:
    frontend_url = os.getenv("FRONTEND_URL")
    allow_origins = [frontend_url] if frontend_url else default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 요청/응답 로깅
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(">> %s %s", request.method, request.url.path)
    resp = await call_next(request)
    logger.info("<< %s %s", resp.status_code, request.url.path)
    return resp

# ──────────────────────────────────────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/", response_model=Dict[str, Any])
async def root():
    return {"message": "Mobile SAM Image Search API", "status": "running"}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        model_loaded=mobile_sam_model is not None,
        session_count=session_cache.get_session_count() if session_cache else 0,
    )

# /session (슬래시 유연)
@app.post("/session", response_model=SessionResponse)
@app.post("/session/", response_model=SessionResponse)
async def create_session(file: UploadFile = File(...)):
    """이미지 업로드 → 저장 → session_id 반환"""
    try:
        # 1) 타입 체크
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Only image/* accepted, got {file.content_type!r}",
            )

        # 2) 파일 읽기
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty file")

        # 3) 이미지 유효성
        if not validate_image_file(raw):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image file or file too large",
            )

        # 4) PIL 로드 & RGB
        try:
            img = Image.open(io.BytesIO(raw))
            img_format = (img.format or "").upper()
            img = convert_to_rgb(img)
        except Exception as e:
            logger.exception("PIL failed to open image")
            raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

        # 5) (선택) 리사이즈
        max_size = int(os.getenv("MAX_IMAGE_SIZE", "1024"))
        img = resize_image(img, max_size)

        # 6) 정보
        info = get_image_info(img)
        if not info.get("format"):
            info["format"] = img_format or (file.content_type or "image")
        logger.info(f"Processing image: {info}")

        # 7) 준비 상태 체크
        if mobile_sam_model is None:
            raise HTTPException(status_code=500, detail="Model not loaded")
        if session_cache is None:
            raise HTTPException(status_code=500, detail="Session cache not initialized")

        # 8) 저장 + 세션
        session_id = str(uuid.uuid4())
        img_path = SESS_DIR / f"{session_id}.png"
        img.save(img_path)

        # 동일 session_id로 저장(※ predict에서 찾기 위해)
        session_cache.create_session({
            "image_path": str(img_path),
            "width": info["width"],
            "height": info["height"],
            "format": info["format"],
        }, session_id=session_id)

        logger.info("Session created successfully: %s", session_id)

        return SessionResponse(
            session_id=session_id,
            image_info={"width": info["width"], "height": info["height"], "format": info["format"]},
        )

    except HTTPException:
        raise
    except ValidationError as e:
        logger.exception("Response model validation error")
        raise HTTPException(status_code=500, detail={"schema_error": e.errors()})
    except Exception as e:
        logger.exception("Unhandled /session error")
        raise HTTPException(status_code=500, detail=f"internal error: {type(e).__name__}: {e}")

@app.get("/session/{session_id}")
async def get_session_info(session_id: str):
    if session_cache is None:
        raise HTTPException(status_code=500, detail="Session cache not initialized")
    info = session_cache.get_session_info(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="Session not found")
    return info

@app.post("/predict", response_model=PredictResponse)
async def predict_mask(body: PredictBody):
    """클릭 좌표로 마스크 예측 → 컨투어 추출 (JSON 바디, AnyLabeling 스타일)"""
    if mobile_sam_model is None:
        raise HTTPException(status_code=500, detail="Model not loaded")
    if session_cache is None:
        raise HTTPException(status_code=500, detail="Session cache not initialized")

    # 세션에서 원본 데이터(dict) 가져와야 image_path/크기 메타를 얻을 수 있음
    sess = session_cache.get_session(body.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    image_path = sess.get("image_path")
    if not image_path or not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        logger.exception("Failed to open session image")
        raise HTTPException(status_code=500, detail=f"Failed to open image: {e}")

    try:
        # SAM 추론 (반환 마스크는 입력 이미지 크기와 동일하도록 보장)
        mask_bin, iou = mobile_sam_model.predict_mask(
            image=img,
            points=body.points,
            labels=body.labels,
            multimask_output=False,
        )

        # ✅ AnyLabeling 스타일 컨투어 추출 & 단순화
        contours = extract_contours(
            mask_bin,
            retr_mode="external",                  # 외곽선만
            chain_approx=1,                        # cv2.CHAIN_APPROX_NONE = 1
            apply_area_filters=True,               # 90% 초과/평균 20% 미만 필터
        )
        contours = simplify_contours(
            contours,
            epsilon_factor=0.001,                  # 아주 미세하게만 단순화
        )

        # JSON 직렬화를 위해 float 리스트로 보장
        contours_json: List[List[List[float]]] = [
            [[float(x), float(y)] for x, y in poly] for poly in contours
        ]

        width = int(sess.get("width", img.width))
        height = int(sess.get("height", img.height))

        return PredictResponse(
            contours=contours_json,
            width=width,
            height=height,
            iou=float(iou) if iou is not None else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled /predict error")
        raise HTTPException(status_code=500, detail=f"internal error: {type(e).__name__}: {e}")

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    if session_cache is None:
        raise HTTPException(status_code=500, detail="Session cache not initialized")
    ok = session_cache.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted successfully"}

# ──────────────────────────────────────────────────────────────────────────────
# Entrypoint (개발용)
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("DEBUG", "True").lower() == "true"

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info",
    )
