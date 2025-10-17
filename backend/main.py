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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from PIL import Image
from dotenv import load_dotenv
import uvicorn
import numpy as np

# 내부 모듈
from models.mobile_sam_model import MobileSAMModel
from services.session_cache import SessionCache
from services.supabase_client import supabase_client
from services.clip_service import get_image_embedding
from services.filter_service import FilterService
from services.similarity_filter_service import SimilarityFilterService
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

class FilterSearchRequest(BaseModel):
    selected_categories: List[str] = []
    selected_colors: List[str] = []
    min_price: float = 4900
    max_price: float = 1500000
    page: int = 1
    limit: int = 10  # 페이지당 10개 아이템 (최대 50개)

class SimilarityFilterSearchRequest(BaseModel):
    session_id: str
    selected_categories: List[str] = []
    selected_colors: List[str] = []
    min_price: float = 4900
    max_price: float = 1500000
    page: int = 1
    limit: int = 10  # 페이지당 10개 아이템 (최대 50개)

class BagResult(BaseModel):
    bag_id: str
    bag_name: str
    brand: str
    price: float
    material: str
    color: str  # JSON 문자열로 저장
    category: str
    link: str
    thumbnail: str
    detail: str
    similarity: float

class FilterSearchResponse(BaseModel):
    results: List[BagResult]
    total_count: int
    total_pages: int
    current_page: int

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

# 정적 파일 서빙: /static → backend/static
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

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
        # 입력 포인트/라벨 로깅
        try:
            pts_len = len(body.points) if isinstance(body.points, list) else 'n/a'
            lbs_len = len(body.labels) if isinstance(body.labels, list) else 'n/a'
            logger.info("/predict received: points=%s labels=%s", pts_len, lbs_len)
        except Exception:
            pass
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
        
        # 마스크 저장 (검색 시 사용)
        mask_path = SESS_DIR / f"{body.session_id}_mask.png"
        mask_pil = Image.fromarray((mask_bin * 255).astype(np.uint8))
        mask_pil.save(mask_path)
        
        # 세션에 마스크 경로 저장
        sess["last_mask_path"] = str(mask_path)

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
# 검색 API
# ──────────────────────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    session_id: str
    selected_colors: List[str] = []  # 선택된 색상명들


class BagResult(BaseModel):
    bag_id: str
    brand: str | None
    bag_name: str | None
    price: float | None
    material: str | None
    color: str | None
    category: str | None
    thumbnail: str | None
    link: str | None
    similarity: float  # 유사도 (0~1)


class SearchResponse(BaseModel):
    top5: List[BagResult]
    gallery10: List[BagResult]


@app.post("/search", response_model=SearchResponse)
async def search_bags(body: SearchRequest):
    """
    세션의 마스크 영역을 임베딩하여 유사한 가방을 검색합니다.
    unique bag_id 15개 이상 확보될 때까지 반복 조회합니다.
    """
    if session_cache is None:
        raise HTTPException(status_code=500, detail="Session cache not initialized")
    
    sess = session_cache.get_session(body.session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        # 1. 세션에서 마스크 이미지 로드
        image_path = sess.get("image_path")
        if not image_path or not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image not found")
        
        # 마스크 파일 경로 (세션에 저장된 최신 마스크 사용)
        mask_path = sess.get("last_mask_path")
        if not mask_path or not os.path.exists(mask_path):
            raise HTTPException(status_code=400, detail="No mask found. Please segment the image first.")
        
        # 2. 원본 이미지 + 마스크 로드
        original_img = Image.open(image_path).convert("RGB")
        mask_img = Image.open(mask_path).convert("L")  # grayscale
        
        # 3. 마스크 영역 바운딩박스 추출 및 크롭
        mask_np = np.array(mask_img)
        coords = np.column_stack(np.where(mask_np > 0))  # (y, x) 좌표
        
        if len(coords) == 0:
            raise HTTPException(status_code=400, detail="Mask is empty")
        
        y_min, x_min = coords.min(axis=0)
        y_max, x_max = coords.max(axis=0)
        
        # 크롭 (바운딩박스)
        cropped = original_img.crop((x_min, y_min, x_max + 1, y_max + 1))
        
        # 크롭된 마스크
        cropped_mask = mask_img.crop((x_min, y_min, x_max + 1, y_max + 1))
        cropped_mask_np = np.array(cropped_mask)
        
        # 4. 마스크 외부를 흰색으로 채우기
        cropped_np = np.array(cropped)
        white_bg = np.ones_like(cropped_np) * 255
        mask_3ch = np.stack([cropped_mask_np] * 3, axis=-1) > 0
        final_np = np.where(mask_3ch, cropped_np, white_bg).astype(np.uint8)
        final_img = Image.fromarray(final_np)
        
        # 5. CLIP 임베딩 생성
        query_embedding = get_image_embedding(final_img)
        
        # 6. Supabase 벡터 검색으로 유사도 검색 (전체 데이터 대상)
        try:
            # 벡터 검색 함수 호출
            response = supabase_client.rpc('match_embeddings', {
                'query_embedding': query_embedding,
                'match_threshold': 0.1,  # 유사도 임계값 (0.1 = 10%)
                'match_count': 50        # 상위 50개 반환
            }).execute()
            
            if not response.data:
                raise Exception("No similar items found")
            
            # 결과를 딕셔너리로 변환
            unique_bags = {}
            for row in response.data:
                bag_id = row['bag_id']
                similarity = row['similarity']
                unique_bags[bag_id] = float(similarity)
                
        except Exception as e:
            logger.warning(f"Vector search failed, falling back to Python calculation: {e}")
            # 벡터 검색 실패 시 기존 방식으로 폴백
            unique_bags = {}
            limit = 1000
            max_retries = 3
            
            for attempt in range(max_retries):
                response = supabase_client.table("image_embeddings") \
                    .select("bag_id, embed") \
                    .range(attempt * limit, (attempt + 1) * limit - 1) \
                    .execute()
                
                if not response.data:
                    break
                
                # 코사인 유사도 계산 (Python)
                for row in response.data:
                    bag_id = row["bag_id"]
                    embed = row["embed"]
                    
                    if bag_id in unique_bags:
                        continue
                    
                    if isinstance(embed, str):
                        import json
                        embed = json.loads(embed)
                    
                    query_vec = np.array(query_embedding, dtype=np.float32)
                    db_vec = np.array(embed, dtype=np.float32)
                    similarity = np.dot(query_vec, db_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(db_vec))
                    
                    unique_bags[bag_id] = float(similarity)
                
                if len(unique_bags) >= 50:
                    break
        
        # 7. 유사도 기준 정렬 (내림차순)
        sorted_bags = sorted(unique_bags.items(), key=lambda x: x[1], reverse=True)
        top_15_bag_ids = [bag_id for bag_id, _ in sorted_bags[:15]]
        
        # 8. bags 테이블에서 메타데이터 조회 (색상 필터링 적용)
        query = supabase_client.table("bags").select("*").in_("bag_id", top_15_bag_ids)
        
        # 색상 필터링이 있는 경우
        if body.selected_colors:
            # 색상 필터링을 위한 OR 조건 생성
            color_conditions = []
            for color in body.selected_colors:
                # ILIKE를 사용하여 대소문자 구분 없이 검색
                color_conditions.append(f"color.ilike.%{color}%")
            
            # OR 조건으로 색상 필터링 적용
            query = query.or_(",".join(color_conditions))
        
        bags_response = query.execute()
        
        # bag_id를 키로 하는 딕셔너리 생성
        bags_dict = {bag["bag_id"]: bag for bag in bags_response.data}
        
        # 9. 결과 구성 (순서 유지)
        results = []
        for bag_id, similarity in sorted_bags[:15]:
            bag_data = bags_dict.get(bag_id)
            if not bag_data:
                continue
            
            results.append(BagResult(
                bag_id=bag_id,
                brand=bag_data.get("brand"),
                bag_name=bag_data.get("bag_name"),
                price=bag_data.get("price"),
                material=bag_data.get("material"),
                color=bag_data.get("color"),
                category=bag_data.get("category"),
                thumbnail=bag_data.get("thumbnail"),
                link=bag_data.get("link"),
                similarity=similarity
            ))
        
        # 10. top5 / gallery10 분할
        top5 = results[:5]
        gallery10 = results[5:15]
        
        return SearchResponse(top5=top5, gallery10=gallery10)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Search error")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/filter-search", response_model=FilterSearchResponse)
async def filter_search_bags(body: FilterSearchRequest):
    """
    필터 조건에 따라 가방을 검색합니다.
    """
    try:
        # 필터 서비스 인스턴스 생성
        filter_service = FilterService()
        
        # 필터 검색 실행
        results, total_count = await filter_service.search_bags(
            categories=body.selected_categories,
            colors=body.selected_colors,
            min_price=body.min_price,
            max_price=body.max_price,
            page=body.page,
            limit=body.limit
        )
        
        # 총 페이지 수 계산
        total_pages = filter_service.calculate_total_pages(total_count, body.limit)
        
        # 딕셔너리 리스트로 변환 (Pydantic 모델 검증을 위해)
        bag_results = []
        for item in results:
            bag_results.append({
                'bag_id': item['bag_id'],
                'bag_name': item['bag_name'],
                'brand': item['brand'],
                'price': item['price'],
                'material': item['material'],
                'color': item['color'],
                'category': item['category'],
                'link': item['link'],
                'thumbnail': item['thumbnail'],
                'detail': item['detail'],
                'similarity': item['similarity']
            })
        
        return FilterSearchResponse(
            results=bag_results,
            total_count=total_count,
            total_pages=total_pages,
            current_page=body.page
        )
    
    except Exception as e:
        logger.exception("Filter search error")
        raise HTTPException(status_code=500, detail=f"Filter search failed: {str(e)}")


@app.post("/filter-search-with-similarity", response_model=FilterSearchResponse)
async def filter_search_bags_with_similarity(body: SimilarityFilterSearchRequest):
    """
    세션의 크롭된 이미지와 유사도를 계산하여 필터 검색합니다.
    """
    try:
        # 유사도 기반 필터 서비스 인스턴스 생성
        if session_cache is None:
            raise HTTPException(status_code=500, detail="Session cache not initialized")
        
        similarity_filter_service = SimilarityFilterService(session_cache)
        
        # 유사도 기반 필터 검색 실행
        results, total_count = await similarity_filter_service.search_bags_with_similarity(
            session_id=body.session_id,
            categories=body.selected_categories,
            colors=body.selected_colors,
            min_price=body.min_price,
            max_price=body.max_price,
            page=body.page,
            limit=body.limit
        )
        
        # 총 페이지 수 계산
        total_pages = similarity_filter_service.calculate_total_pages(total_count, body.limit)
        
        # 딕셔너리 리스트로 변환 (Pydantic 모델 검증을 위해)
        bag_results = []
        for item in results:
            bag_results.append({
                'bag_id': item['bag_id'],
                'bag_name': item['bag_name'],
                'brand': item['brand'],
                'price': item['price'],
                'material': item['material'],
                'color': item['color'],
                'category': item['category'],
                'link': item['link'],
                'thumbnail': item['thumbnail'],
                'detail': item['detail'],
                'similarity': item['similarity']
            })
        
        return FilterSearchResponse(
            results=bag_results,
            total_count=total_count,
            total_pages=total_pages,
            current_page=body.page
        )
    
    except Exception as e:
        logger.exception("Similarity filter search error")
        raise HTTPException(status_code=500, detail=f"Similarity filter search failed: {str(e)}")


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
