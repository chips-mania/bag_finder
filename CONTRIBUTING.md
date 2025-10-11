# 👜 Contributing Guidelines for Bag Segmentation & Search Project

감사합니다!  
이 프로젝트는 **가방 이미지를 AI로 세그멘테이션하고, Supabase 벡터 검색으로 유사한 가방을 찾는 웹서비스**입니다.  
아래의 가이드라인을 따라주시면 코드 품질과 협업 효율을 함께 유지할 수 있습니다.

---

## 🧾 Commit Message Convention

이 프로젝트는 **Conventional Commits** 규칙을 따릅니다.


### ✅ Commit Types
| Type | 설명 |
|------|------|
| **feat** | 새로운 기능 추가 |
| **fix** | 버그 수정 |
| **docs** | 문서 수정 (README, 주석 등) |
| **style** | 코드 포맷팅, 세미콜론/탭 등 비기능적 변경 |
| **refactor** | 코드 리팩터링 (기능 변화 없음) |
| **test** | 테스트 코드 추가 또는 수정 |
| **chore** | 빌드, 설정, 의존성, CI/CD 등 잡무 관련 |

### ✍️ 예시
feat(api): add endpoint for image segmentation
fix(frontend): correct label-path mismatch
docs: update README for deployment instructions
chore: update .gitignore for build folder



<!-- ---

## 🌿 Branch Naming

| 브랜치 이름 | 용도 |
|-------------|------|
| `main` | 배포용 |
| `dev` | 개발 통합용 |
| `feature/<기능명>` | 기능 추가 시 사용 (예: `feature/login-api`) |
| `fix/<이슈명>` | 버그 수정용 (예: `fix/image-path`) |

예시:
git checkout -b feature/upload-endpoint -->



---

## 🔍 Code Style

- Python: [PEP8](https://peps.python.org/pep-0008/) 스타일 준수  
- TypeScript/React: ESLint + Prettier 적용  
- 변수명은 명확하고 의미 있는 이름 사용  
- 불필요한 `console.log`, `print` 제거  

---

## 🧪 Testing

- FastAPI 백엔드는 `pytest` 기반 테스트를 사용합니다.
- 프론트엔드는 `vitest` 또는 `jest`를 사용합니다.
- 새 기능 추가 시, 최소 1개 이상의 테스트를 포함해주세요.

---

## 🐳 환경 변수

- 환경 변수는 `.env` 또는 `.env.local` 파일에 작성  
- `.env`는 커밋 금지 (`.gitignore`에 포함됨)  

