# 🏥 위암 분류 병원 관리 시스템 (Phase 1)
> **ResNet50 기반 AI 위암 분류 모델을 통합한 의료 전문가용 통합 관리 솔루션**

![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=flat-square&logo=flask&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-2.1-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=flat-square&logo=mysql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 📋 프로젝트 개요
본 프로젝트는 학교 프로젝트 및 포트폴리오를 목적으로 제작된 **병원 관리 시스템**입니다. ResNet50 모델을 활용하여 위암 현미경 이미지를 분류하며, 실제 의료 환경을 고려한 보안 프로토콜과 직관적인 UI를 제공합니다.

### ✨ 핵심 목표
* **AI 진단 통합**: 4가지 클래스의 위암 분류 모델 실시간 추론
* **의료 특화 UX/UI**: 깨끗한 화이트 톤의 Bootstrap 5 기반 디자인
* **강력한 데이터 보안**: 개인정보 암호화 및 역할 기반 접근 제어 (RBAC)

---

## 🛠 기술 스택

### Backend & AI
* **Framework:** Flask 3.1 (Python 3.10)
* **Database:** MySQL (Local/Dev)
* **AI Model:** PyTorch 2.1 (ResNet50 기반)
* **Preprocessing:** Albumentations, OpenCV
* **Security:** Flask-Login, AES-256 (Cryptography), Werkzeug (Hashing)

### Frontend
* **UI Kit:** HTML5, Bootstrap 5, Bootstrap Icons
* **Script:** JavaScript (Vanilla JS, Fetch API)

---

## ✅ Phase 1 완성 기능

### 1. AI 위암 분류 서비스 ⭐
* **이미지 업로드**: 드래그 앤 드롭 지원 및 실시간 미리보기
* **4-Class 분류**:
  | 코드 | 국문명 | 영문명 |
  | :--- | :--- | :--- |
  | **STDI** | 미만형선암 | Signet Ring Cell Carcinoma |
  | **STNT** | 위염 | Gastritis (Non-Tumor) |
  | **STIN** | 장형선암 | Tubular Adenocarcinoma |
  | **STMX** | 혼합형선암 | Mixed Type Carcinoma |
* **결과 시각화**: 클래스별 확률 분포 및 신뢰도 프로그레스 바 제공

### 2. 진료 및 대시보드
* **의사 대시보드**: 금일 진료 및 대기 건수 통계 카드, 최근 진료 목록 (10건)
* **진료 관리**: 이름/주민번호 검색 및 상태별(진료 대기/완료) 필터링
* **진료 상세**: 환자 히스토리 조회 및 현미경 사진 확대 기능

### 3. 보안 및 로깅
* **개인정보 보호**: 환자명, 주민번호, 연락처 AES-256 암호화 저장
* **데이터 마스킹**: 화면 출력 시 주요 정보 자동 마스킹 처리
* **예측 로그**: AI 추론 결과(Raw Logits, Softmax)를 일자별 로그 파일로 기록

---

## 📁 프로젝트 구조
```text
hospital-system/
├── app.py                  # Flask 메인 서버 (라우팅 및 로직)
├── config.py               # DB 및 보안키 설정
├── models.py               # SQLAlchemy 데이터 모델
├── schema.sql              # MySQL 테이블 스키마
├── utils/
│   ├── crypto.py           # AES-256 암호화/복호화 유틸
│   └── ai_predictor.py     # PyTorch 모델 로드 및 추론
├── templates/              # HTML 템플릿 레이아웃
├── static/                 # CSS, JS, 업로드 이미지 경로
└── resnet50_best.pth       # AI 모델 가중치 (94MB)
