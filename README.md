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

원본 파일 저장소(Garage)도 compose에 포함되어 있습니다. 개발용 키는 `.env.example`에 있고 버킷 `doni`는 처음 띄울 때 자동으로 만들어집니다. 운영 비밀값은 별도로 주입합니다.

## 배포 환경별 실행

```bash
# dev
APP_ENV=dev docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.cloud.yml up -d

# prod (.env.prod의 빈 값은 배포 파이프라인/시크릿 매니저에서 주입)
APP_ENV=prod docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.cloud.yml up -d
```

## Alembic

`migrations/`는 init 완료, `target_metadata = app.models.Base.metadata`(async 엔진 패턴)로 설정돼 있다.
모델을 바꾼 뒤 새 리비전을 만들 때:

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.local.yml up -d db redis
DATABASE_URL=postgresql+asyncpg://doni:doni@localhost:5432/doni uv run alembic revision --autogenerate -m "설명"
DATABASE_URL=postgresql+asyncpg://doni:doni@localhost:5432/doni uv run alembic upgrade head
```

api/worker 컨테이너는 마이그레이션을 자동으로 돌리지 않는다. 배포 전에 `alembic upgrade head`를 먼저 실행해야 한다.

## 테스트

```bash
uv run pytest
```

`tests/api.http`는 VS Code REST Client 등으로 여는 수동 테스트용 요청 모음이다.

## 구조

```
app/
  core/            config, celery_app (api/worker가 같은 Redis를 보게 하는 접속점)
  db/              DB 세션, Base
  models/          전체 도메인의 SQLAlchemy 모델을 한곳에 모음 (Alembic 누락 방지 목적)
    asset.py         Asset(원본+결과 메타데이터) + AssetRow(실제 행)
    pipeline.py       Pipeline, PipelineNode, PipelineEdge, NodeRun (PipelineRun 없음)
  infrastructure/
    storage/garage.py   원본/프리사인 URL 경계 (Garage, S3 호환)
    ai/client.py        AI 서버 호출 경계 (이미지→텍스트, LLM 컬럼 생성)
  domains/
    auth/            로그인 (JWT)
    ingestion/        업로드 -> Garage 저장 -> uploads 기록 -> 분류 -> Asset 등록
    assets/           Asset/AssetRow 전담 쿼리 (다른 도메인은 이 service로만 접근)
    pipelines/
      errors.py          도메인 예외(404/409/422) - main.py에 핸들러 한 곳만 등록
      rules/            순수 규칙: graph_rules(순환/타입 검증), state_rules(NodeRun 상태 전이)
      nodes/            노드 카탈로그 (메뉴 "데이터 변환/결합/통합/AI 사용"과 매핑)
        transform/        데이터 변환: column_ops, extract_ops, cleanup_ops
        combine/          데이터 결합(join) / 데이터 통합(union)
        ai/               AI 사용: llm_column
      output/            데이터 출력: to_dataset, to_entity_type
      use_cases/
        create_step.py     POST /pipelines/nodes/transform|join|union 공통 로직
                            (노드+선+실행 기록(PENDING) 저장 -> 큐 등록, 실패해도 노드는 남음)
        execute_node.py    워커가 run_id를 받아 실행 (선점 -> load -> transform -> save -> 상태 갱신)
        retry_node.py      FAILED 노드에 새 실행 기록을 만들어 재시도
        delete_node.py     자식이 없고 진행 중이 아닌 노드만 삭제 (만든 Asset은 보존)
        graph.py           GET /pipelines/{id}/graph: 새로고침 후 캔버스 복원
        sweep_runs.py      멈춘 PENDING/RUNNING을 FAILED로 마감 (스케줄러 미연결, 수동 호출용)
      tasks.py           Celery 작업: run_id만 받아 워커가 execute_node를 수행.
                         작업마다 NullPool로 새 엔진을 써서 이벤트 루프 불일치를 피함
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
