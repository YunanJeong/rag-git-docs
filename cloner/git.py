"""리포를 git 으로 받아 두고 원격의 기본 브랜치와 같게 맞춘다. 이력은 전부 받는다.

토큰은 환경변수로만 git 에 넘긴다. clone 주소에도 .git/config 에도 남지 않고, 프로세스 인자에도 보이지 않는다.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
from pathlib import Path


def auth_env(user: str, token: str) -> dict[str, str]:
    basic = base64.b64encode(f"{user}:{token}".encode()).decode()
    return {
        **os.environ,
        # 인증이 틀렸을 때 비밀번호를 물으며 멈추지 않고 실패하게 한다
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.extraHeader",
        "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
    }


def _git(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    res = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, errors="replace")
    if res.returncode:
        raise RuntimeError(f"git {args[0]}: {res.stderr.strip()[-500:]}")
    return res.stdout


def sync(dest: Path, url: str, branch: str, env: dict[str, str]) -> str:
    """dest 를 원격 branch 와 같게 만들고 커밋 해시를 돌려준다. 처음이면 clone, 이후는 fetch."""
    if (dest / ".git").is_dir():
        # 기본 브랜치가 바뀌었거나 강제 push 됐어도 원격과 같아지도록 pull 대신 fetch 후 reset 한다
        _git(["fetch", "--quiet", "--no-tags", "origin", branch], dest, env)
        _git(["reset", "--quiet", "--hard", "FETCH_HEAD"], dest, env)
        _git(["clean", "-ffdxq"], dest, env)
    else:
        # 받다가 죽으면 반쯤 받은 clone 이 남는다. 임시 이름으로 받고 다 받은 뒤에 옮긴다.
        tmp = dest.with_name(dest.name + ".clone-tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.parent.mkdir(parents=True, exist_ok=True)
        try:
            _git(["clone", "--quiet", "--no-tags", "--single-branch", "--branch", branch, url, str(tmp)], env=env)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        tmp.rename(dest)
    return _git(["rev-parse", "HEAD"], dest).strip()


def md_dates(dest: Path) -> dict[str, str]:
    """HEAD 에 있는 md 파일마다 마지막으로 바꾼 커밋의 날짜(YYYY-MM-DD). 리포 이력을 한 번만 훑는다."""
    q = ["-c", "core.quotepath=off"]
    pathspec = ["--", ":(icase)*.md"]
    current = set(_git([*q, "ls-files", *pathspec], dest).splitlines())
    dates: dict[str, str] = {}
    date = ""
    # 최신 커밋부터 나오므로 파일마다 처음 나온 날짜가 마지막 수정일이다
    for line in _git([*q, "log", "--format=%x00%cs", "--name-only", "--no-renames", "HEAD", *pathspec], dest).splitlines():
        if line.startswith("\x00"):
            date = line[1:]
        elif line in current:
            dates.setdefault(line, date)
    return dates
