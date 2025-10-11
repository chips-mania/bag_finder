import React from 'react';
import './ErrorMessage.css';

interface ErrorMessageProps {
  message: string;
  onClose: () => void;
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({ message, onClose }) => {
  return (
    <div className="error-message">
      <div className="error-content">
        <div className="error-icon">⚠️</div>
        <div className="error-text">
          <h4>오류가 발생했습니다</h4>
          <p>{message}</p>
        </div>
        <button className="close-button" onClick={onClose}>
          ✕
        </button>
      </div>
    </div>
  );
};

export default ErrorMessage;
