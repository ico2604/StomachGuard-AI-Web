"""
AI 진단 API - Celery 비동기 태스크 기반

POST /predict      → 이미지 업로드 → Celery 태스크 제출 → task_id 반환
GET  /tasks/{id}   → 태스크 상태/결과 폴링
GET  /model-info   → 모델 정보 조회
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.ai_service import ai_service
from app.core.celery_app import celery_app
import base64

router = APIRouter()


@router.post("/predict")
async def predict_image(file: UploadFile = File(...)):
    """
    이미지 업로드 및 AI 예측 (비동기)

    1. 이미지를 base64로 인코딩
    2. Celery 태스크로 제출
    3. task_id 즉시 반환

    클라이언트는 GET /tasks/{task_id}로 결과를 폴링
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    content = await file.read()
    image_b64 = base64.b64encode(content).decode("utf-8")

    # Celery 태스크 제출
    task = celery_app.send_task(
        "app.worker.tasks.predict_single",
        args=[image_b64],
        kwargs={"task_meta": {"source": "ai_predict"}},
        queue="ai_inference",
    )

    return {
        "task_id": task.id,
        "status": "PENDING",
        "message": "AI 진단 태스크가 제출되었습니다.",
    }


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    """
    태스크 상태 및 결과 조회 (폴링 엔드포인트)

    상태 흐름: PENDING → PROCESSING → COMPLETED / FAILED
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
        return {
            "task_id": task_id,
            "status": "COMPLETED",
            "result": result.result,
        }

    elif result.state == "FAILURE":
        error_info = str(result.info) if result.info else "알 수 없는 오류"
        return {
            "task_id": task_id,
            "status": "FAILED",
            "message": f"태스크 실패: {error_info}",
        }

    else:
        # RETRY 등 기타 상태
        meta = result.info if isinstance(result.info, dict) else {}
        return {
            "task_id": task_id,
            "status": result.state,
            "message": meta.get("message", f"상태: {result.state}"),
        }


@router.get("/model-info")
def get_model_info():
    """모델 정보 조회"""
    return ai_service.get_model_info()
