import axios from 'axios';

function resolveApiBaseUrl(): string {
  const raw = import.meta.env.VITE_API_URL?.trim();
  if (!raw) return 'http://127.0.0.1:8000';
  const withoutSlash = raw.replace(/\/$/, '');
  if (/^https?:\/\//i.test(withoutSlash)) return withoutSlash;
  return `https://${withoutSlash}`;
}

const API_BASE_URL = resolveApiBaseUrl();

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
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

export interface BagResult {
  bag_id: string;
  brand: string | null;
  bag_name: string | null;
  price: number | null;
  material: string | null;
  color: string | null;  // JSON 문자열
  category: string | null;
  thumbnail: string | null;
  link: string | null;
  similarity: number;  // 유사도 (0~1)
}

export interface SearchResponse {
  top5: BagResult[];
  gallery10: BagResult[];
}

export interface FilterSearchRequest {
  selected_categories: string[];
  selected_colors: string[];
  min_price: number;
  max_price: number;
  page: number;
  limit: number;
}

export interface SimilarityFilterSearchRequest {
  session_id: string;
  selected_categories: string[];
  selected_colors: string[];
  min_price: number;
  max_price: number;
  page: number;
  limit: number;
}

export interface FilterSearchResponse {
  results: BagResult[];
  total_count: number;
  total_pages: number;
  current_page: number;
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
      timeout: 180000,
    });
    return response.data;
  },

  // 🔍 유사 가방 검색
  searchBags: async (sessionId: string, selectedColors: string[] = []): Promise<SearchResponse> => {
    const payload = { 
      session_id: sessionId,
      selected_colors: selectedColors
    };
    const response = await api.post<SearchResponse>('/search', payload, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  },

  // 🔍 필터 검색
  filterSearchBags: async (
    selectedCategories: string[] = [],
    selectedColors: string[] = [],
    minPrice: number = 4900,
    maxPrice: number = 1500000,
    page: number = 1,
    limit: number = 10
  ): Promise<FilterSearchResponse> => {
    const payload: FilterSearchRequest = {
      selected_categories: selectedCategories,
      selected_colors: selectedColors,
      min_price: minPrice,
      max_price: maxPrice,
      page: page,
      limit: limit
    };
    const response = await api.post<FilterSearchResponse>('/filter-search', payload, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  },

  filterSearchBagsWithSimilarity: async (
    sessionId: string,
    selectedCategories: string[] = [],
    selectedColors: string[] = [],
    minPrice: number = 4900,
    maxPrice: number = 1500000,
    page: number = 1,
    limit: number = 10
  ): Promise<FilterSearchResponse> => {
    const payload: SimilarityFilterSearchRequest = {
      session_id: sessionId,
      selected_categories: selectedCategories,
      selected_colors: selectedColors,
      min_price: minPrice,
      max_price: maxPrice,
      page: page,
      limit: limit
    };
    const response = await api.post<FilterSearchResponse>('/filter-search-with-similarity', payload, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.data;
  },
};

export default api;
