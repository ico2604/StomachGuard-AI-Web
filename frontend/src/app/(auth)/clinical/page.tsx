/**
 * AI 진단 페이지 - Celery 비동기 폴링 버전
 *
 * 1. 환자 선택 + 이미지 업로드 + POST 제출
 * 2. task_id 수신 후 폴링 (1.5초 간격)
 * 3. COMPLETED 시 결과 표시 (세그멘테이션 비교 뷰)
 */

'use client';

import { useState, useEffect, Suspense, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import api from '@/lib/api';
import Navbar from '@/components/Navbar';
import LoadingSpinner from '@/components/LoadingSpinner';
import ErrorMessage from '@/components/ErrorMessage';

interface Patient {
  id: number;
  patient_number: string;
  name: string;
}

interface DiagnosisResult {
  visit: {
    id: number;
    visit_date: string;
    patient_name: string;
    patient_number: string;
    chief_complaint: string;
    status: string;
  };
  diagnosis: {
    id: number;
    prediction: string;
    prediction_kr: string;
    confidence: number;
    probabilities_kr: { [key: string]: number };
  };
  segmentation: {
    original_base64: string;
    overlay_base64: string;
    mask_base64: string;
    ratios: { [key: string]: number };
    class_colors: { [key: string]: number[] };
    class_names_kr: { [key: string]: string };
  };
  processing_time: number;
}

// 세그멘테이션 클래스별 색상 정의
const SEG_LEGEND = [
  { key: 'tumor', label: '종양 (Tumor)', color: 'rgb(255,0,0)', bg: 'bg-red-500' },
  { key: 'stroma', label: '기질 (Stroma)', color: 'rgb(0,255,0)', bg: 'bg-green-500' },
  { key: 'normal', label: '정상 (Normal)', color: 'rgb(0,0,255)', bg: 'bg-blue-600' },
  { key: 'immune', label: '면역세포 (Immune)', color: 'rgb(255,255,0)', bg: 'bg-yellow-400' },
  { key: 'background', label: '배경 (Background)', color: 'rgb(0,0,0)', bg: 'bg-gray-900' },
];

// 폴링 상태 메시지 맵
const STATUS_MESSAGES: Record<string, string> = {
  PENDING: '태스크가 대기 중입니다...',
  PROCESSING: 'AI 모델이 이미지를 분석하고 있습니다...',
  COMPLETED: '진단이 완료되었습니다.',
  FAILED: '진단에 실패했습니다.',
};

function ClinicalContent() {
  const searchParams = useSearchParams();
  const preSelectedPatientId = searchParams.get('patient_id');

  const [patients, setPatients] = useState<Patient[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [chiefComplaint, setChiefComplaint] = useState('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<DiagnosisResult | null>(null);
  const [viewMode, setViewMode] = useState<'overlay' | 'mask' | 'side-by-side'>('overlay');

  // 폴링 상태 UI
  const [pollingStatus, setPollingStatus] = useState('');
  const [pollingMessage, setPollingMessage] = useState('');
  const [pollingDots, setPollingDots] = useState('');
  const pollingInterval = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    fetchPatients();
    return () => {
      if (pollingInterval.current) clearInterval(pollingInterval.current);
    };
  }, []);

  useEffect(() => {
    if (preSelectedPatientId) {
      setSelectedPatientId(preSelectedPatientId);
    }
  }, [preSelectedPatientId]);

  // 폴링 중 점 애니메이션
  useEffect(() => {
    if (!loading) {
      setPollingDots('');
      return;
    }
    const interval = setInterval(() => {
      setPollingDots((prev) => (prev.length >= 3 ? '' : prev + '.'));
    }, 500);
    return () => clearInterval(interval);
  }, [loading]);

  const fetchPatients = async () => {
    try {
      const data = await api.getPatients();
      setPatients(data);
    } catch (err: any) {
      setError('환자 목록을 불러오는데 실패했습니다.');
    }
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setImageFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleDiagnose = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId) { setError('환자를 선택해주세요.'); return; }
    if (!imageFile) { setError('이미지를 선택해주세요.'); return; }

    try {
      setLoading(true);
      setError('');
      setResult(null);
      setPollingStatus('PENDING');
      setPollingMessage('AI 진단 태스크 제출 중...');

      const formData = new FormData();
      formData.append('patient_id', selectedPatientId);
      formData.append('chief_complaint', chiefComplaint || '정기 검진');
      formData.append('image', imageFile);

      // 비동기 폴링 방식 호출 (onProgress 콜백으로 상태 업데이트)
      const response = await api.diagnose(formData, (status, message) => {
        setPollingStatus(status);
        setPollingMessage(message || STATUS_MESSAGES[status] || status);
      });

      setResult(response);
      setPollingStatus('COMPLETED');
      setPollingMessage('진단이 완료되었습니다.');
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'AI 진단에 실패했습니다.';
      setError(detail);
      setPollingStatus('FAILED');
      setPollingMessage(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setImageFile(null);
    setImagePreview('');
    setChiefComplaint('');
    setError('');
    setViewMode('overlay');
    setPollingStatus('');
    setPollingMessage('');
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.5) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getConfidenceBarColor = (confidence: number) => {
    if (confidence >= 0.8) return 'bg-green-500';
    if (confidence >= 0.5) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <h1 className="text-3xl font-bold text-gray-900 mb-6">AI 진단</h1>

          {error && <ErrorMessage message={error} />}

          {/* ===== 진단 폼 ===== */}
          {!result && (
            <div className="bg-white shadow-md rounded-lg p-6">
              <form onSubmit={handleDiagnose} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">환자 선택</label>
                  <select
                    value={selectedPatientId}
                    onChange={(e) => setSelectedPatientId(e.target.value)}
                    required
                    disabled={loading}
                    className="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
                  >
                    <option value="">환자를 선택하세요</option>
                    {patients.map((patient) => (
                      <option key={patient.id} value={patient.id}>
                        {patient.patient_number} - {patient.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">주증상 (선택사항)</label>
                  <textarea
                    value={chiefComplaint}
                    onChange={(e) => setChiefComplaint(e.target.value)}
                    rows={3}
                    disabled={loading}
                    placeholder="예: 복통, 소화불량, 정기 검진 등"
                    className="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">세포 현미경 이미지</label>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleImageChange}
                    required
                    disabled={loading}
                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 disabled:opacity-50"
                  />
                </div>

                {imagePreview && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">미리보기</p>
                    <img src={imagePreview} alt="Preview" className="max-w-md rounded-lg border border-gray-300" />
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-4 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? 'AI 진단 처리 중...' : 'AI 진단 시작'}
                </button>
              </form>

              {/* ===== 폴링 상태 표시 ===== */}
              {loading && (
                <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-6">
                  <div className="flex flex-col items-center">
                    {/* 스피너 */}
                    <div className="relative">
                      <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <svg className="w-6 h-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                      </div>
                    </div>

                    {/* 상태 */}
                    <div className="mt-4 text-center">
                      <div className="flex items-center gap-2 justify-center mb-2">
                        <span className={`inline-block w-2.5 h-2.5 rounded-full ${
                          pollingStatus === 'PROCESSING' ? 'bg-yellow-400 animate-pulse' :
                          pollingStatus === 'PENDING' ? 'bg-gray-400 animate-pulse' :
                          'bg-blue-400 animate-pulse'
                        }`}></span>
                        <span className="text-sm font-medium text-blue-800">
                          {pollingStatus === 'PROCESSING' ? '분석 중' :
                           pollingStatus === 'PENDING' ? '대기 중' : '처리 중'}
                        </span>
                      </div>
                      <p className="text-gray-600 text-sm">
                        {pollingMessage}{pollingDots}
                      </p>
                      <p className="text-xs text-gray-400 mt-2">
                        Celery 워커가 AI 모델로 이미지를 분석하고 있습니다.
                      </p>
                    </div>

                    {/* 진행 바 */}
                    <div className="w-full max-w-md mt-4">
                      <div className="h-1.5 bg-blue-100 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-600 rounded-full animate-pulse" style={{ width: pollingStatus === 'PROCESSING' ? '70%' : '30%' }}></div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ===== 진단 결과 ===== */}
          {result && (
            <div className="space-y-6">
              {/* 환자 정보 + 분류 결과 */}
              <div className="bg-white shadow-md rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-bold text-gray-900">진단 결과</h2>
                  <span className="text-sm text-gray-500">처리 시간: {result.processing_time.toFixed(3)}초</span>
                </div>

                {/* 환자 정보 */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <p className="text-xs text-gray-500">환자명</p>
                    <p className="text-base font-semibold">{result.visit.patient_name}</p>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <p className="text-xs text-gray-500">환자 번호</p>
                    <p className="text-base font-semibold">{result.visit.patient_number}</p>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <p className="text-xs text-gray-500">진료 ID</p>
                    <p className="text-base font-semibold">#{result.visit.id}</p>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <p className="text-xs text-gray-500">진단 ID</p>
                    <p className="text-base font-semibold">#{result.diagnosis.id}</p>
                  </div>
                </div>

                {/* 주 진단 결과 */}
                <div className="bg-blue-50 border-l-4 border-blue-600 p-4 mb-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">AI 분류 결과</p>
                      <p className="text-2xl font-bold text-blue-900 mt-1">{result.diagnosis.prediction_kr}</p>
                      <p className="text-sm text-gray-500">({result.diagnosis.prediction})</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-gray-600">신뢰도</p>
                      <p className={`text-3xl font-bold ${getConfidenceColor(result.diagnosis.confidence)}`}>
                        {(result.diagnosis.confidence * 100).toFixed(1)}%
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 w-full bg-gray-200 rounded-full h-3">
                    <div
                      className={`${getConfidenceBarColor(result.diagnosis.confidence)} h-3 rounded-full transition-all`}
                      style={{ width: `${result.diagnosis.confidence * 100}%` }}
                    ></div>
                  </div>
                </div>

                {/* 클래스별 확률 */}
                {result.diagnosis.probabilities_kr && (
                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">클래스별 확률</p>
                    <div className="space-y-2">
                      {Object.entries(result.diagnosis.probabilities_kr)
                        .sort(([, a], [, b]) => b - a)
                        .map(([cls, prob]) => (
                          <div key={cls}>
                            <div className="flex justify-between text-sm mb-1">
                              <span className={prob === result.diagnosis.confidence ? 'font-bold text-blue-700' : ''}>{cls}</span>
                              <span className="font-medium">{(prob * 100).toFixed(2)}%</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div
                                className={`h-2 rounded-full ${prob === result.diagnosis.confidence ? 'bg-blue-600' : 'bg-gray-400'}`}
                                style={{ width: `${prob * 100}%` }}
                              ></div>
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>

              {/* ===== 세그멘테이션 비교 뷰 ===== */}
              {result.segmentation && (
                <div className="bg-white shadow-md rounded-lg p-6">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">조직 세그멘테이션 분석</h3>

                  {/* 뷰 모드 전환 */}
                  <div className="flex gap-2 mb-4">
                    {(['overlay', 'mask', 'side-by-side'] as const).map((mode) => (
                      <button
                        key={mode}
                        onClick={() => setViewMode(mode)}
                        className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                          viewMode === mode ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                        }`}
                      >
                        {mode === 'overlay' ? '오버레이' : mode === 'mask' ? '세그멘테이션 마스크' : '나란히 비교'}
                      </button>
                    ))}
                  </div>

                  {/* 이미지 비교 영역 */}
                  <div className="bg-gray-900 rounded-lg p-4">
                    {viewMode === 'side-by-side' ? (
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {[
                          { label: '원본', key: 'original_base64' },
                          { label: '오버레이', key: 'overlay_base64' },
                          { label: '세그 마스크', key: 'mask_base64' },
                        ].map((item) => (
                          <div key={item.key}>
                            <p className="text-white text-sm font-medium mb-2 text-center">{item.label}</p>
                            {(result.segmentation as any)[item.key] ? (
                              <img
                                src={`data:image/png;base64,${(result.segmentation as any)[item.key]}`}
                                alt={item.label}
                                className="w-full rounded-lg"
                              />
                            ) : (
                              imagePreview ? (
                                <img src={imagePreview} alt={item.label} className="w-full rounded-lg" />
                              ) : (
                                <div className="w-full aspect-square bg-gray-800 rounded-lg flex items-center justify-center">
                                  <p className="text-gray-400 text-sm">DEMO</p>
                                </div>
                              )
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <p className="text-white text-sm font-medium mb-2 text-center">원본 이미지</p>
                          {result.segmentation.original_base64 ? (
                            <img src={`data:image/png;base64,${result.segmentation.original_base64}`} alt="Original" className="w-full rounded-lg" />
                          ) : imagePreview ? (
                            <img src={imagePreview} alt="Original" className="w-full rounded-lg" />
                          ) : null}
                        </div>
                        <div>
                          <p className="text-white text-sm font-medium mb-2 text-center">
                            {viewMode === 'overlay' ? 'AI 세그멘테이션 오버레이' : '세그멘테이션 마스크'}
                          </p>
                          {(viewMode === 'overlay' ? result.segmentation.overlay_base64 : result.segmentation.mask_base64) ? (
                            <img
                              src={`data:image/png;base64,${viewMode === 'overlay' ? result.segmentation.overlay_base64 : result.segmentation.mask_base64}`}
                              alt={viewMode}
                              className="w-full rounded-lg"
                            />
                          ) : (
                            <div className="w-full aspect-square bg-gray-800 rounded-lg flex items-center justify-center">
                              <p className="text-gray-400 text-sm">DEMO 모드 - 모델 파일 필요</p>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* 색상 범례 */}
                  <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                    <p className="text-sm font-medium text-gray-700 mb-3">색상 범례</p>
                    <div className="flex flex-wrap gap-4">
                      {SEG_LEGEND.map((item) => (
                        <div key={item.key} className="flex items-center gap-2">
                          <div className={`w-4 h-4 rounded ${item.bg}`}></div>
                          <span className="text-sm text-gray-700">{item.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* 조직 비율 */}
                  {result.segmentation.ratios && (
                    <div className="mt-4">
                      <p className="text-sm font-medium text-gray-700 mb-3">조직 구성 비율</p>
                      <div className="w-full h-8 rounded-full overflow-hidden flex mb-4">
                        {SEG_LEGEND.filter((item) => item.key !== 'background').map((item) => {
                          const ratio = result.segmentation.ratios[item.key] || 0;
                          if (ratio < 0.001) return null;
                          return (
                            <div
                              key={item.key}
                              className={`${item.bg} h-full relative group`}
                              style={{ width: `${ratio * 100}%` }}
                              title={`${item.label}: ${(ratio * 100).toFixed(1)}%`}
                            >
                              {ratio > 0.08 && (
                                <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-white drop-shadow-lg">
                                  {(ratio * 100).toFixed(1)}%
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                        {SEG_LEGEND.map((item) => {
                          const ratio = result.segmentation.ratios[item.key] || 0;
                          return (
                            <div key={item.key} className="bg-white border border-gray-200 p-3 rounded-lg text-center shadow-sm">
                              <div className="flex items-center justify-center gap-2 mb-1">
                                <div className={`w-3 h-3 rounded-sm ${item.bg}`}></div>
                                <p className="text-xs text-gray-500">{item.label.split(' (')[0]}</p>
                              </div>
                              <p className="text-xl font-bold text-gray-900">{(ratio * 100).toFixed(1)}%</p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* 새 진단 버튼 */}
              <button
                onClick={handleReset}
                className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded-lg transition-colors"
              >
                새 진단 시작
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ClinicalPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <ClinicalContent />
    </Suspense>
  );
}
