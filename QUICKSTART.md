# 위암 분류 병원 관리 시스템 - 빠른 시작 가이드

## Multi-Task Learning (UNet + ResNet50) 지원

---

## 필수 요구사항

- **Python** 3.9 이상
- **Node.js** 18 이상 / npm
- (선택) NVIDIA GPU + CUDA 12.1 (AI 모델 GPU 가속)

> SQLite를 사용하므로 별도의 데이터베이스 서버 설치가 필요 없습니다.

---

## 1단계: 저장소 클론

```bash
git clone <repository-url>
cd gastric-hospital
```

---

## 2단계: 백엔드 설정

### 가상환경 생성

```bash
cd backend

# Python 가상환경 생성 및 활성화
python -m venv .venv

# Linux / Mac
source .venv/bin/activate

# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

# Windows CMD
# .\.venv\Scripts\activate.bat
```

### 패키지 설치

```bash
# 기본 패키지 설치
pip install -r requirements.txt

# (선택) AI 모델 사용 시 PyTorch 설치
# CPU 버전
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu

# GPU 버전 (CUDA 12.1)
# pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu121
```

> **참고**: PyTorch 없이도 서버는 정상 실행됩니다. AI 기능은 Mock 모드로 동작합니다.

### 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env
```

필요에 따라 `.env` 파일을 수정합니다:

```env
DATABASE_URL=sqlite:///./gastric_hospital.db
SECRET_KEY=your-random-secret-key-32-chars-minimum
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
AI_MODEL_PATH=unet_resnet50_best.pth
AI_DEVICE=cpu
DEBUG=True
```

### 데이터베이스 초기화

```bash
python init_db.py
```

**예상 출력:**
```
============================================================
  위암 분류 병원 관리 시스템 - 데이터베이스 초기화
  Multi-Task Learning (UNet + ResNet50) 지원
============================================================
테이블 생성 중...
  테이블 생성 완료: users, patients, visits, diagnoses

사용자 계정 생성 중...
  생성: 시스템 관리자 (ADMIN)
  생성: 김의사 (DOCTOR)
  생성: 이의사 (DOCTOR)
  생성: 박간호사 (NURSE)

샘플 환자 데이터 생성 중...
  생성: 홍길동 (P2024001)
  생성: 김영희 (P2024002)

데이터베이스 초기화 완료!
```

### (선택) AI 모델 파일 배치

```bash
# UNet + ResNet50 Multi-Task Learning 모델 파일 복사
cp /path/to/unet_resnet50_best.pth .

# 파일 확인
ls -la unet_resnet50_best.pth
```

> 모델 파일이 없어도 서버는 정상 실행됩니다 (Mock 모드).

### 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**접속 확인:**
- API 문서: http://localhost:8000/api/v1/docs
- Health Check: http://localhost:8000/health

---

## 3단계: 프론트엔드 설정

```bash
cd frontend

# 패키지 설치
npm install

# 환경 변수 설정
cp .env.example .env.local

# 개발 서버 실행
npm run dev
```

**접속:** http://localhost:3000

---

## 4단계: 로그인 및 테스트

### 기본 계정

| 역할 | 아이디 | 비밀번호 |
|------|--------|----------|
| 관리자 | admin | admin123 |
| 의사 1 | doctor1 | doctor123 |
| 의사 2 | doctor2 | doctor123 |
| 간호사 | nurse1 | nurse123 |

### API 테스트

```bash
# Health Check
curl http://localhost:8000/health

# 로그인 테스트
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"doctor1","password":"doctor123"}'

# AI 진단 테스트 (통합 워크플로우)
curl -X POST http://localhost:8000/api/v1/clinical/diagnose \
  -H "Authorization: Bearer <TOKEN>" \
  -F "patient_id=1" \
  -F "chief_complaint=복통" \
  -F "image=@test_image.jpg"
```

---

## 문제 해결

### bcrypt 관련 오류
```bash
pip install passlib[bcrypt] bcrypt==4.0.1
```

### conda 자동 활성화 충돌
```bash
conda config --set auto_activate_base false
```

### PowerShell 실행 정책 (Windows)
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 포트 충돌
```bash
# Linux/Mac
lsof -i :8000
kill -9 <PID>

# Windows
netstat -ano | findstr :8000
taskkill /F /PID <PID>
```

### 데이터베이스 재초기화
```bash
cd backend
rm -f gastric_hospital.db
python init_db.py
```

---

## Multi-Task Learning 특징

### Classification (분류) - 4클래스
| 코드 | 한국어 | 영어 |
|------|--------|------|
| STDI | 미만형 선암 | Diffuse-type adenocarcinoma |
| STNT | 위염 | Gastritis |
| STIN | 장형 선암 | Intestinal-type adenocarcinoma |
| STMX | 혼합형 선암 | Mixed-type adenocarcinoma |

### Segmentation (세그멘테이션) - 5클래스
| 클래스 | 한국어 | 설명 |
|--------|--------|------|
| Background | 배경 | 비조직 영역 |
| Tumor | 종양 | 암 조직 영역 |
| Stroma | 기질 | 결합 조직 |
| Normal | 정상 | 정상 점막 조직 |
| Immune | 면역세포 | 면역 세포 침윤 영역 |

---

## 다음 단계

1. 프론트엔드에서 로그인 후 대시보드 확인
2. 환자 등록 및 AI 진단 테스트
3. 진료 기록 조회 및 필터링
4. (선택) 프로덕션 환경 설정 및 Docker 배포

---

**설치 완료!**
