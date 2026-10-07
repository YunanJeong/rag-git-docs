"""clone 방식에서 검색 서버가 노출하는 코드 도구. DOCS_DIR 의 clone 을 git grep·git show 로 읽는다.

수집 기록(.manifest.json 의 heads)에 있는 리포만 읽는다. 파일은 커밋된 내용(HEAD)을 읽으므로
../ 나 심링크로 리포 밖을 읽을 수 없다. 출력은 상한에서 자르고 잘렸다고 알린다.
docstring 이 그대로 도구 설명이 된다.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from cloner import state

MAX_MATCH_LINES = 200
MAX_READ_LINES = 300
MAX_LINE_CHARS = 300
MAX_FILE_BYTES = 2_000_000
TIMEOUT = 20


def _repo_dir(repo: str) -> Path:
    root = Path(os.environ["DOCS_DIR"])
    heads, _ = state.load(root)
    if repo not in heads:
        raise ValueError(f"없는 리포다: {repo}\n있는 리포: {', '.join(sorted(heads))}")
    return root / repo


def _git(repo_dir: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    # 검색 서버는 clone 을 읽기 전용으로 붙이고, 파일 주인이 수집 파드와 다를 수 있어 safe.directory 를 푼다
    return subprocess.run(
        ["git", "-c", "safe.directory=*", "-C", str(repo_dir), *args],
        capture_output=True, text=True, errors="replace", timeout=TIMEOUT,
    )


def _clip(line: str) -> str:
    return line if len(line) <= MAX_LINE_CHARS else line[:MAX_LINE_CHARS] + " …"


def search_code(repo: str, pattern: str, path: str = "") -> str:
    """리포 하나의 코드에서 정규식(확장 정규식)과 일치하는 줄을 찾는다. 앞뒤 2줄을 함께 준다.

    search_docs 로 문서를 먼저 찾고, 문서로 답이 안 될 때 특정 함수·설정 키·에러 문구가
    코드 어디에 있는지 확인하는 용도다.
    repo 는 "<그룹>/<리포>" 이다. search_docs 결과 경로의 앞부분과 같다.
    path 를 주면 그 아래(또는 그 glob, 예: "*.py", "src/**/*.yaml")만 찾는다.
    결과는 "파일:줄번호:내용" 이고 최대 200줄에서 자른다. 잘리면 path 나 pattern 으로 좁힌다.
    """
    try:
        repo_dir = _repo_dir(repo)
        res = _git(repo_dir, ["grep", "-n", "-I", "-E", "-C", "2", "--no-color", "-e", pattern, "--", path or "."])
    except ValueError as e:
        return str(e)
    except subprocess.TimeoutExpired:
        return "시간이 초과됐다. path 로 범위를 좁힌다"
    if res.returncode == 1:
        return "일치하는 줄이 없다"
    if res.returncode:
        return f"실패: {res.stderr.strip()}"
    lines = res.stdout.splitlines()
    out = [_clip(line) for line in lines[:MAX_MATCH_LINES]]
    if len(lines) > MAX_MATCH_LINES:
        out.append(f"… {len(lines)}줄 중 {MAX_MATCH_LINES}줄에서 잘랐다. path 나 pattern 으로 좁힌다")
    return "\n".join(out)


def read_code(repo: str, path: str, start: int = 1, end: int = 0) -> str:
    """리포 하나의 파일을 줄 범위로 읽는다. 한 번에 최대 300줄이다.

    search_code 로 위치를 찾은 뒤 앞뒤 맥락을 볼 때 쓴다.
    repo 는 "<그룹>/<리포>", path 는 리포 안 경로다. 디렉터리를 주면 그 안의 목록을 준다.
    start·end 는 1부터 세는 줄 번호이고, end 를 비우면 start 부터 300줄을 준다.
    """
    spec = f"HEAD:{path.strip().lstrip('/')}"
    try:
        repo_dir = _repo_dir(repo)
        size = _git(repo_dir, ["cat-file", "-s", spec])
        if size.returncode:
            return f"없는 경로다: {path}"
        if int(size.stdout) > MAX_FILE_BYTES:
            return f"파일이 너무 크다({int(size.stdout)}바이트). search_code 로 위치를 찾는다"
        res = _git(repo_dir, ["show", spec])
    except ValueError as e:
        return str(e)
    except subprocess.TimeoutExpired:
        return "시간이 초과됐다"
    if res.returncode:
        return f"실패: {res.stderr.strip()}"
    if "\x00" in res.stdout:
        return "바이너리 파일이라 읽지 않는다"
    lines = res.stdout.splitlines()
    start = max(start, 1)
    stop = min(end or start + MAX_READ_LINES - 1, start + MAX_READ_LINES - 1, len(lines))
    out = [f"[{repo}/{path} {start}-{stop}줄 / 전체 {len(lines)}줄]"]
    out += [f"{n}: {_clip(lines[n - 1])}" for n in range(start, stop + 1)]
    if stop < len(lines) and (not end or end > stop):
        out.append(f"… 이어서 읽으려면 start={stop + 1}")
    return "\n".join(out)
