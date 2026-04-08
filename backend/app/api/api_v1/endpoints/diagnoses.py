"""
진단 결과 관리 API (리뷰 시스템 포함)
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.schemas.diagnosis import Diagnosis, DiagnosisCreate
from app.models.diagnosis import Diagnosis as DiagnosisModel
from app.models.visit import Visit
from app.models.user import User
from app.models.patient import Patient

router = APIRouter()


@router.get("/stats/summary")
def get_diagnosis_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진단 통계 요약
    
    - 전체/리뷰완료/미검토 건수
    - 암 유형별 분포
    """
    
    total = db.query(DiagnosisModel).count()
    reviewed = db.query(DiagnosisModel).filter(DiagnosisModel.is_reviewed == 1).count()
    unreviewed = db.query(DiagnosisModel).filter(DiagnosisModel.is_reviewed == 0).count()
    
    # 암 유형별 통계
    diagnoses = db.query(DiagnosisModel).all()
    cancer_distribution = {}
    for diag in diagnoses:
        cancer_type = diag.prediction_kr or "미분류"
        cancer_distribution[cancer_type] = cancer_distribution.get(cancer_type, 0) + 1
    
    return {
        "total": total,
        "reviewed": reviewed,
        "unreviewed": unreviewed,
        "cancer_distribution": cancer_distribution
    }


@router.get("/", response_model=List[dict])
def get_diagnoses(
    skip: int = 0,
    limit: int = 100,
    is_reviewed: Optional[int] = Query(None, description="리뷰 상태 (0: 미검토, 1: 검토완료)"),
    prediction: Optional[str] = Query(None, description="진단 결과로 필터링"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진단 결과 목록 조회
    
    - 리뷰 상태 및 진단 결과로 필터링 가능
    - 인증 필요
    """
    
    query = db.query(DiagnosisModel)
    
    if is_reviewed is not None:
        query = query.filter(DiagnosisModel.is_reviewed == is_reviewed)
    
    if prediction:
        query = query.filter(DiagnosisModel.prediction == prediction)
    
    # 최신순 정렬
    query = query.order_by(DiagnosisModel.created_at.desc())
    
    diagnoses = query.offset(skip).limit(limit).all()
    
    # 진료 및 환자 정보 포함
    result = []
    for diag in diagnoses:
        visit = db.query(Visit).filter(Visit.id == diag.visit_id).first()
        patient = None
        if visit:
            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
        
        result.append({
            "id": diag.id,
            "visit_id": diag.visit_id,
            "patient": {
                "name": patient.name,
                "patient_number": patient.patient_number
            } if patient else None,
            "prediction": diag.prediction,
            "prediction_kr": diag.prediction_kr,
            "confidence": diag.confidence,
            "probabilities_kr": diag.probabilities_kr,
            "tumor_ratio": diag.tumor_ratio,
            "stroma_ratio": diag.stroma_ratio,
            "normal_ratio": diag.normal_ratio,
            "is_reviewed": diag.is_reviewed,
            "reviewed_by_id": diag.reviewed_by_id,
            "created_at": diag.created_at.isoformat() if diag.created_at else None
        })
    
    return result


@router.post("/", response_model=Diagnosis)
def create_diagnosis(
    diagnosis: DiagnosisCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진단 결과 생성
    
    - 의사 권한 필요
    """
    
    if current_user.role.value not in ["ADMIN", "DOCTOR"]:
        raise HTTPException(status_code=403, detail="의사 권한이 필요합니다.")
    
    # 진료 기록 존재 확인
    visit = db.query(Visit).filter(Visit.id == diagnosis.visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="진료 기록을 찾을 수 없습니다.")
    
    db_diagnosis = DiagnosisModel(**diagnosis.model_dump())
    db.add(db_diagnosis)
    db.commit()
    db.refresh(db_diagnosis)
    return db_diagnosis


@router.get("/{diagnosis_id}", response_model=dict)
def get_diagnosis(
    diagnosis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진단 결과 상세 조회
    
    - 진료 및 환자 정보 포함
    """
    
    diagnosis = db.query(DiagnosisModel).filter(DiagnosisModel.id == diagnosis_id).first()
    if not diagnosis:
        raise HTTPException(status_code=404, detail="진단 결과를 찾을 수 없습니다.")
    
    # 진료 정보
    visit = db.query(Visit).filter(Visit.id == diagnosis.visit_id).first()
    
    # 환자 정보
    patient = None
    doctor = None
    if visit:
        patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
        doctor = db.query(User).filter(User.id == visit.doctor_id).first()
    
    # 리뷰한 의사 정보
    reviewer = None
    if diagnosis.reviewed_by_id:
        reviewer = db.query(User).filter(User.id == diagnosis.reviewed_by_id).first()
    
    return {
        "id": diagnosis.id,
        "visit_id": diagnosis.visit_id,
        "patient": {
            "id": patient.id,
            "name": patient.name,
            "patient_number": patient.patient_number
        } if patient else None,
        "doctor": {
            "id": doctor.id,
            "full_name": doctor.full_name
        } if doctor else None,
        "prediction": diagnosis.prediction,
        "prediction_kr": diagnosis.prediction_kr,
        "confidence": diagnosis.confidence,
        "probabilities": diagnosis.probabilities,
        "probabilities_kr": diagnosis.probabilities_kr,
        "raw_logits": diagnosis.raw_logits,
        "tumor_ratio": diagnosis.tumor_ratio,
        "stroma_ratio": diagnosis.stroma_ratio,
        "normal_ratio": diagnosis.normal_ratio,
        "immune_ratio": diagnosis.immune_ratio,
        "background_ratio": diagnosis.background_ratio,
        "model_type": diagnosis.model_type,
        "processing_time": diagnosis.processing_time,
        "device": diagnosis.device,
        "is_reviewed": diagnosis.is_reviewed,
        "reviewed_by": {
            "id": reviewer.id,
            "full_name": reviewer.full_name
        } if reviewer else None,
        "created_at": diagnosis.created_at.isoformat() if diagnosis.created_at else None
    }


@router.put("/{diagnosis_id}/review")
def review_diagnosis(
    diagnosis_id: int,
    approved: bool = Query(..., description="승인 여부"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진단 결과 리뷰
    
    - 의사 권한 필요
    - 리뷰 상태 업데이트 및 리뷰어 기록
    """
    
    if current_user.role.value not in ["ADMIN", "DOCTOR"]:
        raise HTTPException(status_code=403, detail="의사 권한이 필요합니다.")
    
    diagnosis = db.query(DiagnosisModel).filter(DiagnosisModel.id == diagnosis_id).first()
    if not diagnosis:
        raise HTTPException(status_code=404, detail="진단 결과를 찾을 수 없습니다.")
    
    diagnosis.is_reviewed = 1 if approved else 0
    diagnosis.reviewed_by_id = current_user.id
    
    db.commit()
    db.refresh(diagnosis)
    
    return {
        "message": "리뷰가 완료되었습니다.",
        "diagnosis_id": diagnosis.id,
        "is_reviewed": diagnosis.is_reviewed,
        "reviewed_by": current_user.full_name
    }


@router.delete("/{diagnosis_id}")
def delete_diagnosis(
    diagnosis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진단 결과 삭제
    
    - 관리자 권한 필요
    """
    
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    diagnosis = db.query(DiagnosisModel).filter(DiagnosisModel.id == diagnosis_id).first()
    if not diagnosis:
        raise HTTPException(status_code=404, detail="진단 결과를 찾을 수 없습니다.")
    
    db.delete(diagnosis)
    db.commit()
    return {"message": "진단 결과가 삭제되었습니다."}
