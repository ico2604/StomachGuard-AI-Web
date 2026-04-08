"""
통합 진료 워크플로우 API - Celery 비동기 버전

POST /diagnose           → 진료 + AI 진단 태스크 제출 → task_id 반환
GET  /diagnose/{task_id} → 진단 태스크 결과 폴링 + DB 저장
GET  /stats              → 진료 통계 (대시보드)
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Dict, Optional
from datetime import datetime
import base64
import json
import logging

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.core.celery_app import celery_app
from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.diagnosis import Diagnosis

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/diagnose")
async def create_clinical_diagnosis(
    patient_id: int = Form(..., description="환자 ID"),
    chief_complaint: str = Form("", description="주 증상"),
    image: UploadFile = File(..., description="현미경 이미지"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    통합 진료 워크플로우 (비동기)

    1. 환자 정보 확인 + 권한 체크
    2. 이미지를 base64로 인코딩
    3. Celery AI 추론 태스크 제출
    4. task_id 즉시 반환

    클라이언트는 GET /clinical/diagnose/{task_id}로 결과 폴링
    """
    # 1. 권한 체크
    if current_user.role.value not in ["ADMIN", "DOCTOR"]:
        raise HTTPException(status_code=403, detail="의사 권한이 필요합니다.")

    # 2. 환자 존재 확인
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="환자를 찾을 수 없습니다.")

    # 3. 이미지 유효성 검사
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    # 4. 이미지 읽기 + base64 인코딩
    content = await image.read()
    image_b64 = base64.b64encode(content).decode("utf-8")

    # 5. Celery 태스크 제출
    task_meta = {
        "patient_id": patient_id,
        "patient_name": patient.name,
        "patient_number": patient.patient_number,
        "doctor_id": current_user.id,
        "doctor_name": current_user.full_name,
        "chief_complaint": chief_complaint,
        "source": "clinical_diagnose",
    }

    task = celery_app.send_task(
        "app.worker.tasks.predict_single",
        args=[image_b64],
        kwargs={"task_meta": task_meta},
        queue="ai_inference",
    )

    return {
        "task_id": task.id,
        "status": "PENDING",
        "message": "AI 진단 태스크가 제출되었습니다.",
        "patient": {
            "id": patient.id,
            "name": patient.name,
            "patient_number": patient.patient_number,
        },
    }


@router.get("/diagnose/{task_id}")
def poll_diagnosis_result(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    AI 진단 태스크 결과 폴링

    상태 흐름: PENDING → PROCESSING → COMPLETED / FAILED

    COMPLETED 시:
    - AI 결과를 DB에 저장 (Visit + Diagnosis)
    - 기존 동기 API와 동일한 응답 스키마 반환
    """
    result = celery_app.AsyncResult(task_id)

    if result.state == "PENDING":
        return {
            "task_id": task_id,
            "status": "PENDING",
            "message": "태스크가 대기 중입니다...",
        }

    elif result.state == "PROCESSING":
        meta = result.info or {}
        return {
            "task_id": task_id,
            "status": "PROCESSING",
            "message": meta.get("message", "AI 모델이 이미지를 분석하고 있습니다..."),
        }

    elif result.state == "SUCCESS":
        prediction = result.result
        task_meta = prediction.get("task_meta", {})

        # DB 저장 여부 확인 (이미 저장되었으면 스킵)
        visit_id = prediction.get("_visit_id")
        diagnosis_id = prediction.get("_diagnosis_id")

        if not visit_id:
            # DB 저장 수행
            try:
                saved = _save_to_db(db, prediction, task_meta)
                visit_id = saved["visit_id"]
                diagnosis_id = saved["diagnosis_id"]

                # 결과에 DB ID 기록 (중복 저장 방지)
                prediction["_visit_id"] = visit_id
                prediction["_diagnosis_id"] = diagnosis_id
                # Celery 결과 업데이트 (선택적)
                # result.backend.store_result(task_id, prediction, "SUCCESS")
            except Exception as e:
                logger.error(f"Failed to save diagnosis to DB: {e}")
                return {
                    "task_id": task_id,
                    "status": "COMPLETED",
                    "message": "AI 진단 완료 (DB 저장 실패)",
                    "result": _format_response(prediction, task_meta),
                }

        # 기존 API와 동일한 응답 포맷
        return {
            "task_id": task_id,
            "status": "COMPLETED",
            "result": _format_response(
                prediction, task_meta, visit_id, diagnosis_id
            ),
        }

    elif result.state == "FAILURE":
        error_info = str(result.info) if result.info else "알 수 없는 오류"
        return {
            "task_id": task_id,
            "status": "FAILED",
            "message": f"AI 진단 실패: {error_info}",
        }

    else:
        meta = result.info if isinstance(result.info, dict) else {}
        return {
            "task_id": task_id,
            "status": result.state,
            "message": meta.get("message", f"상태: {result.state}"),
        }


def _save_to_db(db: Session, prediction: Dict, task_meta: dict) -> dict:
    """AI 예측 결과를 DB에 저장"""
    seg_stats = (
        prediction.get("segmentation", {}).get("stats", {}).get("ratios", {})
    )

    visit = Visit(
        patient_id=task_meta["patient_id"],
        doctor_id=task_meta["doctor_id"],
        chief_complaint=task_meta.get("chief_complaint", ""),
        diagnosis_summary=f"AI 진단: {prediction['prediction_kr']}",
        status="COMPLETED",
        visit_date=datetime.utcnow(),
    )
    db.add(visit)
    db.flush()

    diagnosis_obj = Diagnosis(
        visit_id=visit.id,
        prediction=prediction["prediction"],
        prediction_kr=prediction["prediction_kr"],
        confidence=prediction["confidence"],
        probabilities=prediction["probabilities"],
        probabilities_kr=prediction["probabilities_kr"],
        raw_logits=prediction.get("raw_logits"),
        tumor_ratio=seg_stats.get("tumor", 0),
        stroma_ratio=seg_stats.get("stroma", 0),
        normal_ratio=seg_stats.get("normal", 0),
        immune_ratio=seg_stats.get("immune", 0),
        background_ratio=seg_stats.get("background", 0),
        model_type=prediction.get("model_info", {}).get("model_type", "MTL"),
        processing_time=prediction.get("processing_time"),
        device=prediction.get("model_info", {}).get("device", "cpu"),
        is_reviewed=0,
    )
    db.add(diagnosis_obj)
    db.commit()
    db.refresh(visit)
    db.refresh(diagnosis_obj)

    return {"visit_id": visit.id, "diagnosis_id": diagnosis_obj.id}


def _format_response(
    prediction: dict,
    task_meta: dict,
    visit_id: int = None,
    diagnosis_id: int = None,
) -> dict:
    """기존 동기 API와 호환되는 응답 포맷"""
    seg_data = prediction.get("segmentation", {})
    seg_stats = seg_data.get("stats", {}).get("ratios", {})

    prob_kr = prediction.get("probabilities_kr", {})
    if isinstance(prob_kr, str):
        try:
            prob_kr = json.loads(prob_kr)
        except (json.JSONDecodeError, TypeError):
            prob_kr = {}

    return {
        "visit": {
            "id": visit_id or 0,
            "visit_date": datetime.utcnow().isoformat(),
            "patient_name": task_meta.get("patient_name", ""),
            "patient_number": task_meta.get("patient_number", ""),
            "chief_complaint": task_meta.get("chief_complaint", ""),
            "status": "COMPLETED",
        },
        "diagnosis": {
            "id": diagnosis_id or 0,
            "prediction": prediction["prediction"],
            "prediction_kr": prediction["prediction_kr"],
            "confidence": prediction["confidence"],
            "probabilities_kr": prob_kr,
        },
        "segmentation": {
            "original_base64": seg_data.get("original_base64", ""),
            "overlay_base64": seg_data.get("overlay_base64", ""),
            "mask_base64": seg_data.get("mask_base64", ""),
            "ratios": seg_stats,
            "class_colors": seg_data.get("class_colors", {}),
            "class_names_kr": seg_data.get("class_names_kr", {}),
        },
        "processing_time": prediction.get("processing_time", 0),
    }


@router.get("/stats")
def get_clinical_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    진료 통계 조회 (대시보드용)
    """
    total_visits = db.query(Visit).count()
    completed_visits = db.query(Visit).filter(Visit.status == "COMPLETED").count()
    pending_visits = db.query(Visit).filter(Visit.status == "PENDING").count()
    total_patients = db.query(Patient).count()
    total_diagnoses = db.query(Diagnosis).count()

    diagnoses = db.query(Diagnosis).all()
    cancer_stats = {}
    for diag in diagnoses:
        cancer_type = diag.prediction_kr or "미분류"
        cancer_stats[cancer_type] = cancer_stats.get(cancer_type, 0) + 1

    return {
        "total_visits": total_visits,
        "completed_visits": completed_visits,
        "pending_visits": pending_visits,
        "total_patients": total_patients,
        "total_diagnoses": total_diagnoses,
        "today_visits": 0,
        "cancer_type_distribution": cancer_stats,
    }
