"""
진료 기록 관리 API (확장)
환자별, 의사별, 날짜별 필터링 지원
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.schemas.visit import Visit, VisitCreate, VisitUpdate
from app.models.visit import Visit as VisitModel
from app.models.patient import Patient
from app.models.user import User
from app.models.diagnosis import Diagnosis

router = APIRouter()


@router.get("/stats/summary")
def get_visit_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진료 통계 요약
    
    - 전체/완료/대기 건수
    - 의사별 진료 건수
    """
    
    total = db.query(VisitModel).count()
    completed = db.query(VisitModel).filter(VisitModel.status == "COMPLETED").count()
    pending = db.query(VisitModel).filter(VisitModel.status == "PENDING").count()
    
    return {
        "total": total,
        "completed": completed,
        "pending": pending
    }


@router.get("/", response_model=List[dict])
def get_visits(
    skip: int = 0,
    limit: int = 100,
    patient_id: Optional[int] = Query(None, description="환자 ID로 필터링"),
    doctor_id: Optional[int] = Query(None, description="의사 ID로 필터링"),
    status: Optional[str] = Query(None, description="상태로 필터링 (PENDING/COMPLETED)"),
    date_from: Optional[date] = Query(None, description="시작 날짜"),
    date_to: Optional[date] = Query(None, description="종료 날짜"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진료 기록 목록 조회 (고급 필터링)
    
    - 환자별, 의사별, 상태별, 날짜별 필터링 가능
    - 인증 필요
    """
    
    # 기본 쿼리
    query = db.query(VisitModel)
    
    # 필터링 적용
    if patient_id:
        query = query.filter(VisitModel.patient_id == patient_id)
    
    if doctor_id:
        query = query.filter(VisitModel.doctor_id == doctor_id)
    
    if status:
        query = query.filter(VisitModel.status == status)
    
    if date_from:
        query = query.filter(VisitModel.visit_date >= datetime.combine(date_from, datetime.min.time()))
    
    if date_to:
        query = query.filter(VisitModel.visit_date <= datetime.combine(date_to, datetime.max.time()))
    
    # 최신순 정렬
    query = query.order_by(VisitModel.visit_date.desc())
    
    visits = query.offset(skip).limit(limit).all()
    
    # 환자 및 의사 정보 포함
    result = []
    for visit in visits:
        patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
        doctor = db.query(User).filter(User.id == visit.doctor_id).first()
        
        # 진단 결과 조회
        diagnosis = db.query(Diagnosis).filter(Diagnosis.visit_id == visit.id).first()
        
        result.append({
            "id": visit.id,
            "visit_date": visit.visit_date.isoformat() if visit.visit_date else None,
            "patient": {
                "id": patient.id,
                "name": patient.name,
                "patient_number": patient.patient_number
            } if patient else None,
            "doctor": {
                "id": doctor.id,
                "full_name": doctor.full_name,
                "username": doctor.username
            } if doctor else None,
            "chief_complaint": visit.chief_complaint,
            "diagnosis_summary": visit.diagnosis_summary,
            "status": visit.status,
            "diagnosis": {
                "id": diagnosis.id,
                "prediction": diagnosis.prediction,
                "prediction_kr": diagnosis.prediction_kr,
                "confidence": diagnosis.confidence,
                "probabilities_kr": diagnosis.probabilities_kr,
                "tumor_ratio": diagnosis.tumor_ratio,
                "stroma_ratio": diagnosis.stroma_ratio,
                "normal_ratio": diagnosis.normal_ratio,
                "immune_ratio": diagnosis.immune_ratio,
                "background_ratio": diagnosis.background_ratio,
                "model_type": diagnosis.model_type,
                "processing_time": diagnosis.processing_time,
                "is_reviewed": diagnosis.is_reviewed,
                "created_at": diagnosis.created_at.isoformat() if diagnosis.created_at else None
            } if diagnosis else None,
            "created_at": visit.created_at.isoformat() if visit.created_at else None
        })
    
    return result


@router.post("/", response_model=Visit)
def create_visit(
    visit: VisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진료 기록 생성
    
    - 의사 권한 필요
    - 인증 필요
    """
    
    # 권한 체크
    if current_user.role.value not in ["ADMIN", "DOCTOR"]:
        raise HTTPException(status_code=403, detail="의사 권한이 필요합니다.")
    
    # 환자 존재 확인
    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="환자를 찾을 수 없습니다.")
    
    db_visit = VisitModel(**visit.model_dump())
    db.add(db_visit)
    db.commit()
    db.refresh(db_visit)
    return db_visit


@router.get("/{visit_id}", response_model=dict)
def get_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진료 기록 상세 조회
    
    - 환자, 의사, 진단 결과 포함
    - 인증 필요
    """
    
    visit = db.query(VisitModel).filter(VisitModel.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="진료 기록을 찾을 수 없습니다.")
    
    # 환자 정보
    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
    
    # 의사 정보
    doctor = db.query(User).filter(User.id == visit.doctor_id).first()
    
    # 진단 결과
    diagnosis = db.query(Diagnosis).filter(Diagnosis.visit_id == visit.id).first()
    
    return {
        "id": visit.id,
        "visit_date": visit.visit_date.isoformat() if visit.visit_date else None,
        "patient": {
            "id": patient.id,
            "name": patient.name,
            "patient_number": patient.patient_number,
            "birth_date": patient.birth_date.isoformat() if patient.birth_date else None,
            "gender": patient.gender.value,
            "phone": patient.phone,
            "blood_type": patient.blood_type
        } if patient else None,
        "doctor": {
            "id": doctor.id,
            "full_name": doctor.full_name,
            "username": doctor.username,
            "role": doctor.role.value
        } if doctor else None,
        "chief_complaint": visit.chief_complaint,
        "diagnosis_summary": visit.diagnosis_summary,
        "status": visit.status,
        "diagnosis": {
            "id": diagnosis.id,
            "prediction": diagnosis.prediction,
            "prediction_kr": diagnosis.prediction_kr,
            "confidence": diagnosis.confidence,
            "probabilities_kr": diagnosis.probabilities_kr,
            "tumor_ratio": diagnosis.tumor_ratio,
            "stroma_ratio": diagnosis.stroma_ratio,
            "normal_ratio": diagnosis.normal_ratio,
            "immune_ratio": diagnosis.immune_ratio,
            "background_ratio": diagnosis.background_ratio,
            "model_type": diagnosis.model_type,
            "processing_time": diagnosis.processing_time,
            "is_reviewed": diagnosis.is_reviewed,
            "created_at": diagnosis.created_at.isoformat() if diagnosis.created_at else None
        } if diagnosis else None,
        "created_at": visit.created_at.isoformat() if visit.created_at else None
    }


@router.put("/{visit_id}", response_model=Visit)
def update_visit(
    visit_id: int,
    visit_update: VisitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진료 기록 수정
    
    - 의사 권한 필요
    - 본인이 작성한 기록만 수정 가능 (관리자는 모두 수정 가능)
    """
    
    visit = db.query(VisitModel).filter(VisitModel.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="진료 기록을 찾을 수 없습니다.")
    
    # 권한 체크
    if visit.doctor_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="본인이 작성한 기록만 수정 가능합니다.")
    
    update_data = visit_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(visit, field, value)
    
    db.commit()
    db.refresh(visit)
    return visit


@router.delete("/{visit_id}")
def delete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    진료 기록 삭제
    
    - 관리자 권한 필요
    """
    
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    
    visit = db.query(VisitModel).filter(VisitModel.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="진료 기록을 찾을 수 없습니다.")
    
    db.delete(visit)
    db.commit()
    return {"message": "진료 기록이 삭제되었습니다."}
