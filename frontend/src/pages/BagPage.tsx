import React, { useState, useRef } from 'react';
import ImageUpload from '../components/ImageUpload';
import ImagePreview from '../components/ImagePreview';
import type { SessionResponse } from '../services/api';
import './BagPage.css';

interface BagPageProps {
  session: SessionResponse | null;
  imageUrl: string;
  isLoading: boolean;
  onSessionCreated: (session: SessionResponse, imageUrl: string) => void;
  onError: (errorMessage: string) => void;
  onReset: () => void;
}

const BagPage: React.FC<BagPageProps> = ({
  session,
  imageUrl,
  isLoading,
  onSessionCreated,
  onError,
  onReset
}) => {
  const [showResults, setShowResults] = useState(false);
  const [promptMode, setPromptMode] = useState<'add' | 'remove' | null>('add');
  const [resetSignal, setResetSignal] = useState(0);
  const [previewHeight, setPreviewHeight] = useState<number>(600);

  // 데모 가방 데이터 (백엔드 정적 경로)
  const demoBags = Array.from({ length: 20 }, (_, i) => ({
    id: i + 1,
    imageUrl: `http://127.0.0.1:8000/static/assets/boston_bag/${i + 1}.jpg`,
    name: `보스턴백 ${String.fromCharCode(65 + (i % 26))}`,
    brand: ['Louis Vuitton', 'Gucci', 'Prada', 'Hermès', 'Chanel'][i % 5],
    price: (i + 1) * 50000,
    bagType: '보스턴백',
    material: '가죽',
  }));

  // 하단 갤러리 스크롤 제어
  const bottomGalleryRef = useRef<HTMLDivElement | null>(null);
  const resultsListRef = useRef<HTMLDivElement | null>(null);
  const scrollBottomGallery = (direction: 'left' | 'right') => {
    const el = bottomGalleryRef.current;
    if (!el) return;
    const delta = direction === 'left' ? -el.clientWidth * 0.8 : el.clientWidth * 0.8;
    el.scrollBy({ left: delta, behavior: 'smooth' });
  };
  const scrollResults = (direction: 'up' | 'down') => {
    const el = resultsListRef.current;
    if (!el) return;
    const delta = direction === 'up' ? -el.clientHeight * 0.8 : el.clientHeight * 0.8;
    el.scrollBy({ top: delta, behavior: 'smooth' });
  };
  return (
    <div className="bag-page">
      <div className="bag-header">
      </div>

      <main className={`bag-main ${showResults ? 'preview-mode' : 'upload-mode'}`}>
        <div className="bag-content">
          <div className="upload-section">
            {!session ? (
              <ImageUpload
                onSessionCreated={onSessionCreated}
                onError={onError}
                isLoading={isLoading}
              />
            ) : (
              <ImagePreview
                session={session}
                imageUrl={imageUrl}
                onError={onError}
                promptMode={promptMode}
                resetSignal={resetSignal}
                onHeightChange={(h) => setPreviewHeight(h)}
              />
            )}

            {session && (
              <div className="action-buttons">
                <button 
                  className="search-button"
                  onClick={() => setShowResults(true)}
                >
                  SEARCH
                </button>
                <button 
                  className="reset-button"
                  onClick={() => {
                    onReset();
                    setShowResults(false);
                    setPromptMode(null);
                  }}
                >
                  NEW IMAGE
                </button>
              </div>
            )}

            {session && (
              <div className="prompt-buttons">
                <button 
                  className={`prompt-button add-button ${promptMode === 'add' ? 'active' : ''}`}
                  onClick={() => setPromptMode('add')}
                >
                  ADD
                </button>
                <button 
                  className={`prompt-button remove-button ${promptMode === 'remove' ? 'active' : ''}`}
                  onClick={() => setPromptMode('remove')}
                >
                  REMOVE
                </button>
                <button 
                  className="prompt-button reset-prompt-button"
                  onClick={() => {
                    setResetSignal((v) => v + 1);
                    setPromptMode('add');
                  }}
                >
                  RESET
                </button>
              </div>
            )}
          </div>

          {showResults && (
            <div className="results-section" style={{ height: `calc(${previewHeight + 90}px - 6rem)` }}>
              <div className="results-list" ref={resultsListRef}>
                {demoBags.slice(0, 5).map((bag) => (
                  <div className="bag-card" key={bag.id}>
                    <img src={bag.imageUrl} alt={bag.name} />
                    <div className="bag-info">
                      <div className="bag-info-row">
                        <span className="bag-name">{bag.name}</span>
                        <span className="separator">|</span>
                        <span className="bag-brand">{bag.brand}</span>
                      </div>
                      <div className="bag-info-row">
                        <span className="bag-price">{bag.price.toLocaleString()}</span>
                        <span className="separator">|</span>
                        <span className="bag-type">{bag.bagType}</span>
                        <span className="separator">|</span>
                        <span className="bag-material">{bag.material}</span>
                        <span className="separator">|</span>
                        <button className="color-button" type="button">색상</button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <button
                className="results-arrow up"
                type="button"
                onClick={() => scrollResults('up')}
                aria-label="scroll up"
              />
              <button
                className="results-arrow down"
                type="button"
                onClick={() => scrollResults('down')}
                aria-label="scroll down"
              />
            </div>
          )}

          {showResults && (
            <div className="summary-section">
              <div className="bottom-gallery" ref={bottomGalleryRef}>
                <div className="gallery-track">
                  {demoBags.map((bag) => (
                    <div className="gallery-item" key={bag.id}>
                      <img src={bag.imageUrl} alt={bag.name} />
                    </div>
                  ))}
                </div>
              </div>
              <button 
                className="gallery-arrow left" 
                type="button" 
                onClick={() => scrollBottomGallery('left')} 
                aria-label="scroll left" 
              />
              <button 
                className="gallery-arrow right" 
                type="button" 
                onClick={() => scrollBottomGallery('right')} 
                aria-label="scroll right" 
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default BagPage;
