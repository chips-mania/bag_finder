import React, { useState } from 'react';
import ImageUpload from './components/ImageUpload';
import ImagePreview from './components/ImagePreview';
import ErrorMessage from './components/ErrorMessage';
// import { apiService } from '../services/api';
import type { SessionResponse } from './services/api';
import './App.css';

function App() {
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

  return (
    <div className="app">

      <main className={`app-main ${!session ? 'upload-mode' : 'preview-mode'}`}>
        {!session ? (
          <ImageUpload
            onSessionCreated={handleSessionCreated}
            onError={handleError}
            isLoading={isLoading}
          />
        ) : (
          <ImagePreview
            session={session}
            imageUrl={imageUrl}
            onError={handleError}
          />
        )}

        {session && (
          <div className="action-buttons">
            <button 
              className="reset-button"
              onClick={handleReset}
            >
              NEW IMAGE
            </button>
          </div>
        )}
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
