import React, { useEffect, useState } from 'react';
import ErrorMessage from './components/ErrorMessage';
import { ONBOARDING_STORAGE_KEY } from './components/Onboarding';
import type { SessionResponse } from './services/api';
import { apiService } from './services/api';
import './App.css';

// Page components
import IntroductionPage from './pages/IntroductionPage';
import BagPage from './pages/BagPage';

type Page = 'introduction' | 'bag';

function readOnboardingComplete(): boolean {
  try {
    return localStorage.getItem(ONBOARDING_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

function App() {
  const [currentPage, setCurrentPage] = useState<Page>(() =>
    readOnboardingComplete() ? 'introduction' : 'bag'
  );
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [imageUrl, setImageUrl] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [onboardingComplete, setOnboardingComplete] = useState(readOnboardingComplete);
  const [onboardingOpen, setOnboardingOpen] = useState(() => !readOnboardingComplete());

  const handleSessionCreated = (newSession: SessionResponse, imageUrl: string) => {
    setSession(newSession);
    setImageUrl(imageUrl);
    setError('');
  };

  const handleError = (errorMessage: string) => {
    setError(errorMessage);
  };

  const handleCloseError = () => {
    setError('');
  };

  const handleReset = () => {
    setSession(null);
    setImageUrl('');
    setError('');
  };

  useEffect(() => {
    if (onboardingOpen) {
      setCurrentPage('bag');
    }
  }, [onboardingOpen]);

  const handleOnboardingFinished = () => {
    try {
      localStorage.setItem(ONBOARDING_STORAGE_KEY, '1');
    } catch {
      // ignore storage failures
    }
    setOnboardingComplete(true);
    setOnboardingOpen(false);
  };

  const handleSelectSample = async (src: string, filename: string) => {
    setIsLoading(true);
    setError('');
    try {
      const response = await fetch(src);
      if (!response.ok) {
        throw new Error('샘플 이미지를 불러오지 못했습니다.');
      }
      const blob = await response.blob();
      const file = new File([blob], filename, { type: blob.type || 'image/jpeg' });
      const newSession = await apiService.createSession(file);
      const url = URL.createObjectURL(blob);
      handleSessionCreated(newSession, url);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as Error).message ??
        '샘플 이미지 업로드 중 오류가 발생했습니다.';
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const renderPage = () => {
    switch (currentPage) {
      case 'introduction':
        return <IntroductionPage />;
      case 'bag':
        return (
          <BagPage
            session={session}
            imageUrl={imageUrl}
            isLoading={isLoading}
            onSessionCreated={handleSessionCreated}
            onError={handleError}
            onReset={handleReset}
            onboardingOpen={onboardingOpen}
            onSelectSample={handleSelectSample}
            onOnboardingFinished={handleOnboardingFinished}
          />
        );
      default:
        return <IntroductionPage />;
    }
  };

  return (
    <div className="app">
      <nav className="navigation">
        <div className="nav-left">
          <div className="nav-brand-small">STYLE FINDER</div>
          <div className="nav-main">
            <button 
              className={`nav-main-item ${currentPage === 'introduction' ? 'active' : ''}`}
              onClick={() => setCurrentPage('introduction')}
            >
              HOME
            </button>
            <button 
              className={`nav-main-item ${currentPage === 'bag' ? 'active' : ''}`}
              onClick={() => setCurrentPage('bag')}
            >
              BAG
            </button>
            {onboardingComplete && (
              <button
                className={`nav-main-item ${onboardingOpen ? 'active' : ''}`}
                onClick={() => setOnboardingOpen(true)}
              >
                GUIDE
              </button>
            )}
          </div>
        </div>
      </nav>

      <main className="app-main">
        {renderPage()}
      </main>

      {error && (
        <ErrorMessage
          message={error}
          onClose={handleCloseError}
        />
      )}
    </div>
  );
}

export default App;
