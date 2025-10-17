# CoverFlow 컴포넌트 문서

## 📋 개요

CoverFlow는 3D 회전 효과가 있는 이미지 갤러리 컴포넌트입니다. 중앙에 강조된 이미지와 좌우로 흐릿한 이미지들을 보여주며, 사용자가 이미지를 탐색할 수 있도록 합니다. 웹소설 캐릭터 시각화 서비스에서 AI 생성 이미지를 효과적으로 표시하기 위해 개발되었습니다.

## 🏗️ 컴포넌트 구조

### Props 인터페이스

```typescript
interface CoverFlowProps {
  images: AIImage[];  // 표시할 이미지 배열
}
```

### AIImage 타입

```typescript
interface AIImage {
  id: string;
  imageUrl: string;
  novelId: string;
  novelTitle: string;
  characterName: string;
  description: string;
}
```

## 🎨 주요 기능

### 1. 3D 회전 효과
- **중앙 이미지**: 완전히 보이고 강조됨
- **좌우 이미지**: 회전하고 축소되어 배치
- **투명도**: 중앙에서 멀어질수록 흐려짐
- **Z-index**: 중앙이 가장 앞에 위치

### 2. 네비게이션
- **이전/다음 버튼**: 좌우 화살표 버튼
- **인디케이터**: 하단의 점들로 현재 위치 표시
- **애니메이션**: 700ms 전환 효과

### 3. 이미지 상호작용
- **클릭**: 이미지 클릭 시 모달 열기
- **호버**: 호버 시 오버레이 효과
- **정보 표시**: 중앙 이미지에 캐릭터 정보 표시

## 🔧 핵심 로직

### 1. 위치 계산

```typescript
// 현재 이미지를 기준으로 상대적 위치 계산
let distance = index - currentIndex;

// 순환 배열에서 최단 거리 계산
if (distance > len / 2) {
  distance -= len;
} else if (distance < -len / 2) {
  distance += len;
}

// 보이는 범위 제한 (-2, -1, 0, 1, 2)
if (Math.abs(distance) > 2) {
  return null;
}
```

### 2. 3D 변환

```typescript
const isActive = distance === 0;
const rotationY = distance * 20;        // Y축 회전
const translateX = distance * 280;      // X축 이동
const translateZ = isActive ? 0 : -80;  // Z축 이동
const scale = isActive ? 1 : 0.85;      // 크기 조정
const opacity = isActive ? 1 : Math.abs(distance) === 1 ? 1 : 0.7;
```

### 3. 애니메이션 제어

```typescript
const [isTransitioning, setIsTransitioning] = useState(false);

const handleNext = () => {
  if (isTransitioning) return;
  setIsTransitioning(true);
  setCurrentIndex((prev) => (prev + 1) % len);
  setTimeout(() => setIsTransitioning(false), 700);
};
```

## 📱 반응형 디자인

### 이미지 크기

```typescript
className="w-56 h-72 md:w-64 md:h-80 lg:w-72 lg:h-96 xl:w-80 xl:h-[28rem]"
```

### 컨테이너 높이

```typescript
className="min-h-[400px] md:min-h-[500px] lg:min-h-[600px] xl:min-h-[700px]"
```

## 🎯 사용법

### 1. 기본 사용

```tsx
import CoverFlow from './components/CoverFlow/CoverFlow';
import { aiImages } from './data/ai-images';

function MyComponent() {
  return (
    <CoverFlow images={aiImages} />
  );
}
```

### 2. 데이터 준비

```typescript
const images: AIImage[] = [
  {
    id: '1',
    imageUrl: '/images/character1.png',
    novelId: '1',
    novelTitle: '웹소설 제목',
    characterName: '캐릭터 이름',
    description: '캐릭터 설명'
  },
  // ... 더 많은 이미지
];
```

### 3. 모달 연동

CoverFlow는 자동으로 ImageModal과 연동됩니다:
- 이미지 클릭 시 모달 열기
- 모달에서 댓글 작성 가능
- 캐릭터 상세 정보 표시

## 🎨 스타일링

### CSS 클래스

```css
.coverflow-container {
  @apply relative w-full h-[500px] overflow-hidden;
}
```

### Tailwind 클래스

- **컨테이너**: `relative overflow-hidden min-h-[60vh]`
- **이미지**: `object-cover rounded-2xl shadow-2xl`
- **버튼**: `bg-white/90 hover:bg-white p-3 rounded-full shadow-xl`
- **인디케이터**: `w-3 h-3 rounded-full transition-all duration-300`

## 🔄 상태 관리

### 내부 상태

```typescript
const [currentIndex, setCurrentIndex] = useState(0);        // 현재 이미지 인덱스
const [isTransitioning, setIsTransitioning] = useState(false); // 애니메이션 상태
const [selectedImage, setSelectedImage] = useState<AIImage | null>(null); // 선택된 이미지
const [isModalOpen, setIsModalOpen] = useState(false);      // 모달 열림 상태
```

## 🚀 확장 가능성

### 1. 커스터마이징

- **이미지 크기**: CSS 클래스 수정
- **회전 각도**: `rotationY` 값 조정
- **이동 거리**: `translateX` 값 조정
- **애니메이션 시간**: `setTimeout` 값 조정

### 2. 추가 기능

- **자동 슬라이드**: `setInterval` 추가
- **키보드 네비게이션**: `useEffect`로 키 이벤트 리스너
- **터치 제스처**: 터치 이벤트 핸들러 추가
- **무한 루프**: 현재는 순환 배열로 구현됨

## 📝 주의사항

1. **이미지 로딩**: 이미지가 로드되기 전에 레이아웃이 깨질 수 있음
2. **성능**: 많은 이미지가 있을 때 성능 최적화 필요
3. **접근성**: 키보드 네비게이션과 스크린 리더 지원 필요
4. **모바일**: 터치 제스처 지원 고려

## 📁 파일 구조

```
src/components/CoverFlow/
├── CoverFlow.tsx          # 메인 컴포넌트
└── index.ts              # 내보내기 파일 (선택사항)
```

## 🔗 의존성

- **React**: 18.2.0+
- **TypeScript**: 5.2.2+
- **Tailwind CSS**: 3.3.5+

## 📊 성능 최적화

### 1. 이미지 최적화

```typescript
// 이미지 로딩 최적화
<img
  src={image.imageUrl}
  alt={image.characterName}
  className="w-56 h-72 md:w-64 md:h-80 lg:w-72 lg:h-96 xl:w-80 xl:h-[28rem] object-cover rounded-2xl shadow-2xl group-hover:shadow-3xl transition-all duration-500"
  loading="lazy"  // 지연 로딩
/>
```

### 2. 애니메이션 최적화

```typescript
// GPU 가속 활성화
className="absolute transition-all duration-700 ease-in-out cursor-pointer transform-gpu"
```

## 🎯 사용 사례

### 1. 웹소설 캐릭터 갤러리

```tsx
// 홈페이지에서 사용
<CoverFlow images={aiImages} />
```

### 2. 제품 갤러리

```tsx
// 제품 이미지 갤러리
<CoverFlow images={productImages} />
```

### 3. 포트폴리오 갤러리

```tsx
// 포트폴리오 이미지 갤러리
<CoverFlow images={portfolioImages} />
```

## 🔧 개발 팁

### 1. 디버깅

```typescript
// 이미지 클릭 시 로그 출력
const handleImageClick = (image: AIImage) => {
  console.log('Image clicked:', image);
  setSelectedImage(image);
  setIsModalOpen(true);
  console.log('Modal state set to open');
};
```

### 2. 테스트

```typescript
// 빈 배열 처리
if (len === 0) {
  return (
    <div className="coverflow-container flex items-center justify-center bg-gray-100 rounded-lg">
      <span className="text-gray-400">AI 이미지가 없습니다</span>
    </div>
  );
}
```

### 3. 접근성

```typescript
// ARIA 라벨 추가
<button
  onClick={handlePrev}
  disabled={isTransitioning}
  className="..."
  aria-label="이전"
>
```

## 📈 향후 개선 계획

1. **터치 제스처 지원**: 모바일에서 스와이프 제스처 추가
2. **키보드 네비게이션**: 화살표 키로 이미지 탐색
3. **자동 슬라이드**: 일정 시간마다 자동으로 다음 이미지로 이동
4. **무한 루프**: 마지막 이미지에서 첫 번째 이미지로 자연스럽게 이동
5. **썸네일 네비게이션**: 하단에 썸네일 이미지 추가

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

---

**참고**: 이 문서는 CharacterSketch 프로젝트의 CoverFlow 컴포넌트를 기반으로 작성되었습니다.
