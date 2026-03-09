# Portfolio: Gastric Cancer Diagnosis Hospital Management System

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Key Features & Technical Highlights](#3-key-features--technical-highlights)
4. [Recent Fixes Deep-Dive](#4-recent-fixes-deep-dive)
5. [Code Review: Changed Files](#5-code-review-changed-files)
6. [Interview Q&A](#6-interview-qa)
7. [Portfolio Presentation Strategy](#7-portfolio-presentation-strategy)

---

## 1. Project Overview

### Summary

A **full-stack hospital management system** with integrated AI that performs **gastric cancer classification and segmentation** from pathology images. The system automates the diagnostic workflow -- from patient registration through image upload, AI inference, and result visualization -- serving doctors, nurses, and administrators with role-based access control.

### Problem Statement

Pathologists manually review histopathology slides for gastric cancer, which is time-consuming and subject to inter-observer variability. This project provides a **real-time AI-assisted diagnostic pipeline** that delivers both a cancer-type classification and a pixel-level tissue segmentation map within seconds.

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, Axios | SPA with SSR/SSG, responsive UI |
| **Backend** | FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2 | REST API, ORM, schema validation |
| **AI Model** | PyTorch, segmentation-models-pytorch (UNet + ResNet50) | Multi-Task Learning (Classification + Segmentation) |
| **Task Queue** | Celery 5.4, Redis 7 | Async inference, dynamic batching |
| **Database** | PostgreSQL 16 (prod) / MySQL 8 / SQLite (dev) | Multi-DB support with auto-detection |
| **Infrastructure** | Docker Compose, Nginx, multi-stage Dockerfile | Containerized microservice deployment |
| **Auth** | JWT (HS256), OAuth2 password flow, bcrypt | Stateless authentication |

### Scale & Metrics

- **26+ API endpoints** across 7 route modules
- **5 Docker services** orchestrated with health checks and dependency ordering
- **4 cancer types** classified: STDI, STNT, STIN, STMX
- **5 tissue classes** segmented: Background, Tumor, Stroma, Normal, Immune
- Batch inference processes **up to 8 images** simultaneously with **100ms batching window**
- Polling-based UI supports **up to 3-minute** inference timeout

---

## 2. System Architecture

### High-Level Architecture

```
                    +-----------+
                    |  Browser  |
                    +-----+-----+
                          |
                    +-----v-----+
                    |   Nginx   |  :80
                    +-----+-----+
                     /         \
           /api/*   /           \  /*
    +------v------+        +------v------+
    |   FastAPI   | :8000  |  Next.js    | :3000
    +------+------+        +-------------+
           |
    +------v------+     +-------------+
    |    Redis    |<--->| Celery      |
    |  (Broker)   |     | Worker(s)   |
    +------+------+     +------+------+
           |                   |
    +------v------+     +------v------+
    | Redis :6379 |     | PyTorch     |
    | (Results)   |     | MTL Model   |
    +-------------+     | (GPU/CPU)   |
                        +-------------+
    +-------------+
    | PostgreSQL  | :5432
    | (gastric_   |
    |  hospital)  |
    +-------------+
```

### Request Flow: AI Diagnosis

```
1. Doctor uploads image (POST /clinical/diagnose)
2. FastAPI validates auth + encodes image to base64
3. Celery task submitted to "ai_inference" queue
4. Worker picks up task, loads into DynamicBatcher
5. Batcher accumulates requests (max 8 or 100ms timeout)
6. Batch inference on GPU: classification + segmentation
7. Results stored in Redis, DB records created
8. Frontend polls GET /clinical/diagnose/{task_id}
9. COMPLETED -> renders prediction + segmentation overlay
```

### Data Model (ERD Summary)

```
Users (id, username, full_name, role, hashed_password)
  |-- 1:N --> Visits (as doctor)
  
Patients (id, name, patient_number, encrypted fields)
  |-- 1:N --> Visits (cascade delete)
  
Visits (id, patient_id, doctor_id, status, chief_complaint, ...)
  |-- 1:N --> Diagnoses (cascade delete)
  
Diagnoses (id, visit_id, cancer_type, confidence, probabilities, segmentation_data, ...)
```

---

## 3. Key Features & Technical Highlights

### 3.1 Multi-Task Learning AI Model

- **Architecture**: UNet encoder (ResNet50) shared backbone with dual heads
  - **Segmentation Head**: Decoder producing 5-class pixel masks
  - **Classification Head**: AdaptiveAvgPool2d -> FC(2048->512->4) with BatchNorm, ReLU, Dropout
- **Graceful Fallback**: If model file is missing, system enters "mock mode" returning demo predictions -- ensuring the application runs in any environment

### 3.2 Dynamic Batching Engine

```python
class DynamicBatcher:
    """Collects requests in a queue, fires batch inference when:
       - queue reaches BATCH_SIZE (default 8), OR
       - BATCH_TIMEOUT_MS (default 100ms) elapses since first request"""
```

- Singleton per worker process
- Daemon thread consuming from `queue.Queue`
- Each request wraps a `concurrent.futures.Future` for result delivery
- Automatic fallback to single inference on batch failure

### 3.3 Async Task Architecture (Celery)

- **Two dedicated queues**: `ai_inference` (GPU-bound) and `db_operations` (I/O-bound)
- **Task routing**: `predict_single` -> ai_inference, `save_diagnosis_result` -> db_operations
- **Rate limiting**: 100 predictions/minute per worker
- **Worker initialization**: Model loaded once via `worker_process_init` signal
- **Result backend**: Redis with 1-hour TTL

### 3.4 Frontend Polling Pattern

The `pollTaskResult<T>` generic utility provides:
- Configurable interval (default 1.5s) and max attempts (default 120)
- `onProgress` callback for real-time UI status updates
- Type-safe `TaskResult<T>` interface
- Graceful error propagation on FAILED or timeout

### 3.5 TrailingSlashMiddleware (Custom)

Solves the **307 redirect + token loss** problem in proxy environments. Rewrites paths server-side instead of issuing HTTP 307 redirects that lose POST bodies and Authorization headers.

### 3.6 Multi-Database Support

`database.py` auto-detects SQLite, MySQL, or PostgreSQL from `DATABASE_URL` and configures appropriate engine parameters (pool size, recycle intervals, SQLite PRAGMA).

### 3.7 Docker Production Deployment

- **Multi-stage Dockerfiles** for minimal image sizes
- **Health checks** on every service (curl, redis-cli, pg_isready, wget)
- **GPU passthrough** for Celery worker via NVIDIA runtime
- **Nginx reverse proxy** routing `/api/*` and `/*` to respective services

---

## 4. Recent Fixes Deep-Dive

### Fix 1: TrailingSlashMiddleware (`backend/app/main.py`)

**Problem**: FastAPI's default `redirect_slashes=True` sends 307 Temporary Redirect when a client calls `/api/v1/visits` (no trailing slash). In a reverse-proxy setup (Next.js -> Nginx -> FastAPI), this redirect:
1. Changes the HTTP method (POST -> GET in some clients)
2. Drops the `Authorization: Bearer` header
3. Loses the request body

**Solution**:
```python
app = FastAPI(redirect_slashes=False)

class TrailingSlashMiddleware(BaseHTTPMiddleware):
    SKIP_SEGMENTS = {"login", "me", "refresh", "diagnose", ...}
    
    async def dispatch(self, request, call_next):
        path = request.scope["path"]
        if path.startswith("/api/") and not path.endswith("/"):
            last_segment = path.rstrip("/").split("/")[-1]
            if (not last_segment.isdigit()
                and "-" not in last_segment  # UUID/Celery task IDs
                and last_segment not in self.SKIP_SEGMENTS
                and "." not in last_segment):
                request.scope["path"] = path + "/"
        return await call_next(request)
```

**Key Design Decisions**:
- `redirect_slashes=False` globally disables FastAPI's auto-redirect
- Middleware rewrites the ASGI scope path **before** routing -- zero HTTP round-trips
- Skip heuristics: numeric IDs (`/visits/123`), UUIDs with hyphens (`/tasks/abc-def`), action endpoints (`/auth/login`), file extensions (`openapi.json`)

### Fix 2: Axios Interceptor (`frontend/src/lib/api.ts`)

**Problem**: When a JWT expires mid-session, subsequent API calls return 401. Without proper handling, the user sees cryptic errors and stale state.

**Solution**:
```typescript
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      if (!url.includes('/auth/login')) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
      }
    }
    return Promise.reject(error);
  }
);
```

**Key Design Decisions**:
- **Login exclusion**: A 401 on `/auth/login` means wrong credentials, not an expired token -- so we don't clear storage
- **SSR guard**: `typeof window !== 'undefined'` prevents crashes during Next.js server-side rendering
- **Separation of concerns**: The interceptor only clears tokens; the actual redirect to `/login` is handled by `(auth)/layout.tsx`

### Fix 3: Auth Layout Improvements (`frontend/src/app/(auth)/layout.tsx`)

**Problem**: Every page navigation triggered a redundant `GET /auth/me` call. Race conditions between login redirect and localStorage write caused flickering.

**Solution**:
```typescript
const hasChecked = useRef(false);

useEffect(() => {
  if (hasChecked.current && isAuthenticated) {
    setIsChecking(false);
    return;  // Skip re-verification on page navigations
  }
  const checkAuth = async () => {
    // ... verify token with backend
    hasChecked.current = true;
  };
  const timer = setTimeout(checkAuth, 50);  // Wait for localStorage write
  return () => clearTimeout(timer);
}, []);
```

**Key Design Decisions**:
- `useRef(hasChecked)` persists across re-renders without triggering them
- Empty dependency array `[]` runs only on initial mount
- 50ms `setTimeout` guarantees localStorage is written after login redirect
- `StorageEvent` listener handles cross-tab logout synchronization
- Loading spinner prevents flash of unauthenticated content

---

## 5. Code Review: Changed Files

### 5.1 `backend/app/main.py`

| Aspect | Assessment | Details |
|--------|-----------|---------|
| **Correctness** | Good | `redirect_slashes=False` correctly prevents 307 redirects. Middleware scope rewrite is the standard ASGI approach. |
| **Edge Cases** | Good | Handles numeric IDs, UUIDs (hyphen check), file extensions, and a comprehensive SKIP_SEGMENTS set. |
| **Middleware Order** | Correct | CORS is added first (outermost), TrailingSlashMiddleware second (innermost). ASGI middleware wraps in reverse registration order, so CORS processes first. |
| **Performance** | Excellent | String operations only (split, endswith, isdigit) -- negligible overhead per request. |
| **Improvement Suggestion** | Minor | Consider using a regex pattern instead of multiple conditions for cleaner skip logic. The hyphen check (`"-" not in last_segment`) could inadvertently skip legitimate slug-based routes like `/api/v1/cancer-types`. |
| **Security** | Good | No user input is reflected back; path rewrite is internal only. |

**Middleware Registration Nuance:**
```python
# Starlette wraps middleware in REVERSE order of add_middleware() calls:
# Request flow: Client -> CORS -> TrailingSlash -> Router
# This is correct: CORS headers are set before path rewriting
app.add_middleware(CORSMiddleware, ...)     # Registered first -> outermost
app.add_middleware(TrailingSlashMiddleware)  # Registered second -> innermost
```

### 5.2 `frontend/src/lib/api.ts`

| Aspect | Assessment | Details |
|--------|-----------|---------|
| **Architecture** | Well-structured | Clean separation: Axios instance -> interceptors -> polling utility -> API methods. |
| **Type Safety** | Good | Generic `TaskResult<T>` and `pollTaskResult<T>` allow typed results. |
| **Error Handling** | Good | 401 interceptor excludes login endpoint. Polling throws on FAILED/timeout with Korean error messages. |
| **SSR Compatibility** | Correct | `typeof window !== 'undefined'` guards all localStorage access for Next.js SSR. |
| **Polling Design** | Functional | Linear polling (fixed 1.5s interval). Consider exponential backoff for high-load scenarios. |
| **Improvement Suggestions** | Medium | (1) `maxRedirects: 0` on `getVisits` is a workaround -- document why. (2) `any` types on `createPatient(data: any)` lose type safety; define DTOs. (3) Consider `AbortController` integration for cancellable polling. (4) The `pollTaskResult` could use exponential backoff (e.g., 1s -> 2s -> 4s, capped at 5s). |
| **Memory Leak Risk** | Low | `setTimeout` in polling loop is not cancellable from outside. If the component unmounts during polling, the loop continues. Recommend passing an AbortSignal. |

**Polling Improvement Example:**
```typescript
// Current: fixed interval
await new Promise(resolve => setTimeout(resolve, intervalMs));

// Suggested: exponential backoff
const delay = Math.min(intervalMs * Math.pow(1.5, attempt), 5000);
await new Promise(resolve => setTimeout(resolve, delay));
```

### 5.3 `frontend/src/app/(auth)/layout.tsx`

| Aspect | Assessment | Details |
|--------|-----------|---------|
| **Auth Guard Pattern** | Good | Next.js route group `(auth)` wraps all protected pages with a single layout. |
| **Re-render Prevention** | Excellent | `useRef(hasChecked)` avoids redundant `/auth/me` calls on internal navigation. |
| **Race Condition Handling** | Good | 50ms `setTimeout` addresses the login-redirect-before-localStorage-write race. |
| **Cross-Tab Sync** | Excellent | `StorageEvent` listener logs out all tabs when one tab removes the token. |
| **Loading UX** | Good | Full-screen spinner prevents FOUC (Flash of Unauthenticated Content). |
| **Improvement Suggestions** | Minor | (1) The 50ms timeout is a magic number -- add a comment or constant. (2) `eslint-disable-next-hooks/exhaustive-deps` suppression: safe here but fragile for future edits. (3) Consider adding a retry mechanism for transient network failures on the `/auth/me` call instead of immediately logging out. |
| **Security** | Good | Token is verified server-side (not just checking localStorage existence). Logout clears all sensitive data. |

**Token Verification Flow:**
```
Mount -> setTimeout(50ms) -> checkAuth()
  |-> No token? -> router.replace('/login')
  |-> Has token? -> GET /auth/me
      |-> Success -> setIsAuthenticated(true), cache in ref
      |-> 401 -> interceptor clears localStorage -> logout() -> /login
```

---

## 6. Interview Q&A

### Category 1: FastAPI Routing & Redirects

**Q1. Why did you set `redirect_slashes=False` and implement a custom middleware instead of just defining routes with trailing slashes?**

> **A**: FastAPI's default `redirect_slashes=True` sends a 307 Temporary Redirect from `/visits` to `/visits/`. In a proxy chain (Next.js rewrite -> Nginx -> FastAPI), this 307 causes three problems: (1) some HTTP clients switch POST to GET on redirect, (2) the `Authorization` header is stripped on cross-origin redirects, and (3) the request body is lost. By setting `redirect_slashes=False` and adding a `TrailingSlashMiddleware` that rewrites the ASGI scope path before routing, we handle this internally with zero additional HTTP round-trips. The middleware uses heuristics (numeric IDs, hyphens for UUIDs, SKIP_SEGMENTS set) to only add slashes to collection endpoints.

**Q2. Explain the middleware registration order in your FastAPI application.**

> **A**: Starlette processes middleware in the reverse order of `add_middleware()` calls. I register CORSMiddleware first and TrailingSlashMiddleware second, so the request flow is: Client -> CORS -> TrailingSlash -> Router. This ensures CORS preflight (OPTIONS) requests are handled before path rewriting, and that the CORS headers are correctly applied to the rewritten path's response.

**Q3. What is the difference between ASGI scope path rewriting and an HTTP redirect? When would you choose one over the other?**

> **A**: Scope rewriting modifies `request.scope["path"]` in-process before the router matches it -- no additional network round-trip, no header/body loss. An HTTP redirect (301/307/308) sends a response telling the client to make a new request to a different URL. I choose scope rewriting when the client shouldn't know about the rewrite (internal normalization), and HTTP redirects when the client needs to update its URL (e.g., domain migration, permanent URL change for SEO).

---

### Category 2: Next.js Proxy Rewrites

**Q4. How does the Next.js rewrite proxy work in development vs. production?**

> **A**: In development, `next.config.js` defines `rewrites()` that proxy `/api/:path*` to `http://localhost:8000/api/:path*`. The Next.js dev server intercepts matching requests and forwards them to FastAPI, avoiding CORS issues since both appear on `localhost:3000`. In production, Next.js runs as a standalone Node.js server and the rewrite still applies, but we place Nginx in front to handle the routing more efficiently: `/api/*` goes to FastAPI:8000, everything else to Next.js:3000. The Next.js rewrite acts as a fallback.

**Q5. What problems can arise from Next.js proxy rewrites and how did you handle them?**

> **A**: Key issues: (1) **Trailing slash mismatch**: Next.js rewrites preserve the exact path, but FastAPI may expect trailing slashes -- solved by the TrailingSlashMiddleware. (2) **Redirect loops**: If FastAPI returns a 307, the proxy follows it and the client may see an unexpected response -- solved by `maxRedirects: 0` on specific Axios calls and `redirect_slashes=False` on FastAPI. (3) **Headers not forwarded**: Some proxies strip Authorization headers -- solved by Nginx's `proxy_set_header` and Next.js passing headers through by default.

---

### Category 3: Authentication Handling

**Q6. Explain your JWT authentication flow end-to-end.**

> **A**: (1) Client sends `username` + `password` as `application/x-www-form-urlencoded` to `POST /auth/login` (OAuth2 password flow). (2) Backend verifies credentials with bcrypt, creates a JWT with `sub` (username), `exp` (30min), signed with HS256. (3) Frontend stores the token in `localStorage` and sets it via Axios request interceptor on every subsequent call. (4) Backend `get_current_active_user` dependency decodes the JWT, fetches the user from DB, and checks `is_active`. (5) On 401, the Axios response interceptor clears localStorage (except for login requests). (6) The `(auth)/layout.tsx` route guard detects missing tokens and redirects to `/login`.

**Q7. Why did you use `localStorage` instead of HTTP-only cookies for JWT storage?**

> **A**: `localStorage` was chosen for simplicity in this hospital intranet context. The tradeoffs: localStorage is vulnerable to XSS (JavaScript can read the token), but is simpler for SPA authorization headers. HTTP-only cookies are immune to XSS but require CSRF protection and complicate CORS. For a production healthcare system, I would recommend HTTP-only cookies with `SameSite=Strict`, CSRF tokens, and `Secure` flag, combined with a refresh token rotation pattern.

**Q8. How does your auth layout prevent the "flash of unauthenticated content"?**

> **A**: The `(auth)/layout.tsx` starts with `isChecking=true`, rendering a loading spinner. It calls `GET /auth/me` to verify the token server-side. Only after successful verification does it set `isChecking=false` and render children. This prevents any protected content from being visible before authentication is confirmed. The `useRef(hasChecked)` optimization skips re-verification on internal page navigations.

**Q9. How do you handle token expiration during an active session?**

> **A**: The Axios response interceptor catches 401 errors globally. When a 401 occurs on any non-login request, it clears the token from localStorage. The `(auth)/layout.tsx` doesn't re-check on every navigation (thanks to `hasChecked` ref), but the next API call that fails with 401 will trigger the interceptor. For a better UX, I could implement (1) proactive token refresh before expiry using a refresh token, or (2) silent refresh by intercepting 401, requesting a new token, and retrying the original request.

---

### Category 4: Celery Integration

**Q10. Why did you choose Celery + Redis over other async processing approaches?**

> **A**: AI inference takes 1-10 seconds per image, which blocks the FastAPI event loop. Options considered: (1) `BackgroundTasks` -- too limited, no result tracking, dies with the process. (2) `asyncio` threads -- no GPU scheduling, no retry, no monitoring. (3) Celery -- production-grade: persistent result backend, automatic retries (2x with 5s delay), rate limiting (100/min), queue routing (GPU vs DB operations), and worker health monitoring. Redis was chosen as broker for its speed and dual use as result backend.

**Q11. Explain your dynamic batching strategy.**

> **A**: The `DynamicBatcher` runs a daemon thread that collects `InferenceRequest` objects from a thread-safe queue. It fires a batch when either (a) 8 requests accumulate, or (b) 100ms passes since the first queued request. This balances throughput (batching maximizes GPU utilization) with latency (single requests don't wait more than 100ms). Each request carries a `concurrent.futures.Future`, and after `model_service.predict_batch()` completes, results are dispatched to their respective futures. On batch failure, individual predictions are attempted as fallback.

**Q12. How do you ensure the AI model is loaded only once per worker?**

> **A**: Celery's `worker_process_init` signal fires once when a worker process starts. I attach a handler that creates the `MTLAIService` singleton and `DynamicBatcher` singleton. These persist in the worker's global state across all task executions. Using `--pool=solo` (single-threaded) ensures no concurrent model access issues. For multi-process pools, each process gets its own model copy.

**Q13. How does your task routing work?**

> **A**: I define two queues: `ai_inference` for GPU-bound tasks and `db_operations` for I/O-bound tasks. In `celery_app.py`, `task_routes` maps `predict_single` to `ai_inference` and `save_diagnosis_result` to `db_operations`. The worker is started with `-Q ai_inference,db_operations,default` to consume from all queues. In production, you could run separate workers: GPU workers consuming only `ai_inference`, and CPU workers consuming `db_operations`.

---

### Category 5: Docker Compose Setup

**Q14. Walk me through your Docker Compose architecture.**

> **A**: Six services with explicit health checks and dependency ordering:
> 1. **Redis** (redis:7-alpine): Celery broker + result backend, health: `redis-cli ping`
> 2. **PostgreSQL** (postgres:16-alpine): Primary database, health: `pg_isready`
> 3. **FastAPI**: Built from multi-stage Dockerfile (target: fastapi), waits for healthy Redis + PostgreSQL
> 4. **Celery Worker**: Same Dockerfile (target: celery-worker), mounts model files read-only, reserves NVIDIA GPU
> 5. **Next.js Frontend**: Standalone build, waits for healthy FastAPI
> 6. **Nginx**: Reverse proxy, routes `/api/*` to FastAPI, `/*` to frontend
>
> `depends_on` with `condition: service_healthy` ensures correct startup order.

**Q15. Why did you use multi-stage Dockerfiles?**

> **A**: The backend Dockerfile has a `base` stage (install dependencies), then `fastapi` and `celery-worker` targets that share the base. This avoids duplicating the `pip install` layer (which includes PyTorch at ~2GB). The frontend uses `deps` (npm install), `builder` (npm run build), and `runner` (copy standalone output) stages, reducing the final image from ~1GB to ~100MB by excluding source code and dev dependencies.

**Q16. How do you handle GPU access in Docker Compose?**

> **A**: The `celery-worker` service has a `deploy.resources.reservations.devices` block specifying `driver: nvidia`, `count: all`, `capabilities: [gpu]`. This requires the NVIDIA Container Toolkit installed on the host. The `AI_DEVICE` environment variable switches between `cuda` (production) and `cpu` (development/CI). The `docker-compose.dev.yml` omits the GPU reservation for local development.

---

### Category 6: MySQL/PostgreSQL Migration

**Q17. How does your application support multiple database backends?**

> **A**: `database.py` auto-detects the DB type from `DATABASE_URL` string prefix: `sqlite://`, `mysql://`, or `postgresql://`. Each type gets tailored `engine_kwargs`: SQLite gets `check_same_thread=False` and PRAGMA FK support; MySQL gets `pool_recycle=3600` (to handle MySQL's 8-hour connection timeout); PostgreSQL gets `pool_recycle=1800`. The pool size (10) and max overflow (20) are consistent across MySQL/PostgreSQL. Alembic handles schema migrations, and the `init_db.py` script creates all tables via `Base.metadata.create_all()`.

**Q18. What challenges did you face migrating from MySQL to PostgreSQL?**

> **A**: (1) **Driver change**: `pymysql` to `psycopg2-binary` -- handled by `DATABASE_URL` switching. (2) **Auto-increment syntax**: SQLAlchemy abstracts this, but raw SQL in init scripts needed updating. (3) **Boolean handling**: MySQL uses TINYINT(1), PostgreSQL has native BOOLEAN -- SQLAlchemy maps both correctly. (4) **Connection pooling**: MySQL needs longer `pool_recycle` (3600s) due to `wait_timeout`, PostgreSQL is more stable (1800s). (5) **Docker networking**: Changed `DATABASE_URL` from `localhost` to `postgres` (Docker service name).

---

### Category 7: CI/CD Processes

**Q19. Describe your Git workflow and deployment process.**

> **A**: Feature branch workflow: `feature/sub_1` -> PR to `main`. Before PR creation: (1) `git fetch origin main` to get latest changes, (2) `git rebase origin/main` to integrate, (3) resolve conflicts prioritizing remote code, (4) squash commits with `git reset --soft HEAD~N && git commit`, (5) force push, (6) create/update PR with comprehensive description. Deployment: `docker compose up -d --build` pulls the latest code, rebuilds images, and rolling-restarts services with health checks ensuring zero-downtime.

**Q20. How would you implement a CI/CD pipeline for this project?**

> **A**: GitHub Actions with three stages:
> 1. **Test**: Run `pytest` for backend, `npm run lint && npm run build` for frontend, on every PR
> 2. **Build**: Multi-stage Docker builds, push to container registry (ghcr.io or ECR)
> 3. **Deploy**: `docker compose pull && docker compose up -d` on the target server via SSH
>
> Additional: (1) Database migration step with Alembic before deploy. (2) Health check verification after deploy. (3) Rollback script if health checks fail. (4) Separate staging and production environments.

---

### Bonus: Architecture & Design Questions

**Q21. If inference latency increases under load, what would you do?**

> **A**: Progressive optimization: (1) Increase `BATCH_SIZE` to maximize GPU throughput. (2) Add more Celery workers with `--concurrency` or horizontal scaling. (3) Implement model quantization (FP16/INT8) for faster inference. (4) Add a result cache (Redis) for identical images. (5) Use ONNX Runtime or TensorRT for optimized serving. (6) Implement request prioritization in the queue.

**Q22. How would you make this system HIPAA-compliant?**

> **A**: (1) Encrypt data at rest (PostgreSQL TDE or volume encryption). (2) Encrypt data in transit (TLS everywhere, including internal Docker networking). (3) Replace localStorage JWT with HTTP-only secure cookies. (4) Add audit logging for all data access. (5) Implement field-level encryption for PII (the `ENCRYPTION_KEY` config is already there). (6) Add session timeout and concurrent session limits. (7) Deploy in a HIPAA-eligible cloud environment (AWS GovCloud, Azure HIPAA BAA).

**Q23. Why did you separate `db_operations` and `ai_inference` queues?**

> **A**: Resource isolation. GPU inference is compute-bound and benefits from batch processing. Database operations are I/O-bound and complete quickly. If both shared a queue, slow GPU tasks would block fast DB writes. With separate queues, you can scale them independently: 1 GPU worker for inference, multiple CPU workers for DB operations. This also enables different retry strategies: GPU tasks retry twice (transient CUDA errors), DB tasks could retry more aggressively.

---

## 7. Portfolio Presentation Strategy

### Document Structure Recommendation

```
1. Cover Page
   - Project title + one-line description
   - Your name, role, period
   - Tech stack icons/logos

2. Problem & Solution (1 page)
   - Business context: "Hospital pathology workflow"
   - Pain point: "Manual slide review takes X minutes, Y% variability"
   - Solution: "AI-assisted pipeline reducing to Z seconds"

3. Architecture Diagram (1 page)
   - High-level system diagram (as above)
   - Call out the async inference flow with numbered steps

4. Technical Deep-Dive (2-3 pages)
   - Pick 3 highlights: Dynamic Batching, TrailingSlash fix, Auth Flow
   - Each with: Problem -> Solution -> Code snippet -> Result

5. Before/After Comparison
   - Show the 307 redirect bug with a network trace
   - Show the fix with the middleware trace
   - Show polling UI screenshots (PENDING -> PROCESSING -> COMPLETED)

6. Metrics & Impact
   - Inference throughput: X images/minute
   - Batch vs. single: Y% improvement
   - Docker deployment time: Z minutes

7. Lessons Learned
   - "HTTP redirects behave differently across proxies"
   - "Middleware order matters in ASGI frameworks"
   - "Token handling needs cross-tab synchronization"
```

### Key Presentation Tips

1. **Lead with the problem, not the solution**: "We had a 307 redirect that silently dropped auth tokens in production" is more compelling than "I wrote a trailing slash middleware."

2. **Show code, but annotate it**: Don't paste raw files. Highlight the 3-5 critical lines with arrows/callouts explaining the "why."

3. **Quantify everything**: "Dynamic batching improved throughput by 4x on 8-image batches" is better than "I implemented batching."

4. **Demonstrate debugging process**: Showing how you identified the 307 issue (network tab, server logs) proves real-world skills more than just the fix.

5. **Connect infrastructure to business value**: "Docker Compose with health checks enables one-command deployment, reducing deployment time from 30 minutes to 2 minutes."

6. **Prepare a live demo**: Have Docker Compose running with mock mode. Show: Login -> Patient select -> Image upload -> Polling animation -> Result with segmentation overlay.

7. **Anticipate follow-ups**: For every architectural decision, prepare "why not X?" answers (e.g., "Why Celery instead of FastAPI BackgroundTasks?").

### Korean Presentation Notes (Korean Interview Context)

- AI + Healthcare 도메인은 높은 평가를 받음
- "실제 병원 환경 요구사항 반영"을 강조하면 도메인 이해도를 어필 가능
- 307 리다이렉트 이슈는 "프록시 환경에서의 문제 해결 경험"으로 프레이밍
- Docker Compose 전체 구성을 보여주면 DevOps 역량 어필 가능
- Celery 동적 배칭은 "GPU 자원 최적화 경험"으로 프레이밍

---

*Document generated: 2026-03-09*
*Project: Gastric Cancer Diagnosis Hospital Management System v3.0.0*
*Repository: https://github.com/ico2604/Gastric-Hospital-Web*
