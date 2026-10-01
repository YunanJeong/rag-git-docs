# rag-git-docs

GitLab·GitHub 리포의 마크다운 문서를 Qdrant 에 넣고, Claude Code 에서 검색한다.

```
collect.py   리포에서 md 를 DOCS_DIR 로 받는다. 두 번째부터는 바뀐 것만
index.py     md 를 잘라 임베딩해 Qdrant 에 넣는다
serve.py     Claude Code 가 붙는 검색 서버 (MCP)
```

## 실행

```bash
cp .env.example .env              # 값을 채운다
set -a && . ./.env && set +a
uv sync
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant

uv run collect.py
uv run index.py
uv run serve.py
```

문서를 갱신하려면 `collect.py` 와 `index.py` 를 다시 돌린다. 색인하는 동안에도 검색은 된다.

## 서버에 상시 띄우기

검색 서버는 계속 떠 있고, 수집과 색인은 매일 03:00 에 돈다.

```bash
# 유닛 파일의 User, WorkingDirectory, uv 경로를 서버 값으로 고친 뒤
sudo cp deploy/systemd/rag-git-docs-* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rag-git-docs-serve.service rag-git-docs-sync.timer

sudo systemctl start rag-git-docs-sync.service   # 첫 수집·색인을 바로 돌린다
journalctl -u rag-git-docs-sync -n 50            # 로그
```

## k3s 에 Qdrant 올리기

docker 대신 k3s 에 올릴 때 쓴다. API 키를 담을 Secret 을 먼저 만들어야 키가 켜진다.

```bash
kubectl create namespace qdrant
kubectl -n qdrant create secret generic qdrant-api-key --from-literal=api-key="$QDRANT_API_KEY"
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm install rag-qdrant qdrant/qdrant -n qdrant -f deploy/qdrant/values.yaml
```

`.env` 의 `QDRANT_URL` 을 `http://<노드 IP>:30633` 으로 바꾼다.

## Claude Code 에 붙이기

서버는 `127.0.0.1:8765` 에만 열린다. 내 PC 에서 SSH 터널로 붙는다.

```bash
ssh -N -L 8765:localhost:8765 <서버>
claude mcp add --transport http --scope user git-docs http://localhost:8765/mcp
```

## 폴더

| 경로 | 하는 일 |
|---|---|
| `sources/` | GitLab·GitHub API 에서 리포 목록과 md 를 받는다 |
| `collector/` | 무엇을 새로 받고 무엇을 지울지 정하고, 디스크에 반영한다 |
| `indexer/` | md 를 잘라 벡터로 바꾸고, Qdrant 에 넣고 찾는다 |
| `deploy/` | k3s 용 Qdrant Helm 설정, 서버용 systemd 유닛 |
| `infra/` | 서버 테라폼 (예정) |
| `docs/design.md` | 왜 이렇게 만들었는지에 대한 기록. 코드를 고치기 전에 읽는다 |
