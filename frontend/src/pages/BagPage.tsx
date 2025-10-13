import React, { useState } from 'react';
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
            <div className="results-section">
              <div className="results-grid">
                {/* 분석 결과가 여기에 표시됩니다 */}
              </div>
            </div>
          )}

          {showResults && (
            <div className="summary-section">
              {/* 추가 정보/요약 상자 (업로드+추천 박스 전체 가로폭과 동일) */}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default BagPage;
