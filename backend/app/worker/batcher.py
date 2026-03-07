"""
Dynamic Batching Engine
일정 시간(BATCH_TIMEOUT_MS) 또는 일정 개수(BATCH_SIZE)만큼 요청을 모아서
배치 추론을 실행하는 엔진

워커 프로세스 내에서 싱글톤으로 동작하며,
predict 요청이 들어오면 큐에 넣고 배치가 채워지거나 타임아웃 되면 한번에 처리한다.
"""

import threading
import time
import logging
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from queue import Queue, Empty
from concurrent.futures import Future

logger = logging.getLogger(__name__)

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "8"))
BATCH_TIMEOUT_MS = int(os.getenv("BATCH_TIMEOUT_MS", "100"))


@dataclass
class InferenceRequest:
    """배치에 포함될 개별 추론 요청"""
    request_id: str
    image_bytes: bytes
    future: Future = field(default_factory=Future)


class DynamicBatcher:
    """
    동적 배칭 엔진

    - 요청이 들어오면 내부 큐에 넣는다.
    - 별도 스레드에서 큐를 감시하다가:
      1) 큐에 BATCH_SIZE개 이상 쌓이면 즉시 배치 실행
      2) 첫 요청이 들어온 후 BATCH_TIMEOUT_MS 이내에 배치가 안 채워지면 모아진 것만 실행
    """

    def __init__(self, model_service):
        self.model_service = model_service
        self.batch_size = BATCH_SIZE
        self.batch_timeout_s = BATCH_TIMEOUT_MS / 1000.0
        self._queue: Queue[InferenceRequest] = Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        logger.info(
            f"DynamicBatcher initialized: batch_size={self.batch_size}, "
            f"timeout={BATCH_TIMEOUT_MS}ms"
        )

    def start(self):
        """배칭 스레드 시작"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._batch_loop, daemon=True)
        self._thread.start()
        logger.info("DynamicBatcher batch loop started")

    def stop(self):
        """배칭 스레드 정지"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("DynamicBatcher stopped")

    def submit(self, request_id: str, image_bytes: bytes) -> Future:
        """
        추론 요청 제출. Future를 반환하며, 배치 처리 완료 시 결과가 set된다.
        """
        req = InferenceRequest(request_id=request_id, image_bytes=image_bytes)
        self._queue.put(req)
        return req.future

    def _batch_loop(self):
        """배치 수집 및 실행 루프"""
        while self._running:
            batch: List[InferenceRequest] = []

            # 첫 요청 대기 (블로킹, 1초 타임아웃)
            try:
                first = self._queue.get(timeout=1.0)
                batch.append(first)
            except Empty:
                continue

            # 나머지 요청 수집 (batch_size까지 또는 timeout까지)
            deadline = time.monotonic() + self.batch_timeout_s
            while len(batch) < self.batch_size:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    req = self._queue.get(timeout=remaining)
                    batch.append(req)
                except Empty:
                    break

            # 배치 추론 실행
            if batch:
                self._execute_batch(batch)

    def _execute_batch(self, batch: List[InferenceRequest]):
        """배치 추론 실행 및 개별 결과 매핑"""
        batch_size = len(batch)
        logger.info(f"Executing batch inference: {batch_size} items")
        start_time = time.time()

        try:
            # 모델 서비스의 배치 예측 호출
            image_bytes_list = [req.image_bytes for req in batch]
            results = self.model_service.predict_batch(image_bytes_list)

            elapsed = time.time() - start_time
            logger.info(
                f"Batch inference completed: {batch_size} items in {elapsed:.3f}s "
                f"({elapsed/batch_size:.3f}s/item)"
            )

            # 개별 결과 매핑
            for req, result in zip(batch, results):
                if not req.future.done():
                    req.future.set_result(result)

        except Exception as e:
            logger.error(f"Batch inference failed: {e}")
            for req in batch:
                if not req.future.done():
                    req.future.set_exception(e)


# 싱글톤 인스턴스 (워커 프로세스에서 초기화)
_batcher: Optional[DynamicBatcher] = None
_batcher_lock = threading.Lock()


def get_batcher(model_service=None) -> DynamicBatcher:
    """글로벌 DynamicBatcher 인스턴스 반환"""
    global _batcher
    with _batcher_lock:
        if _batcher is None:
            if model_service is None:
                raise RuntimeError("DynamicBatcher가 초기화되지 않았습니다.")
            _batcher = DynamicBatcher(model_service)
            _batcher.start()
        return _batcher
