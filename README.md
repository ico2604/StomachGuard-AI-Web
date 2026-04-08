# 위암 진단 AI 병원 관리 시스템

> 위암 세포 현미경 이미지를 AI(Multi-Task Learning)로 분석하여 **암 유형 분류(4종)** 와 **조직 영역 분할(5클래스)** 을 동시에 수행하는 풀스택 병원 관리 시스템

---

## 프로젝트 소개

### 해결하려는 문제

병리의사가 위암 조직 슬라이드를 육안으로 판독하는 과정은 **시간이 오래 걸리고**, 판독자 간 **일관성이 떨어지는** 문제가 있습니다.  
본 시스템은 **AI 보조 진단 파이프라인**을 제공하여, 이미지 업로드 후 수 초 내에 암 유형 분류와 조직 세그멘테이션 결과를 시각화합니다.

### 핵심 가치

| 구분 | 내용 |
|------|------|
| **자동화된 진단 워크플로우** | 환자 선택 → 이미지 업로드 → AI 추론 → 결과 시각화까지 단일 화면에서 완료 |
| **비동기 AI 추론** | Celery + Redis 기반 태스크 큐로 무거운 GPU 추론을 백그라운드 처리 |
| **동적 배칭** | 여러 요청을 모아 GPU 배치 추론하여 처리량 극대화 |
| **역할 기반 접근 제어** | 관리자/의사/간호사별 권한 분리, JWT 인증 |
| **원클릭 배포** | Docker Compose로 6개 서비스를 한 번에 기동 |

---

## 기술 스택

| 계층 | 기술 | 역할 |
|------|------|------|
| **프론트엔드** | Next.js 14 (App Router), TypeScript, Tailwind CSS, Axios | SPA + SSR/SSG, 반응형 UI |
| **백엔드** | FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2 | REST API, ORM, 스키마 검증 |
| **AI 모델** | PyTorch, segmentation-models-pytorch (UNet + ResNet50) | 멀티태스크 러닝 (분류 + 세그멘테이션) |
| **태스크 큐** | Celery 5.4, Redis 7 | 비동기 추론, 동적 배칭 |
| **데이터베이스** | PostgreSQL 16 (운영) / MySQL 8 (로컬) / SQLite (폴백) | 다중 DB 자동 감지 |
| **인프라** | Docker Compose, Nginx, 멀티스테이지 Dockerfile | 컨테이너 기반 마이크로서비스 배포 |
| **인증** | JWT (HS256), OAuth2 Password Flow, bcrypt | 무상태 인증 |

---

## 시스템 아키텍처

```
                    ┌─────────────┐
                    │   Nginx :80 │  (리버스 프록시)
                    └──────┬──────┘
                           │
               ┌───────────┴───────────┐
               │                       │
     ┌─────────▼────────┐   ┌─────────▼────────┐
     │  Next.js :3000   │   │  FastAPI :8000    │
     │  (프론트엔드)      │   │  (REST API)       │
     └──────────────────┘   └────────┬──────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      │              │              │
               ┌──────▼──────┐ ┌────▼───────┐ ┌───▼───────────┐
               │ Redis :6379 │ │ PostgreSQL │ │ Celery Worker │
               │ (브로커 +   │ │ :5432      │ │ (GPU 추론)    │
               │  결과 저장)  │ │            │ │ + 동적 배칭   │
               └─────────────┘ └────────────┘ └───────────────┘
```

### AI 진단 요청 흐름

```
① 의사가 이미지 업로드  →  POST /clinical/diagnose
② FastAPI가 인증 검증 + 이미지 base64 인코딩
③ Celery 태스크를 "ai_inference" 큐에 제출  →  task_id 즉시 반환
④ 워커가 태스크를 수신, DynamicBatcher에 전달
⑤ 배처가 요청을 모음 (최대 8개 또는 100ms 타임아웃)
⑥ GPU 배치 추론: 분류 + 세그멘테이션 동시 수행
⑦ 결과를 Redis에 저장, DB에 Visit + Diagnosis 레코드 생성
⑧ 프론트엔드가 GET /clinical/diagnose/{task_id} 로 1.5초 간격 폴링
⑨ 상태가 COMPLETED가 되면 예측 결과 + 세그멘테이션 오버레이 렌더링
```

---

## 주요 기능 상세

### 1. Multi-Task Learning AI 모델

```
입력 이미지 (512×512)
       │
       ▼
┌──────────────────┐
│ ResNet50 Encoder │  (ImageNet 사전학습 가중치)
│ (공유 특성 추출)   │
└────────┬─────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌───────────────┐
│ UNet   │ │ Classification │
│Decoder │ │ Head           │
└───┬────┘ │ FC(2048→512→4)│
    │      │ +BN+ReLU+Drop │
    ▼      └───────┬───────┘
 세그멘테이션        ▼
 마스크 (5cls)   분류 결과 (4cls)
```

**분류 클래스 (4종)**

| 코드 | 한국어명 | 설명 |
|------|----------|------|
| STDI | 미만형선암 | 세포 간 결합이 느슨한 유형 |
| STNT | 위염 | 비암성 염증 상태 |
| STIN | 장형선암 | 선 구조를 형성하는 유형 |
| STMX | 혼합형선암 | 미만형 + 장형 혼합 |

**세그멘테이션 클래스 (5종)**

| 클래스 | 색상 | 설명 |
|--------|------|------|
| Background | 검정 | 비조직 영역 |
| Tumor | 빨강 | 암 조직 |
| Stroma | 초록 | 결합 조직 |
| Normal | 파랑 | 정상 점막 |
| Immune | 노랑 | 면역세포 침윤 |

- 모델 파일이 없을 경우 **Mock 모드**로 자동 전환되어 데모 데이터를 반환합니다
- 이를 통해 **어떤 환경에서든 애플리케이션이 정상 기동**됩니다

### 2. 동적 배칭 엔진

Celery 워커 내부에서 동작하는 **DynamicBatcher**가 GPU 활용률을 극대화합니다.

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `BATCH_SIZE` | 8 | 최대 배치 크기 |
| `BATCH_TIMEOUT_MS` | 100ms | 첫 요청 이후 대기 시간 |

**동작 원리:**
- 데몬 스레드가 `queue.Queue`에서 요청을 수집
- 큐가 `BATCH_SIZE`에 도달하거나 `BATCH_TIMEOUT_MS`가 경과하면 배치 추론 실행
- 각 요청은 `concurrent.futures.Future`를 가지고 있어, 배치 완료 시 개별 결과를 전달받음
- 배치 추론 실패 시 **개별 추론으로 자동 폴백**

### 3. Celery 비동기 태스크 아키텍처

| 구성 요소 | 설명 |
|-----------|------|
| **큐 분리** | `ai_inference` (GPU 바운드) / `db_operations` (I/O 바운드) |
| **태스크 라우팅** | `predict_single` → ai_inference, `save_diagnosis_result` → db_operations |
| **속도 제한** | 워커당 100회/분 |
| **모델 로딩** | `worker_process_init` 시그널로 워커 시작 시 1회만 로드 |
| **결과 저장** | Redis, TTL 1시간 |
| **재시도** | 최대 2회, 5초 간격 |

### 4. 프론트엔드 폴링 패턴

`pollTaskResult<T>` 제네릭 유틸리티를 통해 Celery 태스크 결과를 폴링합니다.

```
[태스크 제출] → task_id 수신
     ↓
[폴링 시작] GET /clinical/diagnose/{task_id} (1.5초 간격)
     ↓
  PENDING → "AI 모델 대기 중..." (스피너)
  PROCESSING → "추론 진행 중..." (진행바)
  COMPLETED → 결과 렌더링
  FAILED → 에러 메시지 표시
```

- 최대 120회 시도 (약 3분 타임아웃)
- `onProgress` 콜백으로 실시간 UI 상태 업데이트
- TypeScript 제네릭 `TaskResult<T>`로 타입 안전성 확보

### 5. 인증 및 권한 관리

**JWT 인증 흐름:**

```
① POST /auth/login (username + password, form-urlencoded)
② 백엔드: bcrypt 검증 → JWT 발급 (HS256, 30분 만료)
③ 프론트엔드: localStorage에 토큰 저장
④ Axios 요청 인터셉터: 모든 요청에 Authorization: Bearer 헤더 자동 첨부
⑤ 401 응답 시: 응답 인터셉터가 토큰 삭제 (로그인 요청 제외)
⑥ (auth)/layout.tsx: 토큰 없으면 /login으로 리다이렉트
```

**역할 기반 접근 제어:**

| 역할 | 권한 |
|------|------|
| 관리자 (ADMIN) | 전체 기능 + 사용자 관리 |
| 의사 (DOCTOR) | AI 진단, 환자 관리, 진료 기록 |
| 간호사 (NURSE) | 환자 조회, 진료 기록 조회 |

---

## 해결한 기술적 문제

### 문제 1: 307 리다이렉트로 인한 인증 토큰 유실

**상황:** FastAPI의 기본 설정(`redirect_slashes=True`)이 `/api/v1/visits` 요청을 `/api/v1/visits/`로 307 리다이렉트합니다.  
프록시 체인(Next.js → Nginx → FastAPI)에서 이 리다이렉트가 발생하면:
1. 일부 HTTP 클라이언트가 POST → GET으로 메서드를 변경
2. `Authorization` 헤더가 제거됨
3. 요청 본문이 유실됨

**해결:** `redirect_slashes=False`를 설정하고, 커스텀 `TrailingSlashMiddleware`로 **서버 내부에서 경로를 재작성**합니다.

```python
# ASGI scope의 path를 직접 수정 → HTTP 왕복 없음
request.scope["path"] = path + "/"
```

- 숫자 ID (`/visits/123`), UUID/Celery task ID (하이픈 포함), 액션 엔드포인트 (`/auth/login`) 등은 **스킵 로직**으로 제외
- 미들웨어 등록 순서: CORS(바깥쪽) → TrailingSlash(안쪽) → Router

### 문제 2: JWT 만료 시 사용자 상태 불일치

**상황:** 세션 중 JWT가 만료되면 API 호출이 401을 반환하지만, 프론트엔드가 이를 적절히 처리하지 못해 사용자에게 알 수 없는 오류가 표시됩니다.

**해결:** Axios **응답 인터셉터**를 추가하여:
- 401 응답 감지 시 `localStorage`에서 토큰과 사용자 정보를 즉시 삭제
- **로그인 요청 자체**(`/auth/login`)의 401은 "잘못된 비밀번호"이므로 토큰 삭제하지 않음
- `typeof window !== 'undefined'` 가드로 Next.js SSR 환경에서의 오류 방지
- 실제 리다이렉트는 `(auth)/layout.tsx`에서 담당 (역할 분리)

### 문제 3: 페이지 이동 시 중복 인증 호출 및 화면 깜빡임

**상황:** 인증 레이아웃이 모든 페이지 전환마다 `GET /auth/me`를 호출하여 불필요한 네트워크 요청이 발생하고, 로그인 직후 `localStorage` 쓰기 완료 전에 인증 체크가 실행되어 화면이 깜빡였습니다.

**해결:**
- `useRef(hasChecked)`로 **최초 인증 성공 후 재검증 생략** (SPA 내부 이동 시 API 호출 없음)
- `setTimeout(checkAuth, 50)`으로 `localStorage` 쓰기 완료를 보장
- `StorageEvent` 리스너로 **다른 탭에서의 로그아웃을 동기화**
- 인증 확인 중 **전체 화면 스피너**를 표시하여 미인증 콘텐츠 노출(FOUC) 방지

---

## 데이터 모델

```
Users (사용자)
 ├── id, username, full_name, role, hashed_password, is_active
 └── 1:N → Visits (담당 의사로서)

Patients (환자)
 ├── id, name, patient_number, 암호화된 개인정보
 └── 1:N → Visits (cascade delete)

Visits (진료 기록)
 ├── id, patient_id, doctor_id, visit_date, chief_complaint
 ├── diagnosis_summary, treatment_plan, notes, status
 └── 1:N → Diagnoses (cascade delete)

Diagnoses (AI 진단 결과)
 └── id, visit_id, cancer_type, confidence, probabilities, segmentation_data
```

---

## 프로젝트 구조

```
.
├── backend/                           # FastAPI 백엔드
│   ├── app/
│   │   ├── api/api_v1/
│   │   │   ├── api.py                 # 라우터 통합 (7개 모듈)
│   │   │   └── endpoints/
│   │   │       ├── auth.py            # 로그인, /me, 토큰 갱신
│   │   │       ├── patients.py        # 환자 CRUD
│   │   │       ├── visits.py          # 진료 기록 CRUD + 필터링
│   │   │       ├── diagnoses.py       # 진단 결과 CRUD + 리뷰
│   │   │       ├── clinical.py        # 통합 워크플로우 (비동기 Celery)
│   │   │       ├── ai.py             # AI 예측 + 태스크 폴링
│   │   │       └── users.py          # 사용자 관리 (관리자 전용)
│   │   ├── core/
│   │   │   ├── config.py             # Pydantic Settings (환경 변수)
│   │   │   ├── celery_app.py         # Celery 앱 설정 + 큐 라우팅
│   │   │   ├── database.py           # SQLAlchemy (PostgreSQL/MySQL/SQLite 자동 감지)
│   │   │   └── security.py           # JWT 검증, bcrypt 해싱
│   │   ├── models/                    # SQLAlchemy ORM 모델
│   │   ├── schemas/                   # Pydantic 요청/응답 스키마
│   │   ├── services/
│   │   │   ├── ai_service.py         # MTL AI 서비스 (배치 추론 지원)
│   │   │   └── model_mt.py           # GastricMTLModel (UNet + ResNet50)
│   │   ├── worker/
│   │   │   ├── tasks.py              # Celery 태스크 (predict_single, save_diagnosis_result)
│   │   │   └── batcher.py            # 동적 배칭 엔진 (DynamicBatcher)
│   │   └── main.py                    # FastAPI 앱 + TrailingSlashMiddleware
│   ├── Dockerfile                     # 멀티스테이지 (fastapi / celery-worker 타겟)
│   └── requirements.txt
│
├── frontend/                          # Next.js 프론트엔드
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/               # 인증 필요 라우트 그룹
│   │   │   │   ├── layout.tsx         # 인증 가드 + 토큰 검증
│   │   │   │   ├── clinical/page.tsx  # AI 진단 (폴링 UI)
│   │   │   │   ├── dashboard/page.tsx # 대시보드 (통계)
│   │   │   │   ├── patients/page.tsx  # 환자 관리
│   │   │   │   └── visits/page.tsx    # 진료 내역 (필터링 + 모달)
│   │   │   └── login/page.tsx         # 로그인
│   │   ├── components/                # 공용 컴포넌트 (Navbar, Spinner 등)
│   │   ├── lib/api.ts                 # API 클라이언트 + 폴링 유틸리티
│   │   └── types/                     # TypeScript 타입 정의
│   ├── Dockerfile                     # 멀티스테이지 (deps → builder → runner)
│   └── next.config.js                 # API 프록시 rewrite 설정
│
├── docker-compose.yml                 # 프로덕션 (6개 서비스)
├── docker-compose.dev.yml             # 개발용 (핫리로드)
├── nginx/nginx.conf                   # Nginx 리버스 프록시 설정
├── models/                            # AI 모델 파일 디렉토리
└── .env.docker.example                # Docker 환경 변수 템플릿
```

---

## Docker 배포

### 서비스 구성

| 서비스 | 이미지 / 빌드 | 포트 | 헬스체크 | 역할 |
|--------|---------------|------|----------|------|
| **redis** | redis:7-alpine | 6379 | `redis-cli ping` | Celery 메시지 브로커 + 결과 저장소 |
| **postgres** | postgres:16-alpine | 5432 | `pg_isready` | 운영 데이터베이스 |
| **fastapi** | backend/Dockerfile (target: fastapi) | 8000 | `curl /health` | REST API 서버 |
| **celery-worker** | backend/Dockerfile (target: celery-worker) | - | - | AI 추론 워커 (GPU 예약) |
| **frontend** | frontend/Dockerfile (standalone) | 3000 | `wget localhost:3000` | 프론트엔드 서버 |
| **nginx** | nginx:alpine | 80 | - | 리버스 프록시 |

- `depends_on` + `condition: service_healthy`로 **기동 순서 보장**
- 멀티스테이지 빌드로 이미지 크기 최소화 (프론트엔드 ~100MB)
- Celery 워커에 **NVIDIA GPU 리소스 예약** 설정 포함

### 실행 방법

```bash
# 1. 환경 변수 준비
cp .env.docker.example .env.docker
# SECRET_KEY에 실제 값 설정 (32자 이상)

# 2. 실행
docker compose up -d --build

# 3. DB 초기화 (최초 1회)
docker compose exec fastapi python init_db.py

# 4. 접속
#    프론트엔드: http://localhost:3000
#    API 문서:   http://localhost:8000/api/v1/docs
```

### 개발 환경 (핫리로드)

```bash
docker compose -f docker-compose.dev.yml up --build
# FastAPI: --reload / Celery: watchmedo / Next.js: npm run dev
```

---

## 로컬 개발 (Docker 없이)

### 백엔드

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # SECRET_KEY, ENCRYPTION_KEY 설정
python init_db.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Celery 워커 (별도 터미널)

```bash
redis-server                   # Redis 기동
cd backend
celery -A app.core.celery_app:celery_app worker \
  --loglevel=info --concurrency=1 --pool=solo \
  -Q ai_inference,db_operations,default
```

### 프론트엔드

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev                    # http://localhost:3000
```

---

## API 엔드포인트

### 인증
| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| POST | `/api/v1/auth/login` | 로그인 (JWT 발급) | 공개 |
| GET | `/api/v1/auth/me` | 현재 사용자 정보 | 로그인 |

### AI 진단 (비동기)
| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| POST | `/api/v1/clinical/diagnose` | 진료 + AI 진단 태스크 제출 | 의사/관리자 |
| GET | `/api/v1/clinical/diagnose/{task_id}` | 진단 결과 폴링 | 의사/관리자 |
| GET | `/api/v1/clinical/stats` | 대시보드 통계 | 로그인 |
| POST | `/api/v1/ai/predict` | AI 예측 (단독) | 공개 |
| GET | `/api/v1/ai/tasks/{task_id}` | AI 태스크 상태 | 공개 |
| GET | `/api/v1/ai/model-info` | 모델 정보 | 공개 |

### 환자 / 진료 / 진단
| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| GET/POST | `/api/v1/patients/` | 환자 목록 / 등록 | 로그인 |
| GET | `/api/v1/patients/{id}` | 환자 상세 | 로그인 |
| GET/POST | `/api/v1/visits/` | 진료 내역 / 생성 | 로그인 |
| GET | `/api/v1/diagnoses/` | 진단 결과 목록 | 로그인 |

---

## 테스트 계정

| 역할 | 아이디 | 비밀번호 | 이름 |
|------|--------|----------|------|
| 관리자 | admin | admin123 | 시스템 관리자 |
| 의사 1 | doctor1 | doctor123 | 김의사 |
| 의사 2 | doctor2 | doctor123 | 이의사 |
| 간호사 | nurse1 | nurse123 | 박간호사 |

---

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DATABASE_URL` | DB 연결 문자열 | `mysql+pymysql://...` (로컬) / `postgresql+psycopg2://...` (Docker) |
| `SECRET_KEY` | JWT 서명 키 (32자 이상 필수) | - |
| `ENCRYPTION_KEY` | 개인정보 암호화 키 | - |
| `REDIS_URL` | Redis 연결 | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery 브로커 | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery 결과 저장소 | `redis://localhost:6379/1` |
| `BATCH_SIZE` | 동적 배칭 최대 크기 | `8` |
| `BATCH_TIMEOUT_MS` | 배칭 대기 시간 | `100` |
| `AI_MODEL_PATH` | 모델 파일 경로 | `mtl_best.pth` |
| `AI_DEVICE` | 추론 디바이스 | `cpu` / `cuda` |

---

## 프로젝트 규모

| 항목 | 수치 |
|------|------|
| API 엔드포인트 | 26개+ (7개 라우트 모듈) |
| Docker 서비스 | 6개 (Redis, PostgreSQL, FastAPI, Celery, Next.js, Nginx) |
| 분류 클래스 | 4종 (STDI, STNT, STIN, STMX) |
| 세그멘테이션 클래스 | 5종 (Background, Tumor, Stroma, Normal, Immune) |
| 배치 추론 | 최대 8장 동시, 100ms 배칭 윈도우 |
| 폴링 타임아웃 | 최대 3분 (120회 × 1.5초) |

---

## 라이선스

이 프로젝트는 학술/교육 목적으로 개발되었습니다.
