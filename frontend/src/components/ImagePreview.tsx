import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import type { SessionResponse } from '../services/api';
import './ImagePreview.css';

interface ImagePreviewProps {
  session: SessionResponse;
  imageUrl: string | null;
  onError: (error: string) => void;
  promptMode?: 'add' | 'remove' | null;
  resetSignal?: number;
}

const ImagePreview: React.FC<ImagePreviewProps> = ({ session, imageUrl, onError, promptMode = 'add', resetSignal = 0 }) => {
  const [points, setPoints] = useState<number[][]>([]);
  const [labels, setLabels] = useState<number[]>([]);
  const [contours, setContours] = useState<number[][][]>([]);
  const [serverSize, setServerSize] = useState<{width: number, height: number} | null>(null);
  const [isPredicting, setIsPredicting] = useState(false);

  // 업로드(세션) 변경 시 상태 초기화
  useEffect(() => {
    setPoints([]);
    setLabels([]);
    setContours([]);
    setServerSize(null);
  }, [session.session_id, imageUrl]);

  // 외부 초기화 신호 처리
  useEffect(() => {
    if (resetSignal > 0) {
      setPoints([]);
      setLabels([]);
      setContours([]);
      setServerSize(null);
    }
  }, [resetSignal]);

  const handleImageClick = async (event: React.MouseEvent<HTMLImageElement>) => {
    if (isPredicting || !imageUrl) return;

    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // ✅ 정확한 좌표 변환 (preserveAspectRatio 고려)
    const serverW = session.image_info.width;
    const serverH = session.image_info.height;
    
    // 이미지의 실제 표시 영역 계산 (object-fit: contain 고려)
    const imageAspect = serverW / serverH;
    const containerAspect = rect.width / rect.height;
    
    let displayWidth, displayHeight, offsetX, offsetY;
    
    if (imageAspect > containerAspect) {
      // 이미지가 컨테이너보다 넓음 (좌우 여백)
      displayWidth = rect.width;
      displayHeight = rect.width / imageAspect;
      offsetX = 0;
      offsetY = (rect.height - displayHeight) / 2;
    } else {
      // 이미지가 컨테이너보다 높음 (상하 여백)
      displayHeight = rect.height;
      displayWidth = rect.height * imageAspect;
      offsetX = (rect.width - displayWidth) / 2;
      offsetY = 0;
    }
    
    // 클릭 좌표를 실제 이미지 영역으로 변환
    const relativeX = (x - offsetX) / displayWidth;
    const relativeY = (y - offsetY) / displayHeight;
    
    // 서버 좌표로 변환 (유효성 검사 포함)
    const imageX = Math.max(0, Math.min(serverW, relativeX * serverW));
    const imageY = Math.max(0, Math.min(serverH, relativeY * serverH));

    const label = promptMode === 'remove' ? 0 : 1;

    // 디버그 로그: 클릭/좌표 변환 정보
    console.log('[Click]', {
      pixel: { x, y },
      container: { width: rect.width, height: rect.height },
      display: { width: displayWidth, height: displayHeight, offsetX, offsetY },
      relative: { x: relativeX, y: relativeY },
      server: { x: imageX, y: imageY },
      promptMode,
      label,
    });
    const newPoints = [...points, [imageX, imageY]];
    const newLabels = [...labels, label];

    setPoints(newPoints);
    setLabels(newLabels);

    console.log('[Predict] points:', newPoints.length, 'labels:', newLabels);
    setIsPredicting(true);
    try {
      const result = await apiService.predictMask(session.session_id, newPoints, newLabels);
      setContours(result.contours);
      setServerSize({ width: result.width, height: result.height });
      console.log('[Predict] contours:', result.contours?.length, 'size:', result.width, 'x', result.height);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      const message = Array.isArray(detail)
        ? detail.map((d: any) => d?.msg || d?.detail || 'Validation error').join(', ')
        : (detail || '마스크 예측 중 오류가 발생했습니다.');
      onError(String(message));
    } finally {
      setIsPredicting(false);
    }
  };

  return (
    <div className="image-preview-container">

      <div className="image-container" style={{ position: 'relative' }}>
        {imageUrl && (
          <img
            src={imageUrl}
            alt="Uploaded"
            className="preview-image"
            onClick={handleImageClick}
            style={{ cursor: isPredicting ? 'wait' : 'crosshair', display: 'block', width: '100%', height: 'auto' }}
          />
        )}

        {contours.length > 0 && serverSize && imageUrl && (
          <svg
            className="contour-overlay"
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              pointerEvents: 'none',
              zIndex: 1,
            }}
            viewBox={`0 0 ${serverSize.width} ${serverSize.height}`}
            preserveAspectRatio="xMidYMid meet"   // img 스케일과 일치
          >
            {contours.map((contour, i) => {
              // polygon은 자동으로 닫히므로 그대로 사용
              const pointsAttr = contour.map(([x, y]) => `${x},${y}`).join(' ');
              return (
                <polygon
                  key={i}
                  points={pointsAttr}
                  fill="#FAE100"
                  fillOpacity={0.25}
                  stroke="#FAE100"
                  strokeWidth={4}
                  strokeOpacity={0.95}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                  shapeRendering="geometricPrecision"
                />
              );
            })}
          </svg>
        )}

      </div>


    </div>
  );
};

export default ImagePreview;
