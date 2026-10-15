# 운영 가이드

rag-git-docs 를 설치하고 관리하는 사람을 위한 문서다. 쓰는 사람에게 안내할 연결 방법과 사용법은 [사용 가이드](usage.md)에 있다.

## 설치

설치 전에 values 파일 `deploy/rag-git-docs.values.yaml` 과 비밀값 파일의 다음 값을 환경에 맞게 채운다. values 는 리포 전체를 받는 수집 방식(`clone`)으로 되어 있고, 다른 방식(`api`)으로 바꾸는 법은 파일 안 주석과 아래 "수집 방식 고르기" 에 있다.

| 값 | 내용 |
|---|---|
| `image.repository`, `image.tag` | 아래에서 빌드해 올린 이미지 |
| `sync.env.SOURCE` | 문서를 받아 올 곳. `gitlab` 또는 `github` |
| `sync.env.GITLAB_URL`, `sync.env.GITLAB_GROUP` | GitLab 이면 GitLab 주소와 수집할 그룹 경로. 하위 그룹까지 수집한다 |
| `sync.env.GITHUB_OWNER` | GitHub 이면 수집할 계정이나 조직 이름 |
| `env.AUTH_MODE` | `token`(기본, 사용자별 토큰). 아래 "인증". `none` 은 로컬 실행 전용이라 서버에서는 뜨지 않는다 |
| 비밀값 파일의 `SERVE_TOKEN` | 팀원별 MCP서버 토큰. 아래 "토큰 관리" |
| 비밀값 파일의 `GITLAB_TOKEN` 또는 `GITHUB_TOKEN` | 수집용 PAT |

```bash
# 이미지. 태그는 values 의 image.tag 와 맞춘다
docker build -t private.docker.wai/yunan/rag-git-docs:0.6.3 . && docker push private.docker.wai/yunan/rag-git-docs:0.6.3

# 차트 패키지. 차트 템플릿을 고쳤을 때만 Chart.yaml 의 version 을 올리고 다시 만든다
helm package charts/rag-git-docs -d deploy/packages

# Qdrant 먼저. 이 차트가 만드는 서비스와 Qdrant API 키 Secret 을 rag-git-docs 가 이름으로 찾으므로 같은 네임스페이스에 둔다
helm install rag-qdrant deploy/packages/qdrant-1.19.1.tgz -n rag --create-namespace -f deploy/qdrant.values.yaml

# 앱. 예시 파일을 복사해 비밀값을 채우고 설치할 때 함께 넘긴다 (복사한 파일은 git 에서 제외됨)
cp deploy/rag-git-docs.secret.example.yaml deploy/rag-git-docs.secret.yaml
helm install rag-git-docs deploy/packages/rag-git-docs-0.4.1.tgz -n rag \
  -f deploy/rag-git-docs.values.yaml -f deploy/rag-git-docs.secret.yaml

# 첫 수집·색인. 리포 전체를 이력까지 받으므로 오래 걸린다
kubectl -n rag create job --from=cronjob/rag-git-docs-sync sync-now
```

설치한 뒤에 네임스페이스나 릴리스 이름을 바꾸면 upgrade 가 아니라 새 설치가 되어, 리포와 색인을 처음부터 다시 받는다.

설치가 끝나면 쓰는 사람에게 MCP서버 주소(`http://<노드 주소>:<serve.service.nodePort>/mcp`)와 각자의 토큰을 보안 채널로 주고, [사용 가이드](usage.md)를 안내한다.

### 앱만 바뀌었을 때

차트는 그대로 두고 이미지만 새 태그로 올린 뒤, values 의 `image.tag` 를 바꿔 upgrade 한다.

```bash
helm upgrade rag-git-docs deploy/packages/rag-git-docs-0.4.1.tgz -n rag \
  -f deploy/rag-git-docs.values.yaml -f deploy/rag-git-docs.secret.yaml
```

### 수집·색인을 지금 한 번 돌리기

설치 직후처럼 정해진 시각을 기다릴 수 없을 때 CronJob 의 설정 그대로 Job 을 하나 만든다.

```bash
kubectl -n rag create job --from=cronjob/rag-git-docs-sync sync-now
kubectl -n rag logs -f job/sync-now
kubectl -n rag delete job sync-now    # 같은 이름으로 다시 만들려면 지운다
```

## 수집 방식 고르기

values 의 `env.COLLECT_MODE` 로 `api` 와 `clone` 중 하나를 고른다. 이 배포는 `clone` 이다. 둘의 차이는 기술보다 **보안과 품질 사이의 선택**이다.

### `api` — md only. 보안을 우선한다

GitLab·GitHub 의 REST API 로 리포마다 `.md` 파일만 받는다. 코드는 받지 않는다.

- **서버에 남는 것이 md 본문뿐이다.** 코드도, `.git` 에 딸려 오는 전체 파일 목록·커밋 메시지·작성자 이메일·과거 이력도 없다.
  서버나 볼륨, 그 백업이 새어 나가도 유출 범위가 문서에서 그친다.
- **코드에 실수로 커밋된 비밀번호·키가 들어오지 않는다.** 이력을 받지 않으니, 지운 줄 알았던 시크릿도 들어오지 않는다.
- **`SERVE_TOKEN` 이 새어도 피해가 작다.** 쓸 수 있는 도구가 문서 조각 검색(`search_docs`) 하나뿐이다. 코드를 읽는 도구가 없다.
- 대신 코드로만 답할 수 있는 질문에는 답하지 못한다.
  바뀐 것만 받기, 지운 문서 지우기, 문서별 날짜 구하기를 직접 짠 코드와 API 호출로 한다.

### `clone` — 리포 전체. 품질과 관리 편의를 얻는다

리포를 이력까지 통째로 `git clone` 해 두고, 주기적으로 `git fetch` 해 원격과 맞춘다.
Vector DB 에 색인하는 것은 api 와 같이 md 뿐이다. 코드는 볼륨에 둔 채로, MCP서버에 더해지는 코드 도구 `search_code`, `read_code`, `code_history` 가 직접 읽는다.
코드 도구는 문서 검색으로 답이 안 될 때만 쓰도록 MCP서버 지침과 도구 설명에 못박아 두었다. 빠르고 토큰을 적게 쓰는 문서 검색의 장점을 코드 탐색이 잡아먹지 않게 하기 위해서다.

- **답의 품질이 오른다.** "이 설정 키를 실제로 어디서 읽나", "이 동작은 언제 왜 바뀌었나"처럼 문서로 답이 안 되는 질문에 코드와 커밋 이력을 근거로 답한다.
  문서와 실제 코드가 어긋날 때 코드 쪽을 확인할 수 있다.
- **관리가 편해진다.** 바뀐 것만 받기와 지운 것 지우기를 git 이 한다. 문서별 날짜는 `git log` 에서 바로 나온다.
  주기적으로 fetch 만 하고 질문할 때는 git 호스팅을 부르지 않아, 호스팅 쪽 부하도 적다.
- **대가는 보안이다.**
  - 볼륨과 그 백업에 사내 코드 전체와 이력의 사본이 생긴다.
  - 실수로 커밋된 시크릿이 이력째 들어온다. 이미 지운 것도 들어오고, `code_history` 로 과거 변경 내용을 볼 수 있다.
  - 커밋 메시지와 작성자 이름이 MCP서버로 보인다. 작성자 이메일은 주지 않는다.
  - `SERVE_TOKEN` 만 있으면, 수집 계정이 볼 수 있는 모든 리포의 코드를 `read_code` 로 반복해 옮겨 적을 수 있다.
    토큰 관리와 네트워크 접근 제한을 api 보다 엄격하게 해야 한다.
  - 리포별 권한을 나누지 않는다. 쓰는 사람 모두가 대상 리포를 다 볼 수 있다는 전제다.
- 디스크가 대상 리포의 저장소 크기 합계에 작업 트리만큼을 더한 만큼 든다.

코드 사본을 서버에 둬도 되는지는 조직의 보안 정책에 따라 정한다.

| | `api` | `clone` |
|---|---|---|
| `env.DOCS_DIR` | `/data/docs` | `/data/repos` |
| 수집용 `GITLAB_TOKEN` 스코프 | `read_api` | `read_api`. GitLab 이 이 스코프에 코드 내려받기 권한을 포함한다 |
| 수집용 `GITHUB_TOKEN` 권한 | 비공개 리포면 Contents 읽기(classic PAT 면 `repo`) | api 와 같다 |
| `persistence.docs.size` | md 사본이라 작다 | 리포 저장소 크기 합계에 작업 트리만큼을 더해 잡는다 |

api 로 바꾸려면 values 의 `COLLECT_MODE`·`DOCS_DIR`·`persistence.docs.size` 를 위 표대로 고치고 upgrade 한다. 두 방식은 같은 볼륨의 다른 디렉터리를 쓰므로 되돌리면 각자의 데이터를 이어서 쓴다.
두 방식을 같은 서버에 함께 띄우려면 values 파일을 복사해 네임스페이스·노드 포트·`QDRANT_ALIAS`·CronJob 시각을 다르게 주고 따로 설치한다.

## 인증 — 사용자별 토큰

MCP서버는 요청마다 `Authorization: Bearer` 헤더의 토큰을 `SERVE_TOKEN` 목록과 대조한다. 토큰은 사람마다 따로 만들어 본인에게 보안 채널로 준다.

### 토큰 관리

토큰은 `deploy/rag-git-docs.secret.yaml` 의 `SERVE_TOKEN` 한 곳에서 관리한다.

```yaml
SERVE_TOKEN: "kim:<토큰>,lee:<토큰>,park:<토큰>"
```

- 이름은 서버 쪽 꼬리표다. 팀원은 토큰만 쓰고, MCP서버는 받은 토큰으로 이름을 찾아 로그에 남긴다. 로그에 토큰 대신 이름이 찍히고, 이 파일에서 누구의 토큰인지 가려 한 사람만 고칠 수 있다.
- 형식이 틀리거나 이름·토큰이 겹치면 MCP서버가 뜨지 않는다.

| 할 일 | 방법 |
|---|---|
| 토큰 만들기 | `openssl rand -hex 32` |
| 사람 더하기 | 끝에 `,이름:새토큰` 을 붙이고 upgrade 한 뒤, 토큰을 본인에게 보안 채널로 준다 |
| 사람 빼기 | 그 항목을 지우고 upgrade 한다. 그 토큰은 바로 401 이 된다 |
| 토큰 바꾸기·유출 대응 | 그 사람의 토큰만 새로 만들어 바꾸고 upgrade 한다. 본인이 할 일은 [사용 가이드의 연결 관리](usage.md#연결-관리)에 있다 |

upgrade 는 이 파일을 쓰는 릴리스마다 한다. 다른 수집 방식으로 릴리스를 하나 더 띄웠다면 그쪽도 한다.

```bash
helm upgrade rag-git-docs deploy/packages/rag-git-docs-0.4.1.tgz -n rag -f deploy/rag-git-docs.values.yaml -f deploy/rag-git-docs.secret.yaml
```

토큰이 바뀌면 MCP서버 파드가 저절로 다시 뜨고, 다른 사람의 연결은 그대로다.
`secretEnv` 대신 `existingSecret` 으로 Secret 을 따로 관리한다면 저절로 다시 뜨지 않으므로 `kubectl -n <네임스페이스> rollout restart deploy/rag-git-docs-serve` 를 한다.

## 네트워크

MCP서버는 NodePort 로 노드의 `serve.service.nodePort` 포트에 열린다. 방화벽(클라우드라면 보안그룹)에서 이 포트를 쓰는 사람의 IP 에만 연다.

Claude Code 와 MCP서버 사이에는 `SERVE_TOKEN` 과 질문·검색 결과가 평문 HTTP 로 오간다. 접근을 넓게 열 거면 앞에 TLS 를 둔다.
clone 방식이면 이 토큰으로 코드까지 읽을 수 있으므로 특히 그렇다.

## 로그 — 누가 무엇을 불렀나

도구를 부를 때마다 MCP서버 로그에 `시각 이름 도구 인자` 가 한 줄씩 남는다. 이름은 `SERVE_TOKEN` 의 이름이다.

```bash
kubectl -n rag logs deploy/rag-git-docs-serve | grep read_code
```
```
2026-10-12 14:03:11 kim search_docs {'query': '배포 롤백 절차'}
2026-10-12 14:03:40 lee read_code {'repo': 'g/api', 'path': 'app.py', 'start': 1, 'end': 0}
```

로그는 파드가 다시 뜨면 사라진다. 오래 둘 기록이 필요하면 로그 수집을 따로 붙인다.

## 로컬 PC 에서 직접 설치·운영하기

자기 PC 에서 혼자 쓸 때의 절차다. `local.env.example` 이 이 용도의 환경변수 예시다. 검색 서버는 인증 없이(`AUTH_MODE=none`) 이 PC 에서만(`127.0.0.1`) 붙을 수 있게 뜬다. Docker 와, clone 방식이면 git 이 있어야 한다.

```bash
cp local.env.example .env                 # 수집할 곳과 수집용 토큰을 채운다. clone 방식이면 COLLECT_MODE 와 DOCS_DIR 도 바꾼다
set -a && . ./.env && set +a
uv sync

# Qdrant. 볼륨에 데이터를 두고, 재부팅해도 다시 뜨고, 이 PC 에서만 열린다
docker run -d --name qdrant --restart unless-stopped -p 127.0.0.1:6333:6333 -v rag-git-docs-qdrant:/qdrant/storage qdrant/qdrant

# 수집·색인. 바뀐 것이 없으면 collect.py 가 3 으로 끝나므로 && 가 아니라 ; 로 잇는다
uv run collect.py; uv run index.py

# 검색 서버. 따로 띄워 둔다. 수집·색인을 다시 돌려도 껐다 켤 필요가 없다
uv run serve.py
```

Claude Code 에는 주소만 등록하면 토큰 없이 바로 붙는다.

```bash
claude mcp add --transport http --scope user git-docs http://127.0.0.1:8765/mcp
```

문서를 갱신하려면 수집·색인만 다시 돌린다. 바뀐 것만 받고 바뀐 조각만 임베딩하며, 검색 서버는 그대로 둔다.

```bash
# 수동 갱신. 레포 디렉터리에서
set -a && . ./.env && set +a && uv run collect.py; uv run index.py

# cron 으로 매일 갱신할 때 (crontab -e). uv 는 which uv 로 나온 전체 경로를 쓴다
0 9 * * * cd <레포 경로> && (set -a; . ./.env; set +a; <uv 경로> run collect.py; <uv 경로> run index.py) >> "$HOME/.rag-git-docs/sync.log" 2>&1
```

다른 PC 에서도 붙게 하려면 `.env` 의 `AUTH_MODE` 를 `token` 으로, `SERVE_HOST` 를 `0.0.0.0` 으로 바꾸고 `SERVE_TOKEN` 을 채운다. `AUTH_MODE=none` 인 채로 `SERVE_HOST` 를 바꾸면 검색 서버가 뜨지 않는다.
