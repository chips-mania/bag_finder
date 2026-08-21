import React, { useEffect, useRef, useState } from 'react';
import { apiService } from '../services/api';
import type { SessionResponse } from '../services/api';
import './ImagePreview.css';

interface ImagePreviewProps {
  session: SessionResponse;
  imageUrl: string | null;
  onError: (error: string) => void;
  promptMode?: 'add' | 'remove' | null;
  resetSignal?: number;
  onHeightChange?: (height: number) => void;
}

const ImagePreview: React.FC<ImagePreviewProps> = ({ session, imageUrl, onError, promptMode = 'add', resetSignal = 0, onHeightChange }) => {
  const [points, setPoints] = useState<number[][]>([]);
  const [labels, setLabels] = useState<number[]>([]);
  const [contours, setContours] = useState<number[][][]>([]);
  const [serverSize, setServerSize] = useState<{width: number, height: number} | null>(null);
  const [isPredicting, setIsPredicting] = useState(false);
  const imgRef = useRef<HTMLImageElement | null>(null);

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

  // 프리뷰 이미지 높이(렌더된 px)와 CSS 변수 값 로깅
  useEffect(() => {
    const el = imgRef.current;
    if (!el) return;

    const logHeights = () => {
      const root = document.documentElement;
      const cssVar = getComputedStyle(root)
        .getPropertyValue('--preview-img-h')
        .trim() || '600px';
      const rendered = Math.round(el.getBoundingClientRect().height);
      // eslint-disable-next-line no-console
      console.log('[Preview Height]', { cssVar, renderedPx: rendered });
      if (onHeightChange && rendered > 0) {
        onHeightChange(rendered);
      }
    };

    const ro = new ResizeObserver(() => logHeights());
    ro.observe(el);
    // 최초 1회
    logHeights();
    return () => {
      try { ro.disconnect(); } catch {}
    };
  }, [imageUrl, onHeightChange]);

    const handleImageClick = async (event: React.MouseEvent<HTMLImageElement>) => {
    if (isPredicting || !imageUrl) return;

    const img = event.currentTarget;
    const rect = img.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    const serverW = session.image_info.width;
    const serverH = session.image_info.height;
    const natW = img.naturalWidth || serverW;
    const natH = img.naturalHeight || serverH;
    const imageAspect = natW / natH;
    const containerAspect = rect.width / rect.height;

    let displayWidth, displayHeight, offsetX, offsetY;

    if (imageAspect > containerAspect) {
      displayWidth = rect.width;
      displayHeight = rect.width / imageAspect;
      offsetX = 0;
      offsetY = (rect.height - displayHeight) / 2;
    } else {
      displayHeight = rect.height;
      displayWidth = rect.height * imageAspect;
      offsetX = (rect.width - displayWidth) / 2;
      offsetY = 0;
    }

    const relativeX = (x - offsetX) / displayWidth;
    const relativeY = (y - offsetY) / displayHeight;
    if (relativeX < 0 || relativeX > 1 || relativeY < 0 || relativeY > 1) {
      return;
    }

    const imageX = Math.max(0, Math.min(serverW, relativeX * serverW));
    const imageY = Math.max(0, Math.min(serverH, relativeY * serverH));

    const label = promptMode === 'remove' ? 0 : 1;

    // 디버그 로그: 클릭/좌표 변환 정보
    console.log('[Click]', {
      pixel: { x, y },
      container: { width: rect.width, height: rect.height },
      display: { width: displayWidth, height: displayHeight, offsetX, offsetY },
      relative: { x: relativeX, y: relativeY },
      natural: { width: natW, height: natH },
      serverInfo: { width: serverW, height: serverH },
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
            ref={imgRef}
            style={{ cursor: isPredicting ? 'wait' : 'crosshair' }}
          />
        )}

        {imageUrl && (
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
            viewBox={`0 0 ${serverSize?.width ?? session.image_info.width} ${serverSize?.height ?? session.image_info.height}`}
            preserveAspectRatio="xMidYMid meet"
          >
            {contours.map((contour, i) => {
              const pointsAttr = contour.map(([x, y]) => `${x},${y}`).join(' ');
              return (
                <polygon
                  key={`c-${i}`}
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
            {points.map(([px, py], i) =>
              labels[i] === 0 ? null : (
                <circle
                  key={`p-${i}`}
                  cx={px}
                  cy={py}
                  r={6}
                  fill="#1677ff"
                  stroke="#fff"
                  strokeWidth={2}
                />
              )
            )}
          </svg>
        )}

      </div>


    </div>
  );
};

export default ImagePreview;
