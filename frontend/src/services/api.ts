import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30초 타임아웃
});

// 요청 인터셉터
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// 응답 인터셉터
api.interceptors.response.use(
  (response) => {
    console.log(`API Response: ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export interface SessionResponse {
  session_id: string;
  image_info: {
    width: number;
    height: number;
    format: string;
  };
}

export interface SessionInfo {
  session_id: string;
  timestamp: string;
  mask_count: number;
  is_expired: boolean;
}

export interface PredictResponse {
  contours: number[][][];  // 각 컨투어 폴리라인의 [x,y] 좌표들
  width: number;           // 서버 기준 크기
  height: number;          // 서버 기준 크기
  iou: number | null;
}

export const apiService = {
  // 세션 생성 (이미지 업로드)
  createSession: async (file: File): Promise<SessionResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post<SessionResponse>('/session', formData);
    return response.data;
  },

  // 세션 정보 조회
  getSessionInfo: async (sessionId: string): Promise<SessionInfo> => {
    const response = await api.get<SessionInfo>(`/session/${sessionId}`);
    return response.data;
  },

  // 세션 삭제
  deleteSession: async (sessionId: string): Promise<void> => {
    await api.delete(`/session/${sessionId}`);
  },

  // 헬스 체크
  healthCheck: async () => {
    const response = await api.get('/health');
    return response.data;
  },

  // ✅ 마스크 예측 (JSON 방식)
  predictMask: async (
    sessionId: string, 
    points: number[][], 
    labels: number[]
  ): Promise<PredictResponse> => {
    const payload = {
      session_id: sessionId,
      points,
      labels,
    };

    const response = await api.post<PredictResponse>('/predict', payload, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  },
};

export default api;
