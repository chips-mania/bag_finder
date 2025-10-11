# bag_finder
AI-powered web service that detects and segments bags from uploaded images using MobileSAM, extracts visual features, and finds visually similar bags through vector search with Supabase.


# 🧭 프로젝트 개요 (MVP 기준)

## 🎯 프로젝트 목표
웹 애플리케이션에서 사용자가 이미지를 업로드하고,  
**Mobile SAM (CPU 전용)** 으로 클릭 기반 세그멘테이션을 수행한 뒤,  
내부적으로 크롭 영역을 분석하여 **pgvector 기반 Top 15 유사도 검색** 결과를 표시하는 서비스입니다.

- **Frontend**: Vite (React 기반)
- **Backend**: FastAPI (Python)
- **Database**: Supabase (Postgres + pgvector)
- **Model**: Mobile SAM (ONNXRuntime - CPU 전용)
- **Embedding Model**: CLIP (ViT-B/32)
- **Infra**: 단일 서버(초기 CPU만 사용)
- **Search Result**: Top 15 결과 카드 표시
- **UI 특징**: 결과 카드의 색상 버튼 클릭 시 가용 색상 아이콘 표시(애니메이션 포함)
- **크롭 이미지는 프런트에 표시하지 않고 내부 처리만 수행**

---

## ⚙️ 시스템 흐름
```
[사용자 업로드] 
   ↓
POST /session  
   └─ Mobile SAM image embedding 1회 계산 → session_id 반환
   ↓
사용자 클릭(+/-)
   ↓
POST /predict
   └─ session_id 기반 임베딩 재사용 → 마스크 내부 계산 및 보관
   ↓
POST /finalize
   └─ 마스크 기반 크롭(내부용) → CLIP 임베딩 계산 → pgvector Top-15 유사도 검색
   ↓
프런트: 15개 결과 카드 렌더링
   ↓
GET /items/{id}/colors
   └─ 색상 리스트 반환 → 색상칩 애니메이션 표시
```
---

## 🧩 기술 스택

| 구성 요소 | 기술 스택 | 비고 |
|------------|------------|------|
| **Frontend** | Vite + React + TypeScript | DnD 업로드, 클릭 좌표 수집, 결과 카드 UI |
| **Backend** | FastAPI + Python 3.11 | Mobile SAM CPU 추론, 세션 캐시, 검색 API |
| **Database** | Supabase (Postgres + pgvector) | 임베딩 저장 및 유사도 검색 |
| **Model** | **Mobile SAM** (ONNXRuntime CPU) | 세그멘테이션 전용 |
| **Embedding** | CLIP (ViT-B/32) | 유사도 계산용 |
| **Storage** | Supabase Storage | 원본/썸네일/마스크(내부용) |

---

## 🧠 모델 서빙 정책

- **Mobile SAM (CPU 전용)**  
  - 포맷: ONNX  
  - 엔진: ONNXRuntime (OpenVINO 또는 DNNL Execution Provider)  
  - 해상도 제한: 긴 변 최대 1024px  
  - `/session` 시 image embedding 1회만 계산 (세션 캐시 유지)
  - `/predict`에서는 캐시된 embedding만 사용하여 마스크 계산
  - `/finalize`는 내부에서 마스크 → 크롭 → CLIP 임베딩 → pgvector 검색 수행

- **CLIP (ViT-B/32)**  
  - 임베딩 차원: 512  
  - DB 내 `embedding vector(512)` 필드와 동일한 전처리 파이프라인 유지  

- **결과 Top 15**  
  - `ORDER BY embedding <-> $1 LIMIT 15`  
  - 항상 정확히 15개 결과 반환  

---

## 📡 주요 API 계약

| Endpoint | Method | Description |
|-----------|--------|-------------|
| `/session` | POST | 이미지 업로드 → Mobile SAM image embedding 1회 계산 및 `session_id` 반환 |
| `/predict` | POST | 클릭 좌표(+/-) 기반 마스크 계산 (내부 보관, 마스크 응답 없음) |
| `/finalize` | POST | 내부 크롭 → CLIP 임베딩 → Supabase pgvector 검색 (Top-15 결과 반환) |
| `/items/{id}/colors` | GET | 특정 결과의 가용 색상 목록 반환 |

> ⚠️ 크롭 이미지는 프런트에 전송하지 않으며, 서버 내부에서만 처리합니다.

---

## 🗃️ Supabase 스키마

### `items`
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID / Serial | PK |
| title | text | 상품명 |
| brand | text | 브랜드명 |
| price | int | 가격 |
| thumb_url | text | 썸네일 경로 |
| embedding | vector(512) | CLIP 임베딩 |
| has_colors | bool | 색상 데이터 여부 |

### `item_colors`
| 컬럼 | 타입 | 설명 |
|------|------|------|
| item_id | FK → items.id | 참조 |
| color_name | text | 색상 이름 |
| color_hex | text | 색상 HEX 코드 |
| swatch_url | text (optional) | 색상 이미지 |

---

## 🪜 개발 단계 (7단계 로드맵)

1️⃣ **업로드 & 세션 캐시**  
→ 이미지 업로드(DnD) 후 Mobile SAM 임베딩 생성 → session_id 반환  

2️⃣ **클릭 좌표 수집 & /predict**  
→ 프런트에서 +/− 클릭 좌표 수집 → /predict 호출 (마스크 내부 보관)  

3️⃣ **마스크 후처리 & 상태 관리**  
→ 서버 내부에서 최대 연결요소 선택, 소영역 제거, 홀 필링 등 후처리  

4️⃣ **크롭(내부) → CLIP 임베딩 생성**  
→ 마스크 기반 크롭 후 CLIP 전처리 → 쿼리 벡터 계산  

5️⃣ **Supabase(pgvector) 연동 & Top-15 검색**  
→ CLIP 벡터 기반 Top 15 유사도 결과 반환  

6️⃣ **결과 카드(15) & 색상 버튼 → 색상 아이콘 애니메이션**  
→ 프런트에서 카드 15개 표시, 색상 버튼 클릭 시 색상칩 애니메이션 표시  

7️⃣ **최적화 & 안정화**  
→ 세션 TTL, 레이트리밋, 타임아웃, 로그, CPU 성능 튜닝

---

## ⚡ 성능 / 안정화 기준

| 항목 | 기준 |
|------|------|
| `/session` | p95 ≤ 2.5s (CPU 기준) |
| `/predict` | p95 ≤ 800ms |
| `/finalize` | p95 ≤ 800ms |
| 세션 TTL | 10분 미사용 시 삭제 |
| 이미지 해상도 | 긴 변 ≤ 1024px |
| 파일 크기 제한 | ≤ 15MB |
| 레이트리밋 | 세션당 `/predict` ≤ 5 RPS |
| 결과 | 항상 Top 15 반환 |

---

## 🎨 프런트엔드 UX 개요

- **DnD + 클릭 업로드** → 미리보기 표시  
- 클릭 시 **+/− 토글**, “검색 실행” 버튼 별도  
- **결과 카드 15개**: 썸네일, 이름, 브랜드, 가격, 점수  
- **색상 버튼 클릭 시** → 색상 아이콘 애니메이션 표시 (페이드/슬라이드 효과)  
- 로딩/에러 메시지 → 통일된 토스트/알럿 처리

---

## 🧱 운영 / 보안 지침

- 업로드 허용 포맷: JPG / PNG / WebP  
- 세션 및 이미지: 10분 후 자동 삭제  
- CORS: 프런트(Vite 도메인)만 허용  
- 로깅: p50/p95, 실패율, 예외 메시지, CPU 스레드/큐 길이  
- DB 커넥션 풀 제한 및 쿼리 타임아웃 설정

---

## 🧩 개발 진행 규칙

- 총 **7단계**로 나누어 구현 및 테스트 진행  
- 각 단계는 `설명 + 입출력 명세 + DoD(완료 기준)` 형태로 작성  
- 모든 모델 동작은 **CPU 전용 (Mobile SAM)** 으로 설정  
- 크롭 이미지는 **내부 처리만** 수행 (프런트 미노출)  
- 각 단계 완료 후 테스트 통과 시 다음 단계 진행  

---

## ✅ Cursor 전달용 요약 문장

> 이 프로젝트는 **Vite + FastAPI + Supabase + Mobile SAM(CPU 전용)** 기반의 클릭형 이미지 검색 웹서비스입니다.  
> 사용자가 이미지를 업로드하면 Mobile SAM이 내부적으로 세그멘테이션을 수행하고,  
> 크롭된 객체를 CLIP 임베딩으로 변환해 pgvector를 통해 **Top 15 유사 이미지**를 반환합니다.  
> 크롭 이미지는 프런트에 표시하지 않으며,  
> 결과 카드의 색상 버튼을 누르면 해당 상품의 색상 아이콘이 애니메이션으로 표시됩니다.  
> 개발은 총 7단계로 나누어 순차적으로 진행됩니다.
