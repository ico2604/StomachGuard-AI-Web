"""
Database initialization script with Multi-Task Learning support
위암 분류 병원 관리 시스템 - 데이터베이스 초기화

MySQL 사용 시:
  1. MySQL 서버가 실행 중이어야 합니다.
  2. .env의 DATABASE_URL에 설정한 데이터베이스를 미리 생성하세요:
     mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS gastric_hospital CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  3. python init_db.py 실행
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from sqlalchemy.orm import Session
from sqlalchemy import text
from passlib.context import CryptContext
from datetime import datetime, date

# 모든 모델 import (순서 중요!)
from app.core.database import engine, SessionLocal, Base
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.patient import Patient, Gender
from app.models.visit import Visit
from app.models.diagnosis import Diagnosis

# 비밀번호 해싱 (bcrypt 호환 설정)
try:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception as e:
    print(f"⚠️  bcrypt 경고: {e}")
    pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def check_mysql_connection():
    """MySQL 연결 확인"""
    if "mysql" not in settings.DATABASE_URL:
        return True
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        print("✅ MySQL 연결 성공")
        return True
    except Exception as e:
        print(f"❌ MySQL 연결 실패: {e}")
        print("\n💡 해결 방법:")
        print("   1. MySQL 서버가 실행 중인지 확인:")
        print("      - Windows: services.msc → MySQL 서비스 시작")
        print("      - Mac: brew services start mysql")
        print("      - Linux: sudo systemctl start mysql")
        print("   2. .env 파일의 DATABASE_URL 확인:")
        print(f"      현재: {settings.DATABASE_URL}")
        print("      형식: mysql+pymysql://사용자:비밀번호@호스트:포트/DB이름")
        print("   3. 데이터베이스 생성:")
        print('      mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS gastric_hospital CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"')
        return False


def create_tables():
    """테이블 생성"""
    print("📊 테이블 생성 중...")
    Base.metadata.create_all(bind=engine)
    print("✅ 테이블 생성 완료")


def create_users(db: Session):
    """기본 사용자 생성"""
    print("\n👥 사용자 계정 생성 중...")
    
    users_data = [
        {
            "email": "admin@hospital.com",
            "username": "admin",
            "password": "admin123"[:72],  # bcrypt 72-byte limit
            "full_name": "시스템 관리자",
            "role": UserRole.ADMIN,
            "is_superuser": True
        },
        {
            "email": "doctor1@hospital.com",
            "username": "doctor1",
            "password": "doctor123",
            "full_name": "김의사",
            "role": UserRole.DOCTOR,
            "is_superuser": False
        },
        {
            "email": "doctor2@hospital.com",
            "username": "doctor2",
            "password": "doctor123",
            "full_name": "이의사",
            "role": UserRole.DOCTOR,
            "is_superuser": False
        },
        {
            "email": "nurse1@hospital.com",
            "username": "nurse1",
            "password": "nurse123",
            "full_name": "박간호사",
            "role": UserRole.NURSE,
            "is_superuser": False
        }
    ]
    
    created_users = []
    for user_data in users_data:
        # 이미 존재하는지 확인
        existing = db.query(User).filter(User.email == user_data["email"]).first()
        if existing:
            print(f"   ⚠️  이미 존재: {user_data['username']}")
            created_users.append(existing)
            continue
        
        user = User(
            email=user_data["email"],
            username=user_data["username"],
            hashed_password=pwd_context.hash(user_data["password"]),
            full_name=user_data["full_name"],
            role=user_data["role"],
            is_superuser=user_data["is_superuser"],
            is_active=True
        )
        db.add(user)
        created_users.append(user)
        print(f"   ✅ 생성: {user_data['full_name']} ({user_data['role'].value})")
    
    db.commit()
    print(f"✅ 사용자 {len(users_data)}명 생성 완료")
    return created_users


def create_sample_patients(db: Session):
    """샘플 환자 데이터 생성"""
    print("\n🏥 샘플 환자 데이터 생성 중...")
    
    patients_data = [
        {
            "name": "홍길동",
            "birth_date": date(1980, 5, 15),
            "gender": Gender.MALE,
            "phone": "010-1234-5678",
            "patient_number": "P2024001",
            "blood_type": "A+",
            "notes": "테스트 환자 1"
        },
        {
            "name": "김영희",
            "birth_date": date(1975, 8, 20),
            "gender": Gender.FEMALE,
            "phone": "010-9876-5432",
            "patient_number": "P2024002",
            "blood_type": "B+",
            "notes": "테스트 환자 2"
        }
    ]
    
    created_patients = []
    for patient_data in patients_data:
        existing = db.query(Patient).filter(
            Patient.patient_number == patient_data["patient_number"]
        ).first()
        if existing:
            print(f"   ⚠️  이미 존재: {patient_data['name']}")
            created_patients.append(existing)
            continue
        
        patient = Patient(**patient_data)
        db.add(patient)
        created_patients.append(patient)
        print(f"   ✅ 생성: {patient_data['name']} ({patient_data['patient_number']})")
    
    db.commit()
    print(f"✅ 환자 {len(patients_data)}명 생성 완료")
    return created_patients


def create_sample_visits(db: Session, patients, doctors):
    """샘플 진료 기록 생성"""
    print("\n📋 샘플 진료 기록 생성 중...")
    
    if not patients or not doctors:
        print("   ⚠️  환자 또는 의사 데이터 없음. 진료 기록 생성 스킵")
        return []
    
    visits_data = [
        {
            "patient": patients[0],
            "doctor": doctors[0],
            "chief_complaint": "복부 불편감, 소화 불량",
            "diagnosis_summary": "위내시경 검사 필요",
            "status": "COMPLETED"
        },
        {
            "patient": patients[1],
            "doctor": doctors[1] if len(doctors) > 1 else doctors[0],
            "chief_complaint": "상복부 통증",
            "diagnosis_summary": "조직 검사 진행",
            "status": "PENDING"
        }
    ]
    
    created_visits = []
    for visit_data in visits_data:
        visit = Visit(
            patient_id=visit_data["patient"].id,
            doctor_id=visit_data["doctor"].id,
            chief_complaint=visit_data["chief_complaint"],
            diagnosis_summary=visit_data["diagnosis_summary"],
            status=visit_data["status"],
            visit_date=datetime.utcnow()
        )
        db.add(visit)
        created_visits.append(visit)
        print(f"   ✅ 생성: 환자 {visit_data['patient'].name} - 의사 {visit_data['doctor'].full_name}")
    
    db.commit()
    print(f"✅ 진료 기록 {len(visits_data)}건 생성 완료")
    return created_visits


def create_sample_diagnoses(db: Session, visits):
    """샘플 AI 진단 결과 생성 (Multi-Task Learning)"""
    print("\n🤖 샘플 AI 진단 결과 생성 중...")
    
    if not visits:
        print("   ⚠️  진료 기록 없음. AI 진단 결과 생성 스킵")
        return
    
    diagnoses_data = [
        {
            "visit": visits[0],
            "prediction": "STIN",
            "prediction_kr": "장형선암",
            "confidence": 0.8734,
            "probabilities": {
                "STDI": 0.0521,
                "STNT": 0.0613,
                "STIN": 0.8734,
                "STMX": 0.0132
            },
            "probabilities_kr": {
                "미만형선암": 0.0521,
                "위염": 0.0613,
                "장형선암": 0.8734,
                "혼합형선암": 0.0132
            },
            "raw_logits": [1.2, 1.6, 3.5, 0.9],
            "tumor_ratio": 0.3245,
            "stroma_ratio": 0.2876,
            "normal_ratio": 0.2543,
            "immune_ratio": 0.1324,
            "background_ratio": 0.0012,
            "model_type": "UNet + ResNet50 Multi-Task Learning",
            "processing_time": 0.234,
            "device": "cuda"
        }
    ]
    
    for diag_data in diagnoses_data:
        diagnosis = Diagnosis(
            visit_id=diag_data["visit"].id,
            prediction=diag_data["prediction"],
            prediction_kr=diag_data["prediction_kr"],
            confidence=diag_data["confidence"],
            probabilities=diag_data["probabilities"],
            probabilities_kr=diag_data["probabilities_kr"],
            raw_logits=diag_data["raw_logits"],
            tumor_ratio=diag_data["tumor_ratio"],
            stroma_ratio=diag_data["stroma_ratio"],
            normal_ratio=diag_data["normal_ratio"],
            immune_ratio=diag_data["immune_ratio"],
            background_ratio=diag_data["background_ratio"],
            model_type=diag_data["model_type"],
            processing_time=diag_data["processing_time"],
            device=diag_data["device"],
            is_reviewed=0
        )
        db.add(diagnosis)
        print(f"   ✅ 생성: {diag_data['prediction_kr']} (신뢰도: {diag_data['confidence']:.2%})")
        print(f"      - 종양 비율: {diag_data['tumor_ratio']:.2%}")
        print(f"      - 간질 비율: {diag_data['stroma_ratio']:.2%}")
    
    db.commit()
    print(f"✅ AI 진단 결과 {len(diagnoses_data)}건 생성 완료")


def main():
    """메인 초기화 함수"""
    print("=" * 60)
    print("🏥 위암 분류 병원 관리 시스템 - 데이터베이스 초기화")
    print("   Multi-Task Learning (UNet + ResNet50) 지원")
    print(f"   DB: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    print("=" * 60)
    
    try:
        # MySQL 연결 확인
        if not check_mysql_connection():
            sys.exit(1)
        
        # 테이블 생성
        create_tables()
        
        # 데이터베이스 세션
        db = SessionLocal()
        
        try:
            # 사용자 생성
            users = create_users(db)
            doctors = [u for u in users if u.role == UserRole.DOCTOR]
            
            # 환자 생성
            patients = create_sample_patients(db)
            
            # 진료 기록 생성
            visits = create_sample_visits(db, patients, doctors)
            
            # AI 진단 결과 생성
            create_sample_diagnoses(db, visits)
            
            print("\n" + "=" * 60)
            print("🎉 데이터베이스 초기화 완료!")
            print("=" * 60)
            print("\n📊 생성된 데이터:")
            print(f"   - 사용자: {db.query(User).count()}명")
            print(f"   - 환자: {db.query(Patient).count()}명")
            print(f"   - 진료 기록: {db.query(Visit).count()}건")
            print(f"   - AI 진단: {db.query(Diagnosis).count()}건")
            
            print("\n🔐 기본 계정:")
            print("   관리자: admin / admin123")
            print("   의사1: doctor1 / doctor123")
            print("   의사2: doctor2 / doctor123")
            print("   간호사: nurse1 / nurse123")
            
            print("\n🚀 다음 단계:")
            print("   1. 모델 파일 배치: copy mtl_best.pth .")
            print("   2. 서버 실행: uvicorn app.main:app --reload")
            print("   3. API 문서: http://localhost:8000/api/v1/docs")
            print("=" * 60)
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
