# BagFinder



> **사진 속 가방을 클릭하면 객체 영역을 분리하고, 3만 개 이상의 상품에서 유사한 가방을 찾아주는 AI Visual Search 서비스**



상품명이나 정확한 검색어를 몰라도 **이미지 자체를 검색 의도**로 사용할 수 있도록 설계했습니다.



**Live** · [Frontend](https://bag-finder-tan.vercel.app) · [Backend](https://bagfinder-production.up.railway.app)



### Key Results

| | Result |
|---|---:|
| Products | **32,309** |
| Image Embeddings | **99,458** |
| YOLO mask mAP50-95 | **0.362 → 0.922** |
| SAM `/predict` | **33.2s → 0.53s** |



<br><br>



---



## 1. Why BagFinder?



연예인·인플루언서의 착장처럼 **모습은 알지만 상품명은 모르는 제품**은 텍스트만으로 검색하기 어렵습니다.



BagFinder는 검색어를 입력하는 대신, 사진 속 원하는 가방을 직접 선택해 시각적으로 유사한 상품을 찾도록 설계했습니다.



![디토소비 배경](docs/readme/motivation-ditto-consumption.png)



단순 이미지 검색이 아니라, **비정형 사용자 이미지를 검색 가능한 표현으로 바꾸고**, 대규모 상품 카탈로그와 같은 embedding 공간에서 연결하는 것이 목표였습니다.



<br><br>



---



## 2. Search Pipeline



![시퀀스 다이어그램](docs/readme/architecture-sequence.png)



```text
Image Upload
    ↓
MobileSAM Image Encode  (/session, once)
    ↓
User Click
    ↓
Mask Decode             (/predict)
    ↓
Pixel Mask
    ↓
Post-process (contour clean + object crop)
    ↓
CLIP Embedding          (/search)
    ↓
pgvector Top-K
    ↓
Similar Products
```



- `/session`: SAM image encode 1회 → 세션 캐시
- `/predict`: cached embedding으로 mask decode
- **검색 전 후처리**: raw pixel mask를 그대로 CLIP에 넣지 않고, Contour 정리 + 객체 crop(마스크 외 흰색) 후 임베딩
- 필터: 세션 CLIP vector 재사용



<br><br>



---



## 3. Tech Stack



| Layer | Technology |
|---|---|
| Frontend | Vite · React · TypeScript |
| Backend | FastAPI · Python 3.11 |
| User Segmentation | MobileSAM · ONNXRuntime |
| Product Segmentation | YOLO11L-Seg |
| Embedding | CLIP ViT-B/32 · 512-d |
| Vector DB | Supabase Postgres · pgvector |
| Deploy | Vercel · Railway |



<br><br>



---



## 4. Product Image Segmentation



약 10만 장의 상품 이미지에서 가방 영역을 자동으로 추출하기 위해 **YOLO11L-Seg**를 파인튜닝했습니다.



공개 데이터로 학습한 모델은 실제 쇼핑몰 이미지에서 성능이 충분하지 않았습니다.  
데이터 분포를 비교해 **공개 데이터와 실제 상품 이미지 간 Domain Mismatch**를 원인으로 판단했습니다.



8개 카테고리의 실제 상품 이미지 **2,901장**을 직접 라벨링·검수하여 재학습했습니다.



### 비교한 모델 3종



| 이름 | 무엇인지 |
|---|---|
| **Base** | Ultralytics YOLO11L-Seg **사전학습 가중치** 그대로. COCO 계열 일반 객체(`handbag`, `backpack` 등) 기준 |
| **Roboflow + COCO** | Roboflow 등으로 모은 **공개 bag/COCO 계열 데이터**로 추가 학습·파인튜닝한 모델 |
| **AnyLabeling (Custom)** | 실제 쇼핑몰 상품 이미지 **2,901장을 AnyLabeling으로 직접 라벨링**하고 `bag` 단일 클래스로 학습한 모델 |



![탐지 비교](docs/readme/yolo-coco-vs-anylabeling.png)



### Model Evaluation



클래스 구성이 달라(`handbag` / `backpack` / `bag`) 동일 조건 비교를 위해 **200장 독립 테스트셋 + 커스텀 평가**로 mask mAP50-95를 맞췄습니다.  
(평가는 별도 실험 환경에서 수행, 이 레포 서빙 코드와 분리)



| Model | mask mAP50-95 |
|---|---:|
| Base | 0.362 |
| Roboflow + COCO | 0.570 |
| **AnyLabeling Custom** | **0.922** |



![mAP 비교](docs/readme/yolo-map-comparison.png)



<br><br>



---



## 5. Click-to-Search with MobileSAM



사용자 이미지는 배경·사람·여러 객체가 포함될 수 있어, **검색할 가방을 클릭으로 직접 지정**하도록 했습니다.



BagFinder에서는 가방의 시각적 특징만 임베딩해야 했기 때문에, Bounding Box보다 배경 포함을 줄일 수 있는 **pixel-level segmentation**이 적합하다고 판단했습니다.



### 개선: raw Pixel Mask → 후처리 후 검색



MobileSAM이 만든 **raw pixel mask를 그대로 CLIP에 넣으면** 경계 노이즈·구멍·주변 픽셀이 유사도에 섞이기 쉽습니다.



그래서 마스크를 **AnyLabeling 스타일로 후처리**한 뒤 검색에 사용합니다.



1. Pixel mask 이진화·외곽 Contour 정리 (`extract_contours` / `simplify_contours`, `backend/utils/contour_utils.py`)
2. Contour/마스크 기준으로 **객체 영역만 crop**
3. 마스크 밖은 **흰색 배경**으로 채워 가방 형상 위주로 임베딩 (`/search` in `backend/main.py`)



```text
User Click
   ↓
MobileSAM decode
   ↓
Raw Pixel Mask
   ↓
Post-process (contour clean + white-bg crop)   ← 검색 품질 개선
   ↓
CLIP → pgvector
```



| Contour Overlay (후처리 UI) | Raw Pixel Mask |
|---|---|
| ![contour](docs/readme/sam-contour-mask.png) | ![pixel](docs/readme/sam-pixel-mask.png) |



<br><br>



---



## 6. Serving Optimization



Railway CPU에서 Ultralytics MobileSAM `.pt`는 `/predict` 평균 **33.2초**였습니다.



### Latency — 지표별로 무엇을 바꿨는지



동일 이미지·클릭 rollback A/B (`n=5` avg).



| 지표 | Before → After | 무엇을 바꿨는지 |
|---|---:|---|
| **SAM `/predict`** | 33.2s → **0.53s** (~62×) | `.pt` → **ONNXRuntime** + 클릭마다 encode 제거 → **decode만** (`reuse_embedding`) |
| **Session + Predict** | 34.2s → **1.9s** (~18×) | encode를 **`/session` 1회**로 옮기고, 첫 클릭은 decode 위주 |
| **Filter Search** | 27.0s → **1.2s** (~23×) | 필터마다 CLIP 재계산 제거 → **`sess["clip_embedding"]` 재사용** |



```text
.pt → ONNXRuntime                 → SAM /predict
SAM encode → /session cache       → Session + Predict
CLIP embed → session reuse        → Filter Search
```



- [`before_pt.json`](_bench_assets/before_pt.json)
- [`after_onnx.json`](_bench_assets/after_onnx.json)



<br><br>



---



## 7. Database



![스키마](docs/readme/db-schema.png)



| Table | Role |
|---|---|
| `bags` | 상품 메타데이터 |
| `image_embeddings` | 상품 이미지 CLIP vector + `bag_id` |



하나의 상품에 여러 이미지·촬영 각도의 embedding을 연결하고, **99,458개 vector**를 대상으로 유사도 검색합니다.



- 검색: Supabase RPC `match_embeddings` (cosine similarity)
- 결과에서 `bag_id` 기준으로 묶어 **상품 단위 중복 제거** 후 Top 결과 구성



<br><br>



---



## 8. API



| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/session` | Upload + SAM encode |
| `POST` | `/predict` | Click → Mask (+ Contour post-process for UI) |
| `POST` | `/search` | Post-processed crop → CLIP → `match_embeddings` |
| `POST` | `/filter-search-with-similarity` | Cached CLIP + filters |



<br><br>



---



## 9. Local Setup



### Backend

```bash
cd backend
pip install -r requirements.txt
cp ../env.example .env
uvicorn main:app --reload --port 8000
```



### Frontend

```bash
cd frontend
npm install
npm run dev
```



환경 변수는 [`env.example`](env.example)을 참고하세요.
