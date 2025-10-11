import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { apiService } from '../services/api';
import type { SessionResponse } from '../services/api';
import './ImageUpload.css';

interface ImageUploadProps {
  onSessionCreated: (session: SessionResponse, imageUrl: string) => void;
  onError: (error: string) => void;
  isLoading: boolean;
}

const ImageUpload: React.FC<ImageUploadProps> = ({
  onSessionCreated,
  onError,
  isLoading,
}) => {
  const [dragActive, setDragActive] = useState(false);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    
    // 파일 유효성 검사
    if (!file.type.startsWith('image/')) {
      onError('이미지 파일만 업로드할 수 있습니다.');
      return;
    }

    if (file.size > 15 * 1024 * 1024) { // 15MB
      onError('파일 크기는 15MB를 초과할 수 없습니다.');
      return;
    }

    try {
      const session = await apiService.createSession(file);
      const imageUrl = URL.createObjectURL(file);
      onSessionCreated(session, imageUrl);
    } catch (error: unknown) {
      const msg =
        (error as any)?.response?.data?.detail ??
        (error as Error).message ??
        '이미지 업로드 중 오류가 발생했습니다.';
      onError(msg);
    }
  
  }, [onSessionCreated, onError]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png', '.webp']
    },
    multiple: false,
    disabled: isLoading,
    onDragEnter: () => setDragActive(true),
    onDragLeave: () => setDragActive(false),
  });

  return (
    <div className="image-upload-container">
      <div
        {...getRootProps()}
        className={`dropzone ${isDragActive || dragActive ? 'active' : ''} ${isLoading ? 'loading' : ''}`}
      >
        <input {...getInputProps()} />
        
        {isLoading ? (
          <div className="loading-content">
            <div className="spinner"></div>
            <p>이미지를 처리하고 있습니다...</p>
          </div>
        ) : (
          <div className="upload-content">
            <h3>UPLOAD</h3>
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageUpload;
