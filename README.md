# 위암 진단 병원 관리 시스템

## Gastric Cancer Diagnosis Hospital Management System

위암 세포 현미경 이미지를 AI(Multi-Task Learning)로 분석하여 **분류(Classification)** 와 **세그멘테이션(Segmentation)** 을 동시에 수행하는 풀스택 병원 관리 시스템입니다.

UNet + ResNet50 기반의 멀티태스크 러닝 모델을 활용하여, 하나의 이미지에서 위암 유형 분류(4종)와 조직 영역 분할(5클래스)을 동시에 수행합니다. 이를 통해 의료진은 AI 보조 진단 결과를 참고하여 보다 신속하고 정확한 의사결정을 내릴 수 있습니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **JWT 인증** | 로그인, 토큰 발급/갱신, 역할 기반 접근 제어 (관리자/의사/간호사) |
| **환자 관리** | 환자 등록, 목록 조회(페이지네이션), 상세 정보 관리 |
| **AI 진단 (비동기)** | Celery 태스크 큐 기반 비동기 추론 + 동적 배칭 |
| **진료 기록** | 진료 내역 생성, 필터링(환자별/의사별/날짜별/상태별), 상세 조회 |
| **대시보드** | 전체 통계(환자 수, 진료 건수, 진단 건수, 오늘 진료), 암 유형별 분포 |
| **진단 리뷰** | 의사가 AI 진단 결과를 검토/승인하는 워크플로우 |
| **Docker 배포** | Docker Compose로 전체 시스템 원클릭 배포 (Redis + PostgreSQL + Celery) |

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| **백엔드** | Python 3.12 / FastAPI 0.109+ / SQLAlchemy 2.0 / Celery 5.4 |
| **프론트엔드** | Next.js 14 (App Router) / TypeScript / Tailwind CSS / Axios |
| **AI 모델** | PyTorch / UNet + ResNet50 (Multi-Task Learning) / segmentation-models-pytorch |
| **태스크 큐** | Celery + Redis (브로커 + 결과 백엔드) / 동적 배칭 |
| **데이터베이스** | PostgreSQL (Docker) / MySQL (로컬) / SQLite (폴백) |
| **인프라** | Docker Compose / Nginx 리버스 프록시 / NVIDIA GPU 지원 |

---

## 아키텍처

```
                    ┌─────────────┐
                    │   Nginx :80 │  (리버스 프록시)
                    └─────┬───────┘
                          │
              ┌───────────┴───────────┐
              │                       │
    ┌─────────▼───────┐    ┌──────────▼────────┐
    │ Next.js :3000   │    │  FastAPI :8000     │
    │ (프론트엔드)     │    │  (REST API)        │
    └─────────────────┘    └────────┬───────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     │              │              │
              ┌──────▼─────┐ ┌─────▼──────┐ ┌────▼──────────┐
              │ Redis :6379│ │ PostgreSQL  │ │ Celery Worker │
              │ (Broker +  │ │ :5432      │ │ (GPU 추론)    │
              │  Backend)  │ │            │ │ 동적 배칭     │
              └────────────┘ └────────────┘ └───────────────┘
```

### 비동기 AI 진단 흐름

```
1. 클라이언트 → POST /clinical/diagnose (이미지 업로드)
2. FastAPI → Celery 태스크 제출 → task_id 즉시 반환
3. 클라이언트 → GET /clinical/diagnose/{task_id} (1.5초 간격 폴링)
4. Celery Worker → 동적 배칭 → GPU 배치 추론
5. 결과 완료 → Redis에 저장 → 폴링 응답으로 반환
6. FastAPI → DB에 Visit + Diagnosis 저장
```

---

## 프로젝트 구조

```
.
├── backend/                          # FastAPI 백엔드
│   ├── app/
│   │   ├── api/api_v1/
│   │   │   ├── api.py                # API 라우터 통합
│   │   │   └── endpoints/
│   │   │       ├── auth.py           # 로그인, /me, 토큰 갱신
│   │   │       ├── patients.py       # 환자 CRUD
│   │   │       ├── visits.py         # 진료 기록 CRUD + 필터링 + 통계
│   │   │       ├── diagnoses.py      # 진단 결과 CRUD + 리뷰 시스템
│   │   │       ├── clinical.py       # 통합 워크플로우 (비동기 Celery)
│   │   │       ├── ai.py             # AI 예측 + 태스크 폴링
│   │   │       └── users.py          # 사용자 관리 (관리자)
│   │   ├── core/
│   │   │   ├── config.py             # 환경 설정 (Celery/Redis 포함)
│   │   │   ├── celery_app.py         # Celery 앱 설정
│   │   │   ├── database.py           # SQLAlchemy (PostgreSQL/MySQL/SQLite)
│   │   │   └── security.py           # JWT 검증, 비밀번호 해싱
│   │   ├── models/                   # SQLAlchemy ORM 모델
│   │   ├── schemas/                  # Pydantic 요청/응답 스키마
│   │   ├── services/
│   │   │   ├── ai_service.py         # AI 서비스 (배치 추론 지원)
│   │   │   └── model_mt.py           # GastricMTLModel
│   │   ├── worker/
│   │   │   ├── __init__.py           # 워커 패키지
│   │   │   ├── tasks.py              # Celery 태스크 정의
│   │   │   └── batcher.py            # 동적 배칭 엔진
│   │   └── main.py                   # FastAPI 앱 엔트리포인트
│   ├── Dockerfile                    # 백엔드 Dockerfile (multi-stage)
│   ├── requirements.txt              # Python 패키지 목록
│   └── .env.example                  # 환경 변수 템플릿
│
├── frontend/                         # Next.js 프론트엔드
│   ├── src/
│   │   ├── app/(auth)/               # 인증 필요 페이지
│   │   │   ├── clinical/page.tsx     # AI 진단 (비동기 폴링 UI)
│   │   │   ├── dashboard/page.tsx    # 대시보드
│   │   │   ├── patients/page.tsx     # 환자 관리
│   │   │   └── visits/page.tsx       # 진료 내역
│   │   └── lib/api.ts                # API 클라이언트 (폴링 유틸리티)
│   ├── Dockerfile                    # 프론트엔드 Dockerfile (standalone)
│   └── next.config.js                # Next.js 설정
│
├── docker-compose.yml                # 프로덕션 Docker Compose
├── docker-compose.dev.yml            # 개발용 Docker Compose (핫리로드)
├── .env.docker.example               # Docker 환경 변수 템플릿
├── nginx/nginx.conf                  # Nginx 리버스 프록시 설정
├── models/                           # AI 모델 파일 마운트 디렉토리
└── README.md
```

---

## Docker로 실행하기

### 사전 요구사항

- **Docker** 20.10+
- **Docker Compose** v2+
- (선택) NVIDIA GPU + [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

### 프로덕션 실행

```bash
# 1. 환경 변수 설정
cp .env.docker.example .env.docker

# SECRET_KEY 생성 및 설정 (필수!)
python -c "import secrets; print(secrets.token_urlsafe(48))"
# 출력된 값을 .env.docker의 SECRET_KEY에 붙여넣기

# 2. AI 모델 파일 배치 (선택 - 없으면 DEMO 모드)
# cp /path/to/mtl_best.pth models/

# 3. Docker Compose 실행
docker compose up -d --build

# 4. DB 초기화 (최초 실행 시)
docker compose exec fastapi python init_db.py

# 5. 접속
# 프론트엔드: http://localhost:3000
# API 문서:   http://localhost:8000/api/v1/docs
# Nginx:     http://localhost (포트 80)
```

### 개발 환경 (핫리로드)

```bash
# 소스 코드 변경 시 자동 재시작
docker compose -f docker-compose.dev.yml up --build

# FastAPI: 소스 마운트 + --reload
# Celery: watchmedo auto-restart
# Next.js: npm run dev (소스 마운트)
```

### Docker 서비스 구성

| 서비스 | 포트 | 설명 |
|--------|------|------|
| `redis` | 6379 | Celery 메시지 브로커 + 결과 백엔드 |
| `postgres` | 5432 | PostgreSQL 데이터베이스 |
| `fastapi` | 8000 | FastAPI REST API 서버 |
| `celery-worker` | - | AI 모델 추론 워커 (GPU) |
| `frontend` | 3000 | Next.js 프론트엔드 |
| `nginx` | 80 | 리버스 프록시 (프론트+API 통합) |

### GPU 사용 시 (NVIDIA)

```bash
# .env.docker에서 설정
AI_DEVICE=cuda

# docker-compose.yml의 celery-worker에 GPU 할당이 이미 설정됨
# deploy.resources.reservations.devices: nvidia
```

### 유용한 Docker 명령어

```bash
# 로그 확인
docker compose logs -f fastapi
docker compose logs -f celery-worker

# 서비스 상태 확인
docker compose ps

# DB 접속
docker compose exec postgres psql -U gastric -d gastric_hospital

# Redis 접속
docker compose exec redis redis-cli

# Celery 워커 상태 확인
docker compose exec celery-worker celery -A app.core.celery_app:celery_app inspect active

# 전체 중지 및 볼륨 삭제
docker compose down -v
```

---

## 로컬 개발 (Docker 없이)

### 사전 요구사항

- **Python** 3.9+
- **Node.js** 18+
- **MySQL** 또는 **PostgreSQL** (또는 SQLite)
- **Redis** (Celery 사용 시)

### 1. 백엔드 실행

```bash
cd backend

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate

# 패키지 설치
pip install -r requirements.txt

# (선택) PyTorch 설치
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu

# 환경 변수 설정
cp .env.example .env
# .env 파일에서 SECRET_KEY, ENCRYPTION_KEY를 실제 값으로 변경

# 데이터베이스 초기화
python init_db.py

# 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Celery 워커 실행 (AI 비동기 추론용)

```bash
# Redis 서버 실행 (별도 터미널)
redis-server

# Celery 워커 시작 (별도 터미널)
cd backend
celery -A app.core.celery_app:celery_app worker \
  --loglevel=info --concurrency=1 --pool=solo \
  -Q ai_inference,db_operations,default
```

### 3. 프론트엔드 실행

```bash
cd frontend

# 패키지 설치
npm install

# 환경 변수 설정
cp .env.example .env.local

# 개발 서버 실행
npm run dev
```

### 4. 접속

| 서비스 | URL |
|--------|-----|
| 프론트엔드 | http://localhost:3000 |
| 백엔드 API 문서 (Swagger) | http://localhost:8000/api/v1/docs |
| 헬스 체크 | http://localhost:8000/health |

---

## 테스트 계정

`init_db.py` 실행 시 자동으로 생성되는 기본 계정입니다.

| 역할 | 아이디 | 비밀번호 | 이름 |
|------|--------|----------|------|
| 관리자 | admin | admin123 | 시스템 관리자 |
| 의사 1 | doctor1 | doctor123 | 김의사 |
| 의사 2 | doctor2 | doctor123 | 이의사 |
| 간호사 | nurse1 | nurse123 | 박간호사 |

---

## API 엔드포인트

### 인증
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/auth/login` | 로그인 (JWT 발급) |
| GET | `/api/v1/auth/me` | 현재 사용자 정보 |

### AI 진단 (비동기)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/clinical/diagnose` | 진료+AI 진단 태스크 제출 -> task_id 반환 |
| GET | `/api/v1/clinical/diagnose/{task_id}` | 진단 결과 폴링 |
| GET | `/api/v1/clinical/stats` | 진료 통계 |
| POST | `/api/v1/ai/predict` | 단독 AI 예측 태스크 제출 |
| GET | `/api/v1/ai/tasks/{task_id}` | AI 태스크 상태 폴링 |
| GET | `/api/v1/ai/model-info` | 모델 정보 |

### 환자/진료/진단
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET/POST | `/api/v1/patients/` | 환자 목록/등록 |
| GET | `/api/v1/visits/` | 진료 내역 |
| GET | `/api/v1/diagnoses/` | 진단 결과 |

---

## 환경 변수

### 백엔드 (`backend/.env`)

```env
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/gastric_hospital
SECRET_KEY=your-secret-key-32-chars-minimum
ENCRYPTION_KEY=your-encryption-key
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
BATCH_SIZE=8
BATCH_TIMEOUT_MS=100
CELERY_WORKER_CONCURRENCY=1
AI_MODEL_PATH=mtl_best.pth
AI_DEVICE=cpu
```

### Docker (`.env.docker`)

```env
DATABASE_URL=postgresql+psycopg2://gastric:gastric_secret@postgres:5432/gastric_hospital
SECRET_KEY=your-production-secret-key
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
AI_MODEL_PATH=/app/models/mtl_best.pth
AI_DEVICE=cuda
```

---

## AI 모델

### 아키텍처

```
입력 이미지 (512x512)
    │
    ▼
┌──────────────────┐
│  ResNet50 Encoder │  (ImageNet 사전학습)
│  (공유 특성 추출)  │
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐  ┌──────────────┐
│ Decoder │  │ Classification│
│ (UNet)  │  │     Head      │
└────┬───┘  └──────┬───────┘
     │              │
     ▼              ▼
  세그멘테이션    분류 결과
  마스크 (5cls)   (4cls)
```

### 분류 (4클래스)

| 코드 | 한국어 | 설명 |
|------|--------|------|
| STDI | 미만형선암 | 세포 간 결합이 느슨한 유형 |
| STNT | 위염 | 비암성 염증 상태 |
| STIN | 장형선암 | 선 구조를 형성하는 유형 |
| STMX | 혼합형선암 | 미만형+장형 혼합 |

### 세그멘테이션 (5클래스)

| 클래스 | 색상 | 설명 |
|--------|------|------|
| Background | 검정 | 비조직 영역 |
| Tumor | 빨강 | 암 조직 |
| Stroma | 초록 | 결합 조직 |
| Normal | 파랑 | 정상 점막 |
| Immune | 노랑 | 면역세포 침윤 |

### 동적 배칭

Celery 워커 내에서 동적 배칭 엔진이 동작합니다:
- `BATCH_SIZE` (기본 8): 최대 배치 크기
- `BATCH_TIMEOUT_MS` (기본 100ms): 첫 요청 후 대기 시간
- 배치가 가득 차거나 타임아웃 시 GPU 배치 추론 실행
- 워커당 모델 1회 로드 (GPU 메모리 효율)

---

## 문제 해결

### Docker 관련

```bash
# GPU를 인식하지 못하는 경우
nvidia-smi  # GPU 확인
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# 포트 충돌
docker compose down
lsof -i :8000  # 사용 중인 프로세스 확인

# DB 초기화
docker compose down -v  # 볼륨 삭제
docker compose up -d --build
docker compose exec fastapi python init_db.py
```

### AI 모델 DEMO 모드

모델 파일(`mtl_best.pth`)이 없으면 자동으로 Mock 모드로 동작합니다.
실제 모델 파일을 `models/` 디렉토리에 배치하면 GPU 추론이 활성화됩니다.

---

## 라이선스

이 프로젝트는 학술/교육 목적으로 개발되었습니다.
