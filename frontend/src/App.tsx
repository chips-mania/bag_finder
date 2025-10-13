import React, { useState } from 'react';
import ImageUpload from './components/ImageUpload';
import ImagePreview from './components/ImagePreview';
import ErrorMessage from './components/ErrorMessage';
import type { SessionResponse } from './services/api';
import './App.css';

// Page components
import IntroductionPage from './pages/IntroductionPage';
import BagPage from './pages/BagPage';
import ShoesPage from './pages/ShoesPage';
import HeadwearPage from './pages/HeadwearPage';
import AccessoryPage from './pages/AccessoryPage';

type Page = 'introduction' | 'bag' | 'shoes' | 'headwear' | 'accessory';

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('introduction');
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [imageUrl, setImageUrl] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string>('');

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
          />
        );
      case 'shoes':
        return <ShoesPage />;
      case 'headwear':
        return <HeadwearPage />;
      case 'accessory':
        return <AccessoryPage />;
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
              FINDER
            </button>
            <button 
              className={`nav-main-item ${currentPage === 'bag' ? 'active' : ''}`}
              onClick={() => setCurrentPage('bag')}
            >
              BAG
            </button>
            <button 
              className={`nav-main-item ${currentPage === 'shoes' ? 'active' : ''}`}
              onClick={() => setCurrentPage('shoes')}
            >
              SHOES
            </button>
            <button 
              className={`nav-main-item ${currentPage === 'headwear' ? 'active' : ''}`}
              onClick={() => setCurrentPage('headwear')}
            >
              HEADWEAR
            </button>
            <button 
              className={`nav-main-item ${currentPage === 'accessory' ? 'active' : ''}`}
              onClick={() => setCurrentPage('accessory')}
            >
              ACCESSORY
            </button>
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
