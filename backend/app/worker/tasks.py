"""
Celery Tasks - AI 모델 추론 태스크

워커가 시작될 때 모델을 한 번만 로드하고 메모리에 유지.
동적 배칭을 통해 여러 요청을 모아서 배치 추론 실행.
"""

import logging
import time
import json
from typing import Dict, Optional

from celery import current_app
from celery.signals import worker_process_init, worker_process_shutdown

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)

# 워커 프로세스 전역 변수
_ai_service = None
_batcher = None


@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    워커 프로세스 시작 시 모델 로드 (프로세스당 1회)
    Celery 워커가 fork 된 후 호출됨
    """
    global _ai_service, _batcher
    logger.info("Initializing AI model in worker process...")

    try:
        from app.services.ai_service import MTLAIService
        from app.worker.batcher import get_batcher

        # 모델 로드 (GPU 메모리에 올림)
        _ai_service = MTLAIService()
        logger.info(f"AI model loaded: {_ai_service.get_model_info()}")

        # 동적 배칭 엔진 시작
        _batcher = get_batcher(_ai_service)
        logger.info("Dynamic batcher started")

    except Exception as e:
        logger.error(f"Failed to initialize worker: {e}")
        _ai_service = None
        _batcher = None


@worker_process_shutdown.connect
def shutdown_worker_process(**kwargs):
    """워커 프로세스 종료 시 정리"""
    global _batcher
    if _batcher:
        _batcher.stop()
        logger.info("Dynamic batcher stopped")


@celery_app.task(
    bind=True,
    name="app.worker.tasks.predict_single",
    queue="ai_inference",
    max_retries=2,
    default_retry_delay=5,
)
def predict_single(self, image_bytes_b64: str, task_meta: Dict = None) -> Dict:
    """
    단일 이미지 AI 추론 태스크

    동적 배칭 엔진에 요청을 제출하고 결과를 기다림.
    배칭 엔진이 내부적으로 여러 요청을 모아 배치 추론 실행.

    Args:
        image_bytes_b64: base64 인코딩된 이미지 바이트
        task_meta: 태스크 메타데이터 (patient_id, user_id 등)

    Returns:
        AI 예측 결과 딕셔너리
    """
    import base64
    global _ai_service, _batcher

    task_id = self.request.id
    meta = task_meta or {}

    # 상태 업데이트: PROCESSING
    self.update_state(
        state="PROCESSING",
        meta={
            "status": "PROCESSING",
            "message": "AI 모델이 이미지를 분석하고 있습니다...",
            **meta,
        }
    )

    try:
        # base64 디코딩
        image_bytes = base64.b64decode(image_bytes_b64)

        if _batcher is not None:
            # 동적 배칭 사용
            future = _batcher.submit(task_id, image_bytes)
            # 배치 처리 완료까지 대기 (타임아웃 60초)
            result = future.result(timeout=60)
        elif _ai_service is not None:
            # 배칭 미사용 시 직접 추론
            result = _ai_service.predict(image_bytes)
        else:
            # 폴백: mock 서비스
            from app.services.ai_service import MTLAIService
            mock_service = MTLAIService.__new__(MTLAIService)
            mock_service.model = None
            mock_service.SEG_COLORS = MTLAIService.SEG_COLORS
            result = mock_service._mock_predict(time.time())

        if "error" in result:
            raise Exception(result.get("message", "AI prediction failed"))

        # 메타데이터 추가
        result["task_id"] = task_id
        result["task_meta"] = meta

        return result

    except Exception as exc:
        logger.error(f"Task {task_id} failed: {exc}")
        self.update_state(
            state="FAILED",
            meta={
                "status": "FAILED",
                "message": str(exc),
                **meta,
            }
        )
        raise self.retry(exc=exc, countdown=5) if self.request.retries < self.max_retries else exc


@celery_app.task(
    name="app.worker.tasks.save_diagnosis_result",
    queue="db_operations",
    max_retries=3,
    default_retry_delay=3,
)
def save_diagnosis_result(
    prediction_result: Dict,
    patient_id: int,
    doctor_id: int,
    chief_complaint: str = "",
) -> Dict:
    """
    AI 예측 결과를 DB에 저장하는 태스크

    Celery 워커에서 DB 세션을 직접 사용하여 저장.
    FastAPI의 요청 컨텍스트와 분리되어 동작.

    Args:
        prediction_result: AI 예측 결과
        patient_id: 환자 ID
        doctor_id: 의사 (사용자) ID
        chief_complaint: 주증상

    Returns:
        저장된 visit_id, diagnosis_id
    """
    from datetime import datetime
    from app.core.database import SessionLocal
    from app.models.visit import Visit
    from app.models.diagnosis import Diagnosis

    db = SessionLocal()
    try:
        seg_stats = (
            prediction_result.get("segmentation", {})
            .get("stats", {})
            .get("ratios", {})
        )

        # 진료 기록 생성
        visit = Visit(
            patient_id=patient_id,
            doctor_id=doctor_id,
            chief_complaint=chief_complaint,
            diagnosis_summary=f"AI 진단: {prediction_result['prediction_kr']}",
            status="COMPLETED",
            visit_date=datetime.utcnow(),
        )
        db.add(visit)
        db.flush()

        # 진단 결과 저장
        diagnosis = Diagnosis(
            visit_id=visit.id,
            prediction=prediction_result["prediction"],
            prediction_kr=prediction_result["prediction_kr"],
            confidence=prediction_result["confidence"],
            probabilities=prediction_result["probabilities"],
            probabilities_kr=prediction_result["probabilities_kr"],
            raw_logits=prediction_result.get("raw_logits"),
            tumor_ratio=seg_stats.get("tumor", 0),
            stroma_ratio=seg_stats.get("stroma", 0),
            normal_ratio=seg_stats.get("normal", 0),
            immune_ratio=seg_stats.get("immune", 0),
            background_ratio=seg_stats.get("background", 0),
            model_type=prediction_result.get("model_info", {}).get("model_type", "MTL"),
            processing_time=prediction_result.get("processing_time"),
            device=prediction_result.get("model_info", {}).get("device", "cpu"),
            is_reviewed=0,
        )
        db.add(diagnosis)
        db.commit()
        db.refresh(visit)
        db.refresh(diagnosis)

        logger.info(
            f"Diagnosis saved: visit_id={visit.id}, diagnosis_id={diagnosis.id}, "
            f"prediction={prediction_result['prediction_kr']}"
        )

        return {
            "visit_id": visit.id,
            "diagnosis_id": diagnosis.id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save diagnosis: {e}")
        raise
    finally:
        db.close()
