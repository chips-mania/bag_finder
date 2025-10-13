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
  const [promptMode, setPromptMode] = useState<'add' | 'remove' | null>(null);
  return (
    <div className="bag-page">
      <div className="bag-header">
        <h1>BAG FINDER</h1>
      </div>

      <main className={`bag-main ${!session ? 'upload-mode' : 'preview-mode'}`}>
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
                  onClick={() => setPromptMode(promptMode === 'add' ? null : 'add')}
                >
                  영역더하기
                </button>
                <button 
                  className={`prompt-button remove-button ${promptMode === 'remove' ? 'active' : ''}`}
                  onClick={() => setPromptMode(promptMode === 'remove' ? null : 'remove')}
                >
                  영역빼기
                </button>
                <button 
                  className="prompt-button reset-prompt-button"
                  onClick={() => setPromptMode(null)}
                >
                  초기화
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
        </div>
      </main>
    </div>
  );
};

export default BagPage;
