
# 🧭 Supabase 설정 요약 (현재 상태 기준 — `public` 스키마)

## 1️⃣ 프로젝트 구성
- **DB 엔진**: PostgreSQL (Supabase 기본)
- **확장 기능**: `pgvector` → `create extension if not exists vector;`
- **스키마명**: `public`
- **RLS(Row Level Security)**: Off (공개 API 기반, 인증 없음)
- **사용 목적**: 이미지 임베딩 기반 가방 유사도 검색 서비스

---

## 2️⃣ 테이블 구조

### 📘 `public.bags`
| 컬럼명       | 타입            | 설명                               |
|-------------|----------------|------------------------------------|
| `bag_id`    | `text`   (PK)  | 상품 고유번호                        |
| `brand`     | `text`         | 브랜드명                            |
| `bag_name`  | `text`         | 상품명                              |
| `price`     | `numeric`      | 가격                                |
| `material`  | `text`         | 소재                                |
| `color`     | `text`         | 색상                                |
| `category`  | `text`         | 종류 (예: backpack, shoulder 등)     |
| `link`      | `text`         | 쇼핑몰 상세 페이지 URL                |
| `thumbnail` | `text`         | 대표 이미지 URL                      |
| `detail`    | `text`         | 상세 이미지 URL (필요시 JSON 배열 형태로 가능) |
 
✅ **특징**
- `link`는 실제 쇼핑몰 상품 페이지 링크.
- `thumbnail`, `detail`은 외부 이미지 URL 그대로 사용 (Supabase Storage 미사용).
- 이미지 파일 핫링크(외부 URL 직접 표시) 방식 채택.

---

### 📘 `public.image_embeddings`
| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| `bag_id` | `text` (PK, FK → bags.bag_id)` | `bags` 테이블 참조 |
| `embed` | `vector(512)` | CLIP ViT-B/32 임베딩 (L2 정규화 적용) |

✅ **특징**
- `bag_id` 기반 1:1 매핑.
- 삭제 시 CASCADE로 함께 제거.
- 512차원 벡터, 코사인 유사도 검색 기준.

---

## 3️⃣ 인덱스 설정
```sql
create index if not exists idx_bag_embed_cos
on public.image_embeddings
using ivfflat (embed vector_cosine_ops)
with (lists = 200);
```

✅ **검색 최적화 기준**
- 알고리즘: `ivfflat`
- 거리 계산: `vector_cosine_ops`
- `lists = 200` (데이터 규모에 따라 400~800까지 조정 가능)

---

## 5️⃣ 정책 및 권한 설정
| 항목 | 설정값 | 설명 |
|------|---------|------|
| RLS | Off | 인증 없이 조회 가능 |
| 권한 | public 접근 허용 | 프론트엔드 직접 접근용 |
| 인증 키 | `anon key` | 프론트엔드 Supabase-js용 |
| 서비스 키 | `service_role_key` | FastAPI 백엔드용 (DB write/search) |

---

## 6️⃣ 연결 정보 (.env에 이렇게 저장했음음)
```bash
SUPABASE_DB_URL=postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=eyJhbGciOi...
SCHEMA=public
TABLE_BAGS=bags
TABLE_EMB=image_embeddings
```

---

## 7️⃣ 현재 상태 요약

| 구분 | 상태 | 비고 |
|------|------|------|
| pgvector 확장 설치 | ✅ 완료 | `create extension vector` |
| 스키마 | ✅ `public` 사용 | 기본 스키마 |
| bags 테이블 | ✅ 생성됨 | 메타데이터 저장용 |
| image_embeddings 테이블 | ✅ 생성됨 | 벡터 검색용 |
| 벡터 인덱스 | ✅ 생성됨 | cosine 기준 ivfflat |
| RLS | ✅ Off | 인증 미사용 |
| URL 구조 | ✅ 외부 URL 그대로 사용 | Supabase Storage 미사용 |
| key 관리 | ✅ 백엔드/프론트 분리 | service / anon key 구분 |
