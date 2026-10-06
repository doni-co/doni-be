# doni-be

팔란티어 파운드리 경량화 버전의 백엔드. 빠른 초기 버전 개발을 목표로
도메인 단위 분리 + 얇은 서비스 계층(DDD-lite)으로 구성했다. 엄격한 엔티티/리포지토리 계층은
의도적으로 생략했다.

## 시작

```bash
cp .env.example .env.local   # 이미 생성되어 있음. 값만 확인
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.local.yml up --build
curl localhost:8000/health
```

## 배포 환경별 실행

```bash
# dev
APP_ENV=dev docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.cloud.yml up -d

# prod (.env.prod의 빈 값은 배포 파이프라인/시크릿 매니저에서 주입)
APP_ENV=prod docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.cloud.yml up -d
```

## Alembic

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.local.yml run --rm api \
  alembic init -t async migrations
# migrations/env.py 에서 target_metadata = app.models.Base.metadata 로 설정
# app/models/__init__.py 를 import 하면 전체 테이블이 함께 인식됨 (Alembic 누락 방지)
```

## 테스트

```bash
uv run pytest
```

`tests/api.http`는 VS Code REST Client 등으로 여는 수동 테스트용 요청 모음이다.

## 구조

```
app/
  core/          설정, 스토리지 경계, AI 서버 호출 경계, Celery 설정 (전부 공통 인프라)
  db/            DB 세션, Base
  models/        전체 도메인의 SQLAlchemy 모델을 한곳에 모음 (Alembic 누락 방지 목적)
  domains/
    auth/        로그인 (JWT)
    ingestion/   업로드 + 확장자 기반 dataset/media_set 분류 (조율 레이어)
    media/       MediaSet (비정형 원천)
    datasets/    Dataset (정형) — 온톨로지 모듈과의 접점이 될 예정
    pipelines/
      transforms/      노드 카탈로그 (파이프라인 빌더 메뉴와 매핑)
        column_ops.py    데이터 변환 > 컬럼명/ 데이터 타입 통일, 컬럼 선택, 컬럼 제거, 컬럼명 표준화
        extract_ops.py   데이터 변환 > PDF에서 텍스트/ 이미지에서 텍스트/ 엑셀에서 JSON 추출, 배열 펼치기, 구조체 필드 추출
        cleanup_ops.py   데이터 변환 > 데이터 표준화, 문자 정리, 필터
        combine/         데이터 결합(join) / 데이터 통합(union)
        llm_column.py    AI 사용
      output/      데이터 출력 (새 Dataset / 새 Entity 타입) — Transform과 다른 유스케이스라 분리
      service.py   그래프 검증 + 상태 전이 + Run 오케스트레이션 (순수 로직을 별도 레이어로 안 뗌)
      tasks.py     Celery 워커 작업 (API 프로세스와 분리 실행)
tests/
migrations/        Alembic
deploy/            Dockerfile, docker-compose(base/local/cloud)
```

## 분리 대비 규칙 (나중에 서버 분리 시 핵심)

1. 한 도메인의 서비스 코드는 다른 도메인의 테이블을 직접 쿼리하지 않는다.
   항상 `media.service.*`, `datasets.service.*` 같은 함수 호출로만 접근한다.
2. 파일은 `app.core.storage`를 통해서만 읽고 쓴다. 경로를 직접 열지 않는다.
3. AI 서버 호출은 `app.core.ai_client`를 통해서만 한다.
4. Celery 작업은 `run_id`처럼 작은 값만 받고, 나머지는 워커가 DB에서 직접 조회한다.

이 네 가지만 지켜지면, 나중에 `pipelines`(+ `transforms`, `tasks.py`)를 별도 서버로 떼어낼 때도
새로 설계할 필요 없이 함수 호출을 HTTP 호출로 바꾸는 정도로 작업이 끝난다.
