"""
Diagnosis Model (AI 진단 결과)
Multi-Task Learning 지원: Classification + Segmentation
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base


class Diagnosis(Base):
    __tablename__ = "diagnoses"
    
    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(Integer, ForeignKey("visits.id", ondelete="CASCADE"), nullable=False)
    
    # AI 예측 결과 (Classification)
    prediction = Column(String(50), nullable=False)  # STDI, STNT, STIN, STMX
    prediction_kr = Column(String(50))  # 한국어 진단명
    confidence = Column(Float, nullable=False)  # 신뢰도 (0~1)
    
    # 확률 분포 (JSON 저장)
    probabilities = Column(JSON)  # {"STDI": 0.05, "STNT": 0.06, ...}
    probabilities_kr = Column(JSON)  # {"미만형선암": 0.05, ...}
    raw_logits = Column(JSON)  # [1.2, 1.5, 3.4, 0.8]
    
    # ⭐ Segmentation 결과 (Multi-Task Learning)
    tumor_ratio = Column(Float)  # 종양 비율
    stroma_ratio = Column(Float)  # 간질 비율
    normal_ratio = Column(Float)  # 정상 조직 비율
    immune_ratio = Column(Float)  # 면역세포 비율
    background_ratio = Column(Float)  # 배경 비율
    
    # 이미지 정보
    image_path = Column(String(500))  # 업로드된 이미지 경로
    image_size = Column(JSON)  # [width, height]
    
    # 처리 정보
    processing_time = Column(Float)  # 처리 시간 (초)
    model_version = Column(String(50))  # 모델 버전
    model_type = Column(String(100))  # "UNet + ResNet50 MTL"
    device = Column(String(20))  # cuda / cpu
    
    # 의사 검토
    is_reviewed = Column(Integer, default=0)  # 0: 미검토, 1: 검토 완료
    reviewed_by_id = Column(Integer, ForeignKey("users.id"))
    review_notes = Column(Text)  # 의사 소견
    final_diagnosis = Column(String(50))  # 최종 진단 (AI 결과 수정 가능)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    visit = relationship("Visit", back_populates="diagnoses")
    reviewer = relationship("User", foreign_keys=[reviewed_by_id])
    
    def __repr__(self):
        return f"<Diagnosis(id={self.id}, prediction={self.prediction}, confidence={self.confidence:.2f})>"
