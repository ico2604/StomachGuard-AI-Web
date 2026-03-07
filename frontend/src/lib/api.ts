/**
 * API 클라이언트
 * 백엔드 API와의 모든 통신을 담당
 * v3: Celery 비동기 태스크 폴링 지원
 */

import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

// Axios 인스턴스 생성
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 요청 인터셉터: 토큰 자동 첨부
apiClient.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 응답 인터셉터: 401 에러 시 토큰 제거 + reject (리다이렉트는 layout.tsx에서 처리)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      console.log('[API] 401 Unauthorized:', url);
      // 로그인 요청 자체가 아닌 경우에만 토큰 제거
      if (!url.includes('/auth/login')) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          localStorage.removeItem('user');
        }
      }
    }
    return Promise.reject(error);
  }
);

// ==================== 폴링 유틸리티 ====================

interface TaskResult<T = any> {
  task_id: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  message?: string;
  result?: T;
}

/**
 * Celery 태스크 결과를 폴링하는 유틸리티
 *
 * @param pollUrl - 폴링할 URL (예: /clinical/diagnose/{task_id})
 * @param options - 폴링 옵션
 * @returns 완료된 태스크 결과
 */
async function pollTaskResult<T = any>(
  pollUrl: string,
  options: {
    intervalMs?: number;      // 폴링 간격 (기본 1500ms)
    maxAttempts?: number;     // 최대 시도 횟수 (기본 120 = 3분)
    onProgress?: (status: string, message: string) => void;
  } = {}
): Promise<TaskResult<T>> {
  const { intervalMs = 1500, maxAttempts = 120, onProgress } = options;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await apiClient.get<TaskResult<T>>(pollUrl);
    const data = response.data;

    if (onProgress) {
      onProgress(data.status, data.message || '');
    }

    if (data.status === 'COMPLETED') {
      return data;
    }

    if (data.status === 'FAILED') {
      throw new Error(data.message || 'AI 진단 태스크가 실패했습니다.');
    }

    // PENDING, PROCESSING 상태이면 대기 후 재시도
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error('AI 진단 태스크 응답 시간이 초과되었습니다.');
}

// ==================== API 함수 ====================

const api = {
  // ==================== 인증 ====================

  /** 로그인 (OAuth2 form 형식) */
  login: async (username: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await apiClient.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
  },

  /** 현재 사용자 정보 조회 */
  getCurrentUser: async () => {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },

  // ==================== 환자 관리 ====================

  /** 환자 목록 조회 */
  getPatients: async () => {
    const response = await apiClient.get('/patients/');
    return response.data;
  },

  /** 환자 등록 */
  createPatient: async (data: any) => {
    const response = await apiClient.post('/patients/', data);
    return response.data;
  },

  /** 환자 상세 조회 */
  getPatient: async (patientId: number) => {
    const response = await apiClient.get(`/patients/${patientId}`);
    return response.data;
  },

  // ==================== 진료 기록 ====================

  /** 진료 내역 조회 */
  getVisits: async (params?: Record<string, any>) => {
    const response = await apiClient.get('/visits/', {
      params,
      maxRedirects: 0,
    });
    return response.data;
  },

  /** 진료 기록 생성 */
  createVisit: async (data: any) => {
    const response = await apiClient.post('/visits/', data);
    return response.data;
  },

  /** 진료 기록 상세 조회 */
  getVisit: async (visitId: number) => {
    const response = await apiClient.get(`/visits/${visitId}`);
    return response.data;
  },

  // ==================== AI 진단 (비동기 Celery) ====================

  /**
   * 통합 진료 워크플로우 (비동기)
   *
   * 1. POST /clinical/diagnose → task_id 수신
   * 2. GET /clinical/diagnose/{task_id} → 폴링
   * 3. COMPLETED 시 결과 반환
   *
   * @param formData - patient_id, chief_complaint, image
   * @param onProgress - 진행 상태 콜백
   * @returns 기존과 동일한 DiagnosisResult 포맷
   */
  diagnose: async (
    formData: FormData,
    onProgress?: (status: string, message: string) => void
  ) => {
    // 1단계: 태스크 제출
    const submitResponse = await apiClient.post('/clinical/diagnose', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    const { task_id } = submitResponse.data;

    if (onProgress) {
      onProgress('PENDING', 'AI 진단 태스크가 제출되었습니다...');
    }

    // 2단계: 결과 폴링
    const taskResult = await pollTaskResult(
      `/clinical/diagnose/${task_id}`,
      {
        intervalMs: 1500,
        maxAttempts: 120,
        onProgress,
      }
    );

    // 3단계: 결과 반환 (기존 동기 API와 동일한 포맷)
    return taskResult.result;
  },

  /**
   * AI 예측 단독 (비동기)
   * 인증 없이 이미지만 업로드하여 예측
   */
  predictImage: async (
    file: File,
    onProgress?: (status: string, message: string) => void
  ) => {
    const formData = new FormData();
    formData.append('file', file);

    const submitResponse = await apiClient.post('/ai/predict', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    const { task_id } = submitResponse.data;

    const taskResult = await pollTaskResult(`/ai/tasks/${task_id}`, {
      intervalMs: 1500,
      maxAttempts: 120,
      onProgress,
    });

    return taskResult.result;
  },

  /** AI 태스크 상태 조회 (수동 폴링용) */
  getTaskStatus: async (taskId: string) => {
    const response = await apiClient.get(`/ai/tasks/${taskId}`);
    return response.data;
  },

  /** AI 모델 정보 조회 */
  getModelInfo: async () => {
    const response = await apiClient.get('/ai/model-info');
    return response.data;
  },

  // ==================== 진단 결과 ====================

  /** 진단 결과 목록 조회 */
  getDiagnoses: async (params?: Record<string, any>) => {
    const response = await apiClient.get('/diagnoses/', { params });
    return response.data;
  },

  /** 진단 결과 상세 조회 */
  getDiagnosis: async (diagnosisId: number) => {
    const response = await apiClient.get(`/diagnoses/${diagnosisId}`);
    return response.data;
  },

  // ==================== 통계 ====================

  /** 임상 통계 (대시보드) */
  getStats: async () => {
    const response = await apiClient.get('/clinical/stats');
    return response.data;
  },
};

export default api;
