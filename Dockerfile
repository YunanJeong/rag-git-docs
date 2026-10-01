# collect.py, index.py, serve.py 를 모두 이 이미지 하나로 돌린다.
# 무엇을 돌릴지는 k8s 매니페스트의 command 가 정한다.
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv

WORKDIR /app

# 의존성을 소스보다 먼저 설치한다. 소스만 바뀌었을 때 이 층을 다시 쓰지 않아 빌드가 빠르다.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY collect.py index.py serve.py ./
COPY collector collector
COPY indexer indexer

# bge-m3 모델(2.3GB)을 받아 둘 곳이다. 볼륨을 붙여야 실행마다 다시 받지 않는다.
ENV PATH=/app/.venv/bin:$PATH HF_HOME=/cache/hf

CMD ["python", "serve.py"]
