# collect.py, index.py, serve.py 를 모두 이 이미지 하나로 돌린다.
# 무엇을 돌릴지는 k8s 매니페스트의 command 가 정한다.
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv

# clone 방식(COLLECT_MODE=clone)이 리포를 받고 코드 도구가 코드를 찾는 데 쓴다. api 방식이면 쓰지 않는다.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성을 소스보다 먼저 설치한다. 소스만 바뀌었을 때 이 층을 다시 쓰지 않아 빌드가 빠르다.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# bge-m3 모델(약 2.3GB)을 이미지에 넣는다. 실행할 때 Hugging Face 에서 받지 않으므로 외부 인터넷 없이 뜨고, 첫 기동도 빠르다.
# 소스보다 먼저 받아 두어, 소스만 바뀐 재빌드에서는 이 층을 다시 받거나 올리지 않는다. ONNX 판은 쓰지 않아 뺀다.
# 언제 빌드해도 같은 모델이 들어가도록 커밋을 고정한다. 바꾸면 색인과 벡터가 맞지 않으므로 indexer/store.py 의 VERSION 도 같이 바꾼다.
ENV BGE_M3_PATH=/opt/bge-m3 BGE_M3_REVISION=5617a9f61b028005a4858fdac845db406aefb181
RUN .venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-m3', revision='$BGE_M3_REVISION', local_dir='$BGE_M3_PATH', ignore_patterns=['onnx/*', 'imgs/*'])"

COPY collect.py collect_api.py collect_clone.py index.py serve.py auth.py ./
COPY collector collector
COPY cloner cloner
COPY indexer indexer

ENV PATH=/app/.venv/bin:$PATH

CMD ["python", "serve.py"]
