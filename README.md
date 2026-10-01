# rag-git-docs

GitLab·GitHub 리포의 마크다운 문서를 Qdrant 에 넣고, Claude Code 에서 검색한다.

## 구조

실행 파일 셋이 번호 순서로 돈다. 1·2 는 매일 한 번, 3 은 계속 떠 있다.
`collector/` 와 `indexer/` 는 서로 import 하지 않는다. 둘을 잇는 것은 실행 파일뿐이다.

```
rag-git-docs/
├── collect.py            1. GitLab·GitHub 리포의 md 파일을 DOCS_DIR 로 내려받는다  → collector/
├── index.py              2. DOCS_DIR 의 md 를 Qdrant 에 색인한다                 → indexer/
├── serve.py              3. Claude Code 의 질문을 받아 Qdrant 에서 관련 조각을 찾아 준다 (MCP 서버)
│
├── collector/            1 단계. git 호스팅에서 md 를 내려받아 DOCS_DIR 에 둔다
│   ├── sources/          GitLab·GitHub API 호출. 호스팅마다 파일 하나
│   │   ├── gitlab.py     그룹의 리포 목록, 리포 안 md 목록, md 내용을 받는다
│   │   ├── github.py     계정의 리포에 대해 같은 일을 한다
│   │   ├── _http.py      HTTP GET 과 페이지 넘기기. 두 API 가 같은 방식이라 같이 쓴다
│   │   └── types.py      리포 정보(Repo)와, 파일 목록에서 md 만 골라내는 함수
│   ├── manifest.py       지난번에 받은 목록과 비교해 새로 받을 것, 지울 것을 정한다
│   └── files.py          md 를 DOCS_DIR 에 쓰고 지운다. 받은 목록을 .manifest.json 에 남긴다
│
├── indexer/              2 단계. md 를 잘라 벡터로 바꿔 Qdrant 에 넣는다
│   ├── chunk.py          md 를 헤딩마다 잘라 조각으로 만든다
│   ├── embed.py          조각을 임베딩 모델 bge-m3 로 벡터로 바꾼다
│   └── store.py          벡터를 Qdrant 에 넣는다. 색인하는 동안에도 검색이 끊기지 않게 한다
│
├── deploy/
│   ├── qdrant-helm/      Qdrant 공식 Helm 차트에 넘길 설정값
│   └── rag-helm/         1·2·3 을 k3s 에 띄우는 Helm 차트. 1·2 는 CronJob, 3 은 Deployment
├── infra/                서버 테라폼 (예정)
├── tests/                지울 파일 판정과 md 자르기 테스트
└── docs/design.md        왜 이렇게 만들었는지에 대한 기록. 코드를 고치기 전에 읽는다
```

`serve.py` 는 `indexer/` 의 `embed.py` 와 `store.py` 를 가져다 쓴다. 질문을 문서와 비교하려면
색인 때와 같은 모델로 질문도 벡터로 바꿔야 하고, 색인과 같은 Qdrant 컬렉션을 읽어야 하기 때문이다.

## 배포

```bash
# 이미지
docker build -t docker.wai/yunan/rag-git-docs:0.1.0 . && docker push docker.wai/yunan/rag-git-docs:0.1.0

# Qdrant 먼저. 이 차트가 만드는 서비스와 Qdrant API 키 Secret 을 rag-git-docs 가 이름으로 찾으므로 같은 네임스페이스에 둔다
helm install rag-qdrant qdrant/qdrant -n rag --create-namespace -f deploy/qdrant-helm/values.yaml

# 앱. 예시 파일을 복사해 비밀값을 채우고 설치할 때 함께 넘긴다 (복사한 파일은 git 에서 제외됨)
cp deploy/rag-helm/secret-values.example.yaml deploy/rag-helm/secret-values.yaml
helm install rag-git-docs deploy/rag-helm -n rag -f deploy/rag-helm/secret-values.yaml
```

### 수집·색인을 지금 한 번 돌리기

설치 직후처럼 03:00 를 기다릴 수 없을 때 CronJob 의 설정 그대로 Job 을 하나 만든다.

```bash
kubectl -n rag create job --from=cronjob/rag-git-docs-sync sync-now
kubectl -n rag logs -f job/sync-now
kubectl -n rag delete job sync-now    # 같은 이름으로 다시 만들려면 지운다
```

## Claude Code 와 연동하기

검색 서버는 NodePort 로 EC2 의 `30876` 포트에 열린다. EC2 보안그룹에서 이 포트를 내 IP 에만 연다.
요청마다 `secret-values.yaml` 에 넣은 `SERVE_TOKEN` 을 확인한다.

```bash
claude mcp add --transport http --scope user git-docs http://<EC2 주소>:30876/mcp \
  --header "Authorization: Bearer <SERVE_TOKEN>"
```

검색 서버 토큰과 검색 내용이 평문 HTTP 로 오간다. 보안그룹을 넓게 열 거면 앞에 TLS 를 둔다.

### 왜 Qdrant 에 바로 붙지 않고 검색 서버를 거치나

- Qdrant 는 질문 텍스트가 아니라 벡터를 받는다
- 그 벡터는 색인 때와 같은 모델(bge-m3)로 만들어야 하는데, Claude Code 는 그 모델을 돌리지 못한다
- 그래서 검색 서버가 모델을 띄워 두고, 질문을 벡터로 바꿔 Qdrant 에 묻는다
- MCP 는 Claude Code 가 이런 서버를 도구로 불러 쓰게 하는 표준 규약이다

### 왜 Qdrant 공식 MCP 서버(mcp-server-qdrant)를 쓰지 않나

- 공식 서버는 bge-m3 를 쓸 수 없다. 색인과 다른 모델로 질문을 벡터로 바꾸면 비교가 안 된다
- 공식 서버는 dense 검색은 되지만 sparse 검색은 안 된다
  - dense 는 뜻으로 찾기 때문에 표현이 달라도 같은 내용을 찾아 준다 (다른 표현이어도 유사의미면 유사벡터값을 가짐)
  - 하지만 region-a1 과 region-a2 처럼 생김새도 뜻도 비슷한 단어는 같은 것으로 본다
  - sparse 는 단어 자체를 비교해서 이 둘을 구분한다

## 로컬에서 돌리기

```bash
cp .env.example .env && set -a && . ./.env && set +a
uv sync
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
uv run collect.py && uv run index.py && uv run serve.py    # http://localhost:8765/mcp
```
