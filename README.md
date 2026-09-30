# rag-git-docs

GitLab·GitHub 리포에 흩어진 마크다운 문서를 모아 벡터 DB 에 넣고,
팀원의 Claude Code 가 그 문서를 검색해 답하게 한다.

```
리포 ──collect.py──▶ DOCS_DIR ──index.py──▶ Qdrant ◀──serve.py (MCP)──▶ 팀원 Claude Code
```

## 설치

필요한 것은 [uv](https://docs.astral.sh/uv/), Docker, GitLab 또는 GitHub 토큰이다.

```bash
cp .env.example .env        # 값을 채운다
uv sync
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

k3s 에 Qdrant 를 올릴 거면 [deploy/qdrant/values.yaml](deploy/qdrant/values.yaml) 을 쓴다.

## 실행

```bash
set -a && . ./.env && set +a

uv run collect.py    # 리포에서 md 를 DOCS_DIR 로 받는다. 두 번째부터는 바뀐 것만
uv run index.py      # DOCS_DIR 을 전부 색인한다
uv run serve.py      # 검색 서버를 띄운다 (포트 8765)
```

문서를 최신으로 유지하려면 `collect.py` 와 `index.py` 를 cron 으로 매일 돌린다.
색인하는 동안에도 검색은 끊기지 않는다.

```
0 3 * * * cd /opt/rag-git-docs && set -a && . ./.env && uv run collect.py && uv run index.py
```

## 팀원이 붙기

각자 한 번만 실행한다. `<서버>` 와 `<SERVE_TOKEN>` 은 관리자에게 받는다.

```bash
claude mcp add --transport http --scope user git-docs http://<서버>:8765/mcp \
  --header "Authorization: Bearer <SERVE_TOKEN>"
```

이후 Claude Code 에게 "배포 롤백 어떻게 해?" 처럼 물으면 사내 문서를 찾아보고 답한다.

## 폴더

| 경로 | 하는 일 |
|---|---|
| `collect.py` `index.py` `serve.py` | 실행 파일. 위 순서대로 쓴다 |
| `sources/` | GitLab·GitHub API 호출 |
| `collector/` | 무엇을 새로 받고 무엇을 지울지 정한다 |
| `vectordb/` | 문서를 잘라 벡터로 바꿔 Qdrant 에 넣고, 거기서 찾는다 |
| `deploy/` | Qdrant Helm 설정 |
| `infra/` | EC2 테라폼 (예정) |
| `docs/design.md` | 설계를 왜 이렇게 했는지에 대한 기록 |

## 테스트

```bash
uv run pytest -q
```
