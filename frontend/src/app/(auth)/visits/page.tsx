/**
 * 진료 내역 페이지
 * 진료 내역 목록 조회, 필터링, 상세 보기 (AI 진단 결과 + 세그멘테이션 비율 포함)
 */

'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import Navbar from '@/components/Navbar';
import LoadingSpinner from '@/components/LoadingSpinner';
import ErrorMessage from '@/components/ErrorMessage';

interface VisitDiagnosis {
  id: number;
  prediction: string;
  prediction_kr: string;
  confidence: number;
  probabilities_kr?: { [key: string]: number };
  tumor_ratio?: number;
  stroma_ratio?: number;
  normal_ratio?: number;
  immune_ratio?: number;
  background_ratio?: number;
  model_type?: string;
  processing_time?: number;
  is_reviewed?: number;
  created_at?: string;
}

interface Visit {
  id: number;
  visit_date: string;
  patient: {
    id: number;
    name: string;
    patient_number: string;
  } | null;
  doctor: {
    id: number;
    full_name: string;
    username: string;
  } | null;
  chief_complaint: string;
  diagnosis_summary: string;
  status: string;
  diagnosis: VisitDiagnosis | null;
  created_at: string;
}

// 세그멘테이션 클래스 색상 정의
const SEG_LEGEND = [
  { key: 'tumor', label: '종양', color: 'bg-red-500', textColor: 'text-red-600' },
  { key: 'stroma', label: '기질', color: 'bg-green-500', textColor: 'text-green-600' },
  { key: 'normal', label: '정상', color: 'bg-blue-600', textColor: 'text-blue-600' },
  { key: 'immune', label: '면역세포', color: 'bg-yellow-400', textColor: 'text-yellow-600' },
  { key: 'background', label: '배경', color: 'bg-gray-900', textColor: 'text-gray-600' },
];

export default function VisitsPage() {
  const router = useRouter();
  const [visits, setVisits] = useState<Visit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedVisit, setSelectedVisit] = useState<Visit | null>(null);

  // 필터 상태
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterSearch, setFilterSearch] = useState('');

  useEffect(() => {
    fetchVisits();
  }, []);

  const fetchVisits = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await api.getVisits();
      setVisits(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || '진료 내역을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 필터링된 진료 내역
  const filteredVisits = visits.filter((visit) => {
    // 상태 필터
    if (filterStatus && visit.status !== filterStatus) return false;
    // 검색 필터 (환자명, 환자번호, 담당의, 진단명)
    if (filterSearch) {
      const search = filterSearch.toLowerCase();
      const matchPatient = visit.patient?.name?.toLowerCase().includes(search);
      const matchNumber = visit.patient?.patient_number?.toLowerCase().includes(search);
      const matchDoctor = visit.doctor?.full_name?.toLowerCase().includes(search);
      const matchDiagnosis = visit.diagnosis?.prediction_kr?.toLowerCase().includes(search);
      const matchComplaint = visit.chief_complaint?.toLowerCase().includes(search);
      if (!matchPatient && !matchNumber && !matchDoctor && !matchDiagnosis && !matchComplaint) return false;
    }
    return true;
  });

  const statusBadge = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <span className="px-2.5 py-0.5 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">완료</span>;
      case 'PENDING':
        return <span className="px-2.5 py-0.5 inline-flex text-xs leading-5 font-semibold rounded-full bg-yellow-100 text-yellow-800">대기</span>;
      case 'CANCELLED':
        return <span className="px-2.5 py-0.5 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">취소</span>;
      default:
        return <span className="px-2.5 py-0.5 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">{status}</span>;
    }
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

  // 세그멘테이션 비율 가져오기
  const getSegRatio = (diagnosis: VisitDiagnosis, key: string): number => {
    switch (key) {
      case 'tumor': return diagnosis.tumor_ratio || 0;
      case 'stroma': return diagnosis.stroma_ratio || 0;
      case 'normal': return diagnosis.normal_ratio || 0;
      case 'immune': return diagnosis.immune_ratio || 0;
      case 'background': return diagnosis.background_ratio || 0;
      default: return 0;
    }
  };

  // 통계 카운트
  const totalCount = visits.length;
  const completedCount = visits.filter(v => v.status === 'COMPLETED').length;
  const pendingCount = visits.filter(v => v.status === 'PENDING').length;
  const diagnosedCount = visits.filter(v => v.diagnosis !== null).length;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-3xl font-bold text-gray-900">진료 내역</h1>
            <button
              onClick={() => router.push('/clinical')}
              className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg text-sm"
            >
              + 새 AI 진단
            </button>
          </div>

          {error && <ErrorMessage message={error} onRetry={fetchVisits} />}

          {/* 통계 요약 카드 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-blue-500">
              <p className="text-xs text-gray-500 uppercase">전체 진료</p>
              <p className="text-2xl font-bold text-gray-900">{totalCount}</p>
            </div>
            <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-green-500">
              <p className="text-xs text-gray-500 uppercase">완료</p>
              <p className="text-2xl font-bold text-green-600">{completedCount}</p>
            </div>
            <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-yellow-500">
              <p className="text-xs text-gray-500 uppercase">대기</p>
              <p className="text-2xl font-bold text-yellow-600">{pendingCount}</p>
            </div>
            <div className="bg-white rounded-lg shadow-sm p-4 border-l-4 border-purple-500">
              <p className="text-xs text-gray-500 uppercase">AI 진단 완료</p>
              <p className="text-2xl font-bold text-purple-600">{diagnosedCount}</p>
            </div>
          </div>

          {/* 필터 영역 */}
          <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1">
                <input
                  type="text"
                  value={filterSearch}
                  onChange={(e) => setFilterSearch(e.target.value)}
                  placeholder="환자명, 환자번호, 담당의, 진단명 검색..."
                  className="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setFilterStatus('')}
                  className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                    filterStatus === '' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  전체
                </button>
                <button
                  onClick={() => setFilterStatus('COMPLETED')}
                  className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                    filterStatus === 'COMPLETED' ? 'bg-green-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  완료
                </button>
                <button
                  onClick={() => setFilterStatus('PENDING')}
                  className={`px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                    filterStatus === 'PENDING' ? 'bg-yellow-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  대기
                </button>
              </div>
            </div>
            {(filterSearch || filterStatus) && (
              <p className="text-xs text-gray-500 mt-2">
                {filteredVisits.length}건 검색됨 (전체 {totalCount}건)
              </p>
            )}
          </div>

          {loading && <LoadingSpinner />}

          {/* 진료 내역 테이블 */}
          {!loading && !error && (
            <div className="bg-white shadow-md rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">환자</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">담당의</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">진료일</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">주증상</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">AI 진단</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">신뢰도</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">상태</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">상세</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {filteredVisits.map((visit) => (
                      <tr
                        key={visit.id}
                        className="hover:bg-blue-50 cursor-pointer transition-colors"
                        onClick={() => setSelectedVisit(visit)}
                      >
                        <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">#{visit.id}</td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <div>
                            <p className="text-sm font-medium text-gray-900">{visit.patient?.name || '-'}</p>
                            <p className="text-xs text-gray-500">{visit.patient?.patient_number || ''}</p>
                          </div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                          {visit.doctor?.full_name || '-'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                          {visit.visit_date ? new Date(visit.visit_date).toLocaleDateString('ko-KR') : '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500 max-w-[200px] truncate">
                          {visit.chief_complaint || '-'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm">
                          {visit.diagnosis ? (
                            <span className="px-2.5 py-0.5 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                              {visit.diagnosis.prediction_kr}
                            </span>
                          ) : (
                            <span className="text-gray-400 text-xs">-</span>
                          )}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm">
                          {visit.diagnosis ? (
                            <span className={`font-bold ${getConfidenceColor(visit.diagnosis.confidence)}`}>
                              {(visit.diagnosis.confidence * 100).toFixed(1)}%
                            </span>
                          ) : (
                            <span className="text-gray-400 text-xs">-</span>
                          )}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">{statusBadge(visit.status)}</td>
                        <td className="px-4 py-3 whitespace-nowrap text-center">
                          <button
                            onClick={(e) => { e.stopPropagation(); setSelectedVisit(visit); }}
                            className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                          >
                            상세보기
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {filteredVisits.length === 0 && (
                <div className="text-center py-12">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="mt-2 text-gray-500">
                    {filterSearch || filterStatus ? '검색 결과가 없습니다.' : '진료 내역이 없습니다.'}
                  </p>
                  {!filterSearch && !filterStatus && (
                    <button
                      onClick={() => router.push('/clinical')}
                      className="mt-3 text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      AI 진단 시작하기
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ===== 상세 보기 모달 ===== */}
      {selectedVisit && (
        <div className="fixed z-50 inset-0 overflow-y-auto">
          <div className="flex items-start justify-center min-h-screen px-4 pt-10 pb-20">
            {/* 배경 오버레이 */}
            <div
              className="fixed inset-0 bg-gray-900 bg-opacity-60 transition-opacity"
              onClick={() => setSelectedVisit(null)}
            ></div>

            {/* 모달 콘텐츠 */}
            <div className="relative bg-white rounded-xl shadow-2xl transform transition-all w-full max-w-3xl">
              {/* 헤더 */}
              <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-t-xl px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-bold text-white">
                      진료 상세 #{selectedVisit.id}
                    </h3>
                    <p className="text-blue-200 text-sm">
                      {selectedVisit.visit_date ? new Date(selectedVisit.visit_date).toLocaleString('ko-KR') : ''}
                    </p>
                  </div>
                  <button
                    onClick={() => setSelectedVisit(null)}
                    className="text-white hover:text-blue-200 transition-colors"
                  >
                    <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              <div className="px-6 py-5 space-y-6 max-h-[70vh] overflow-y-auto">
                {/* 환자 + 의사 정보 */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <p className="text-xs text-gray-500">환자명</p>
                    <p className="text-sm font-semibold text-gray-900">{selectedVisit.patient?.name || '-'}</p>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <p className="text-xs text-gray-500">환자 번호</p>
                    <p className="text-sm font-semibold text-gray-900">{selectedVisit.patient?.patient_number || '-'}</p>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <p className="text-xs text-gray-500">담당의</p>
                    <p className="text-sm font-semibold text-gray-900">{selectedVisit.doctor?.full_name || '-'}</p>
                  </div>
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <p className="text-xs text-gray-500">상태</p>
                    <div className="mt-0.5">{statusBadge(selectedVisit.status)}</div>
                  </div>
                </div>

                {/* 주증상 */}
                {selectedVisit.chief_complaint && (
                  <div>
                    <p className="text-xs text-gray-500 mb-1">주증상</p>
                    <p className="text-sm text-gray-900 bg-gray-50 p-3 rounded-lg">{selectedVisit.chief_complaint}</p>
                  </div>
                )}

                {/* AI 진단 결과 */}
                {selectedVisit.diagnosis ? (
                  <>
                    {/* 주 진단 */}
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-bold text-blue-900">AI 진단 결과</h4>
                        {selectedVisit.diagnosis.is_reviewed === 1 ? (
                          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-700">검토 완료</span>
                        ) : (
                          <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-orange-100 text-orange-700">미검토</span>
                        )}
                      </div>

                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-2xl font-bold text-blue-900">{selectedVisit.diagnosis.prediction_kr}</p>
                          <p className="text-xs text-gray-500 mt-0.5">
                            {selectedVisit.diagnosis.prediction} | {selectedVisit.diagnosis.model_type || 'MTL'}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className={`text-3xl font-bold ${getConfidenceColor(selectedVisit.diagnosis.confidence)}`}>
                            {(selectedVisit.diagnosis.confidence * 100).toFixed(1)}%
                          </p>
                          <p className="text-xs text-gray-500">신뢰도</p>
                        </div>
                      </div>

                      {/* 신뢰도 바 */}
                      <div className="mt-3 w-full bg-gray-200 rounded-full h-2.5">
                        <div
                          className={`${getConfidenceBarColor(selectedVisit.diagnosis.confidence)} h-2.5 rounded-full transition-all`}
                          style={{ width: `${selectedVisit.diagnosis.confidence * 100}%` }}
                        ></div>
                      </div>

                      {/* 처리 시간 */}
                      {selectedVisit.diagnosis.processing_time && (
                        <p className="text-xs text-gray-500 mt-2">
                          처리 시간: {selectedVisit.diagnosis.processing_time.toFixed(3)}초
                        </p>
                      )}
                    </div>

                    {/* 클래스별 확률 분포 */}
                    {selectedVisit.diagnosis.probabilities_kr && (
                      <div>
                        <h4 className="text-sm font-bold text-gray-900 mb-3">분류 확률 분포</h4>
                        <div className="space-y-2">
                          {Object.entries(selectedVisit.diagnosis.probabilities_kr)
                            .sort(([, a], [, b]) => (b as number) - (a as number))
                            .map(([cls, prob]) => {
                              const probNum = prob as number;
                              const isTop = probNum === selectedVisit.diagnosis!.confidence;
                              return (
                                <div key={cls}>
                                  <div className="flex justify-between text-sm mb-1">
                                    <span className={isTop ? 'font-bold text-blue-700' : 'text-gray-700'}>{cls}</span>
                                    <span className={`font-medium ${isTop ? 'text-blue-700' : 'text-gray-600'}`}>
                                      {(probNum * 100).toFixed(2)}%
                                    </span>
                                  </div>
                                  <div className="w-full bg-gray-100 rounded-full h-2">
                                    <div
                                      className={`h-2 rounded-full transition-all ${isTop ? 'bg-blue-600' : 'bg-gray-300'}`}
                                      style={{ width: `${probNum * 100}%` }}
                                    ></div>
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    )}

                    {/* 세그멘테이션 비율 */}
                    {(selectedVisit.diagnosis.tumor_ratio !== undefined && selectedVisit.diagnosis.tumor_ratio !== null) && (
                      <div>
                        <h4 className="text-sm font-bold text-gray-900 mb-3">조직 구성 비율 (세그멘테이션)</h4>

                        {/* 전체 비율 바 */}
                        <div className="w-full h-6 rounded-full overflow-hidden flex mb-3">
                          {SEG_LEGEND.filter(item => item.key !== 'background').map((item) => {
                            const ratio = getSegRatio(selectedVisit.diagnosis!, item.key);
                            if (ratio < 0.001) return null;
                            return (
                              <div
                                key={item.key}
                                className={`${item.color} h-full relative`}
                                style={{ width: `${ratio * 100}%` }}
                                title={`${item.label}: ${(ratio * 100).toFixed(1)}%`}
                              >
                                {ratio > 0.1 && (
                                  <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-white drop-shadow">
                                    {(ratio * 100).toFixed(0)}%
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>

                        {/* 상세 비율 카드 */}
                        <div className="grid grid-cols-5 gap-2">
                          {SEG_LEGEND.map((item) => {
                            const ratio = getSegRatio(selectedVisit.diagnosis!, item.key);
                            return (
                              <div key={item.key} className="bg-white border border-gray-200 p-2 rounded-lg text-center">
                                <div className="flex items-center justify-center gap-1 mb-1">
                                  <div className={`w-2.5 h-2.5 rounded-sm ${item.color}`}></div>
                                  <p className="text-xs text-gray-500">{item.label}</p>
                                </div>
                                <p className={`text-lg font-bold ${item.textColor}`}>
                                  {(ratio * 100).toFixed(1)}%
                                </p>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-center py-8 bg-gray-50 rounded-lg">
                    <svg className="mx-auto h-10 w-10 text-gray-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    <p className="text-gray-500 text-sm">AI 진단이 수행되지 않았습니다.</p>
                    <button
                      onClick={() => {
                        setSelectedVisit(null);
                        router.push(`/clinical?patient_id=${selectedVisit.patient?.id || ''}`);
                      }}
                      className="mt-2 text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      AI 진단 시작하기
                    </button>
                  </div>
                )}
              </div>

              {/* 푸터 */}
              <div className="bg-gray-50 rounded-b-xl px-6 py-3 flex justify-between items-center">
                <p className="text-xs text-gray-400">
                  진단일: {selectedVisit.diagnosis?.created_at ? new Date(selectedVisit.diagnosis.created_at).toLocaleString('ko-KR') : '-'}
                </p>
                <button
                  onClick={() => setSelectedVisit(null)}
                  className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 text-sm font-medium rounded-lg transition-colors"
                >
                  닫기
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
