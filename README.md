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

## k3s 에 올리기

```bash
# 1. Qdrant. API 키 Secret(rag-qdrant-apikey)도 차트가 만든다
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm install rag-qdrant qdrant/qdrant -n qdrant --create-namespace -f deploy/qdrant-helm/values.yaml

# 2. 이미지를 k3s 에 넣는다
docker build -t rag-git-docs:latest .
docker save rag-git-docs:latest | sudo k3s ctr images import -

# 3. 앱. values.yaml 에 그룹 이름을, secret-values.yaml 에 토큰을 채운다
cp deploy/rag-helm/secret-values.example.yaml deploy/rag-helm/secret-values.yaml
helm install rag-git-docs deploy/rag-helm -n qdrant -f deploy/rag-helm/secret-values.yaml
```

수집과 색인은 매일 03:00 에 처음 돈다. 그 전까지는 검색 결과가 없다.
`secret-values.yaml` 은 커밋되지 않는다.

## Claude Code 에 붙이기

검색 서버는 인증이 없어서 클러스터 밖에 열지 않는다. 터널로 붙는다.

```bash
# 서버에서
kubectl -n qdrant port-forward svc/rag-git-docs-serve 8765:8765

# 내 PC 에서
ssh -N -L 8765:localhost:8765 <서버>
claude mcp add --transport http --scope user git-docs http://localhost:8765/mcp
```

## 로컬에서 돌리기

```bash
cp .env.example .env && set -a && . ./.env && set +a
uv sync
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
uv run collect.py && uv run index.py && uv run serve.py
```
