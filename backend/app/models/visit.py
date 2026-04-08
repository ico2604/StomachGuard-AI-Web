"""
Visit Model (진료 기록)
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base


class Visit(Base):
    __tablename__ = "visits"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 진료 정보
    visit_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    chief_complaint = Column(Text)  # 주 증상
    diagnosis_summary = Column(Text)  # 진단 요약
    treatment_plan = Column(Text)  # 치료 계획
    notes = Column(Text)  # 추가 메모
    
    # 상태
    status = Column(String(50), default="PENDING")  # PENDING, COMPLETED, CANCELLED
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships (문자열 참조로 순환 import 방지)
    patient = relationship("Patient", back_populates="visits")
    doctor = relationship("User", foreign_keys=[doctor_id])
    
    diagnoses = relationship(
        "Diagnosis",
        back_populates="visit",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    def __repr__(self):
        return f"<Visit(id={self.id}, patient_id={self.patient_id}, date={self.visit_date})>"
