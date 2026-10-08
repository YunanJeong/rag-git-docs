# rag-git-docs

> GitLab·GitHub 리포의 문서를 Qdrant Vector DB 에 색인해, Claude Code 가 조직의 맥락으로 답하게 하는 검색 MCP 서버다. clone 모드에서는 코드와 git 이력을 분석하는 MCP tool 도 함께 제공한다.

AI 는 기술의 일반적인 맥락에는 밝지만, 조직의 비즈니스 맥락은 알지 못한다.
같은 질문에도 "보통은 이렇게 한다"와 "우리는 이렇게 한다"는 다를 때가 많고, 실무에 필요한 답은 늘 후자다.

농담 반 진담 반으로, Git 은 경력 개발자의 뇌를 대체한다고 한다.
무엇을 왜 그렇게 만들었는지, 어떻게 배포하고 장애 때 무엇을 했는지가 사람의 기억이 아니라 리포의 문서와 코드, 이력에 남기 때문이다.
AI 가 모르는 조직의 맥락이 이미 Git 에 기록으로 쌓여 있는 셈이니, Git 만큼 RAG 를 붙이기 좋은 곳도 드물다.

이 프로젝트는 리포들에 흩어진 md 문서를 모아 Qdrant Vector DB 에 색인하고, Claude Code 가 MCP서버를 통해 질문에 맞는 조각만 찾아 쓰게 한다.
**색인하는 것은 문서뿐이다.** `clone` 모드에서는 리포 전체와 git 이력을 받아 두고, 문서로 답이 안 될 때 코드와 변경 이력을 직접 분석하는 MCP tool(`search_code`, `read_code`, `code_history`)을 함께 제공한다.

## 수집 방식 — md only(`api`) 와 리포 전체(`clone`)

무엇을 서버에 들여올지 두 가지 중에 고른다. 둘의 차이는 기술보다 **보안과 품질 사이의 선택**이다.
환경변수 `COLLECT_MODE` 하나로 바꾸고, 기본값은 `api` 다.

### `api` — md only. 보안을 우선한다 (기본값)

REST API 로 리포마다 `.md` 파일만 받는다. 코드는 받지 않는다.

- **서버에 남는 것이 md 본문뿐이다.** 코드도, `.git` 에 딸려 오는 전체 파일 목록·커밋 메시지·작성자 이메일·과거 이력도 없다.
  서버나 볼륨, 그 백업이 새어 나가도 유출 범위가 문서에서 그친다.
- **코드에 실수로 커밋된 비밀번호·키가 들어오지 않는다.** 이력을 받지 않으니, 지운 줄 알았던 시크릿도 들어오지 않는다.
- **MCP서버 토큰이 새어도 피해가 작다.** 쓸 수 있는 도구가 문서 조각 검색(`search_docs`) 하나뿐이다. 코드를 읽는 도구가 없다.
- 대신 코드로만 답할 수 있는 질문에는 답하지 못한다.
  바뀐 것만 받기, 지운 문서 지우기, 문서별 날짜 구하기를 직접 짠 코드와 API 호출로 한다.

### `clone` — 리포 전체. 품질과 관리 편의를 얻는다 (PoC)

리포를 이력까지 통째로 `git clone` 해 두고, 주기적으로 `git fetch` 해 원격과 맞춘다.
MCP서버에 코드 도구 `search_code`, `read_code`, `code_history` 가 더해진다.
코드 도구는 문서 검색으로 답이 안 될 때만 쓰도록 MCP서버 지침과 도구 설명에 못박아 두었다. 빠르고 토큰을 적게 쓰는 문서 검색의 장점을 코드 탐색이 잡아먹지 않게 하기 위해서다.

- **답의 품질이 오른다.** "이 설정 키를 실제로 어디서 읽나", "이 동작은 언제 왜 바뀌었나"처럼 문서로 답이 안 되는 질문에 코드와 커밋 이력을 근거로 답한다.
  문서와 실제 코드가 어긋날 때 코드 쪽을 확인할 수 있다.
- **관리가 편해진다.** 바뀐 것만 받기와 지운 것 지우기를 git 이 한다. 문서별 날짜는 `git log` 에서 바로 나온다.
  주기적으로 fetch 만 하고 질문할 때는 git 호스팅을 부르지 않아, 호스팅 쪽 부하도 적다.
- **대가는 보안이다.**
  - 볼륨과 그 백업에 사내 코드 전체와 이력의 사본이 생긴다.
  - 실수로 커밋된 시크릿이 이력째 들어온다. 이미 지운 것도 들어오고, `code_history` 로 과거 변경 내용을 볼 수 있다.
  - 커밋 메시지와 작성자 이름이 MCP서버로 보인다. 작성자 이메일은 주지 않는다.
  - MCP서버 토큰만 있으면, 수집 계정이 볼 수 있는 모든 리포의 코드를 `read_code` 로 반복해 옮겨 적을 수 있다.
    토큰 관리와 네트워크 접근 제한을 api 보다 엄격하게 해야 한다.
  - 리포별 권한을 나누지 않는다. 쓰는 사람 모두가 대상 리포를 다 볼 수 있다는 전제다.
- 디스크가 대상 리포의 저장소 크기 합계에 작업 트리만큼을 더한 만큼 든다.

**`clone` 은 PoC 다.** 코드 사본을 서버에 둬도 되는지는 조직의 보안 정책에 달려 있으므로, 확인한 뒤 쓴다.
api 를 갈아엎지 않고 나란히 두어 환경변수만 바꾸면 오갈 수 있게 했다.
두 방식은 같은 볼륨 안에서 다른 디렉터리를 쓰므로(`/data/docs`, `/data/repos`), 되돌리면 각자의 데이터를 이어서 쓴다.

| | `api` (기본) | `clone` (PoC) |
|---|---|---|
| 서버에 두는 것 | md 파일 | 리포 전체와 이력 |
| MCP서버 도구 | `search_docs` | `search_docs`, `search_code`, `read_code`, `code_history` |
| GitLab 토큰 스코프 | `read_api` | `read_api` + `read_repository` |
| `DOCS_DIR` (헬름) | `/data/docs` | `/data/repos` |

## 구조

실행 파일 셋이 번호 순서로 돈다. 1·2 는 매일 한 번, 3 은 계속 떠 있다.
수집(`collector/`·`cloner/`)과 색인(`indexer/`)은 서로 import 하지 않는다. 둘을 잇는 것은 실행 파일뿐이다.

```
rag-git-docs/
├── collect.py            1. COLLECT_MODE 를 보고 아래 둘 중 하나를 부른다
├── collect_api.py           api   md 파일만 API 로 DOCS_DIR 에 받는다                   → collector/
├── collect_clone.py         clone 리포를 이력까지 DOCS_DIR 에 git clone 해 두고 맞춘다  → cloner/ + collector/sources
├── index.py              2. DOCS_DIR 의 md 를 Qdrant 에 색인한다. 수집 방식을 모른다    → indexer/
├── serve.py              3. MCP서버. Claude Code 의 질문으로 Qdrant 에서 관련 조각을 찾아 준다
│                            clone 이면 코드 도구(search_code, read_code, code_history)도 노출한다 → cloner/code.py
│
├── collector/            api 방식. git 호스팅에서 md 를 내려받아 DOCS_DIR 에 둔다
│   ├── sources/          GitLab·GitHub API 호출. 호스팅마다 파일 하나. clone 도 리포 목록·인증은 여기서 받는다
│   │   ├── gitlab.py     그룹의 리포 목록, 리포 안 md 목록, md 내용, git 인증 정보를 준다
│   │   ├── github.py     계정의 리포에 대해 같은 일을 한다
│   │   ├── _http.py      HTTP GET 과 페이지 넘기기. 두 API 가 같은 방식이라 같이 쓴다
│   │   └── types.py      리포 정보(Repo)와, 파일 목록에서 md 만 골라내는 함수
│   ├── manifest.py       지난번에 받은 목록과 비교해 새로 받을 것, 지울 것을 정한다
│   └── files.py          md 를 DOCS_DIR 에 쓰고 지운다. 받은 목록을 .manifest.json 에 남긴다
│
├── cloner/               clone 방식. 리포를 git 으로 받아 두고, MCP서버가 그 코드를 읽는다
│   ├── git.py            clone·fetch 로 원격과 맞추고, md 마다 마지막 커밋일을 git log 로 구한다
│   ├── state.py          리포마다 맞춘 커밋 해시와 날짜를 .manifest.json 에 남긴다. 지울 clone 을 정한다
│   └── code.py           MCP서버의 코드 도구. clone 을 git grep·git show·git log 로 읽는다
│
├── indexer/              2 단계. md 를 잘라 벡터로 바꿔 Qdrant 에 넣는다
│   ├── chunk.py          md 를 헤딩마다 잘라 조각으로 만든다
│   ├── embed.py          조각을 임베딩 모델 bge-m3 로 벡터로 바꾼다
│   └── store.py          벡터를 Qdrant 에 넣는다. 색인하는 동안에도 검색이 끊기지 않게 한다
│
├── charts/
│   └── rag-git-docs/     1·2·3 을 띄우는 Helm 차트 소스. 1·2 는 CronJob, 3 은 Deployment. values.yaml 은 기본값
├── deploy/               이 환경(EC2 k3s)에 배포하는 것
│   ├── packages/         설치할 차트 패키지. rag-git-docs 는 helm package 로 만들고, Qdrant 는 공식에서 받는다
│   ├── qdrant.values.yaml           Qdrant 차트 기본값 위에 덮어쓰는 이 환경의 값
│   ├── qdrant.clone.values.yaml     clone 모드 릴리스용 Qdrant 의 값. 이 파일 하나로 설치한다
│   ├── rag-git-docs.values.yaml     rag-git-docs 차트 기본값 위에 덮어쓰는 이 환경의 값
│   ├── rag-git-docs.clone.values.yaml   clone 모드 릴리스의 값. 이 파일 하나로 설치한다
│   └── rag-git-docs.secret.example.yaml   토큰 자리. 복사본은 git 에서 제외
├── infra/                서버 테라폼 (예정)
├── tests/                지울 파일 판정, md 자르기, clone 기록과 git 동작 테스트
└── docs/
    ├── design.md                 왜 이렇게 만들었는지에 대한 기록. 코드를 고치기 전에 읽는다
    └── proposal-git-clone.md     clone 방식 검토 기록과 결정 사항
```

`serve.py` 는 `indexer/` 의 `embed.py` 와 `store.py` 를 가져다 쓴다. 질문을 문서와 비교하려면
색인 때와 같은 모델로 질문도 벡터로 바꿔야 하고, 색인과 같은 Qdrant 컬렉션을 읽어야 하기 때문이다.

## 배포

```bash
# 이미지. 태그는 deploy/rag-git-docs.values.yaml 의 image.tag 와 맞춘다
docker build -t private.docker.wai/yunan/rag-git-docs:0.5.0 . && docker push private.docker.wai/yunan/rag-git-docs:0.5.0

# 차트 패키지. 차트 템플릿을 고쳤을 때만 Chart.yaml 의 version 을 올리고 다시 만든다
helm package charts/rag-git-docs -d deploy/packages

# Qdrant 먼저. 이 차트가 만드는 서비스와 Qdrant API 키 Secret 을 rag-git-docs 가 이름으로 찾으므로 같은 네임스페이스에 둔다
helm install rag-qdrant deploy/packages/qdrant-1.19.1.tgz -n rag --create-namespace -f deploy/qdrant.values.yaml

# 앱. 예시 파일을 복사해 비밀값을 채우고 설치할 때 함께 넘긴다 (복사한 파일은 git 에서 제외됨)
cp deploy/rag-git-docs.secret.example.yaml deploy/rag-git-docs.secret.yaml
helm install rag-git-docs deploy/packages/rag-git-docs-0.3.0.tgz -n rag \
  -f deploy/rag-git-docs.values.yaml -f deploy/rag-git-docs.secret.yaml
```

### 앱만 바뀌었을 때

차트는 그대로 두고 이미지만 새 태그로 올린 뒤, `deploy/rag-git-docs.values.yaml` 의 `image.tag` 를 바꿔 upgrade 한다.

```bash
helm upgrade rag-git-docs deploy/packages/rag-git-docs-0.3.0.tgz -n rag \
  -f deploy/rag-git-docs.values.yaml -f deploy/rag-git-docs.secret.yaml
```

### 수집·색인을 지금 한 번 돌리기

설치 직후처럼 03:00 를 기다릴 수 없을 때 CronJob 의 설정 그대로 Job 을 하나 만든다.

```bash
kubectl -n rag create job --from=cronjob/rag-git-docs-sync sync-now
kubectl -n rag logs -f job/sync-now
kubectl -n rag delete job sync-now    # 같은 이름으로 다시 만들려면 지운다
```

### 수집 방식 고르기

차트는 수집 방식을 모른다. values 의 `env` 를 수집·색인 CronJob 과 MCP서버에 그대로 환경변수로 넣을 뿐이다.
그래서 방식마다 릴리스를 따로 두면 된다.

**두 방식을 동시에 띄우기.** 네임스페이스와 릴리스를 나누면 볼륨·Service·Secret 이 따로 생겨 한 노드에서도 서로 격리된다.
Qdrant 도 네임스페이스마다 하나씩 띄운다. 겹치는 것은 클러스터 전체에서 하나뿐인 노드 포트와 CronJob 시각이라, clone 용 values 가 이것만 바꾼다.

clone 버전 실행 예시:

```bash
kubectl create ns rag-clone
helm install rag-qdrant deploy/packages/qdrant-1.19.1.tgz -n rag-clone -f deploy/qdrant.clone.values.yaml
helm install rag-git-docs deploy/packages/rag-git-docs-0.3.0.tgz -n rag-clone -f deploy/rag-git-docs.clone.values.yaml -f deploy/rag-git-docs.secret.yaml

# 첫 수집을 바로 돌린다
kubectl -n rag-clone create job --from=cronjob/rag-git-docs-sync sync-now 
```

clone 용 values 는 api 용과 같은 항목을 모두 적은 별도 파일이라, 그 파일 하나로 설치한다. api 용과 다른 값은 수집 방식, MCP서버·Qdrant 의 노드 포트, CronJob 시각, Qdrant 별칭(`QDRANT_ALIAS`), 볼륨 크기다.

**한 릴리스에서 갈아끼우기.** `env` 의 `COLLECT_MODE` 와 `DOCS_DIR` 을 함께 바꾸고 upgrade 한다.
두 방식은 같은 볼륨 안에서 다른 디렉터리(`/data/docs`, `/data/repos`)를 쓰므로, 되돌리면 각자의 데이터를 이어서 쓴다.

clone 은 첫 수집에 리포 전체를 이력까지 받으므로 오래 걸린다. 그 전에 GitLab 토큰에 `read_repository` 스코프를 더하고, 볼륨에 리포 전체가 들어갈 여유가 있는지 확인한다.
local-path 처럼 크기를 강제하지 않는 스토리지라면 실제 한도는 노드 디스크다.

## Claude Code 와 연동하기

MCP서버는 NodePort 로 EC2 의 `30876` 포트에 열린다. EC2 보안그룹에서 이 포트를 내 IP 에만 연다.
요청마다 `rag-git-docs.secret.yaml` 에 넣은 MCP서버 토큰(`SERVE_TOKEN`)을 확인한다.

```bash
claude mcp add --transport http --scope user git-docs http://<EC2 주소>:30876/mcp \
  --header "Authorization: Bearer <SERVE_TOKEN>"
```

토큰과 검색 내용이 평문 HTTP 로 오간다. 보안그룹을 넓게 열 거면 앞에 TLS 를 둔다.
clone 방식이면 이 토큰으로 코드까지 읽을 수 있으므로 특히 그렇다.

### 왜 Qdrant 에 바로 붙지 않고 MCP서버를 거치나

- Qdrant 는 질문 텍스트가 아니라 벡터를 받는다
- 그 벡터는 색인 때와 같은 모델(bge-m3)로 만들어야 하는데, Claude Code 는 그 모델을 돌리지 못한다
- 그래서 MCP서버가 모델을 띄워 두고, 질문을 벡터로 바꿔 Qdrant 에 묻는다
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

# clone 방식. DOCS_DIR 은 api 와 다른 곳을 쓴다 (같은 곳이면 수집이 시작하지 않는다). 로컬에 git 이 있어야 한다
export COLLECT_MODE=clone DOCS_DIR=/var/lib/rag-git-docs/repos
uv run collect.py && uv run index.py && uv run serve.py
```
