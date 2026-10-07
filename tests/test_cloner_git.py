"""clone 방식을 실제 git 으로 확인한다. 임시 디렉터리에 원본 리포를 만들어 file:// 로 받는다."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cloner import code, git, state  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git 이 없다")
ID = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def _commit(src: Path, files: dict[str, str], date: str) -> None:
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    env = {"GIT_COMMITTER_DATE": f"{date}T12:00:00", "GIT_AUTHOR_DATE": f"{date}T12:00:00", "PATH": "/usr/bin:/bin"}
    subprocess.run(["git", *ID, "-C", str(src), "add", "-A"], check=True, env=env)
    subprocess.run(["git", *ID, "-C", str(src), "commit", "-qm", date], check=True, env=env)


@pytest.fixture
def origin(tmp_path):
    src = tmp_path / "origin"
    src.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(src)], check=True)
    _commit(src, {"README.md": "# 개요\n", "docs/배포 절차.md": "# 배포\n", "app.py": "def deploy():\n    pass\n"}, "2025-01-01")
    _commit(src, {"docs/배포 절차.md": "# 배포\n롤백\n"}, "2025-02-01")
    return src


def test_clone_then_fetch_follows_origin(tmp_path, origin):
    dest = tmp_path / "docs" / "g" / "r"
    env = git.auth_env("oauth2", "dummy")
    first = git.sync(dest, origin.as_uri(), "main", env)
    assert (dest / "README.md").exists()
    assert not dest.with_name("r.clone-tmp").exists()
    assert "dummy" not in (dest / ".git" / "config").read_text(), "토큰이 .git/config 에 남았다"

    _commit(origin, {"README.md": "# 개요\n바뀜\n"}, "2025-03-01")
    second = git.sync(dest, origin.as_uri(), "main", env)
    assert second != first
    assert "바뀜" in (dest / "README.md").read_text(encoding="utf-8")


def test_md_dates_uses_last_commit_per_file(tmp_path, origin):
    dest = tmp_path / "r"
    git.sync(dest, origin.as_uri(), "main", git.auth_env("u", "t"))
    assert git.md_dates(dest) == {"README.md": "2025-01-01", "docs/배포 절차.md": "2025-02-01"}


def test_code_tools_stay_inside_repo(tmp_path, origin, monkeypatch):
    root = tmp_path / "docs"
    git.sync(root / "g" / "r", origin.as_uri(), "main", git.auth_env("u", "t"))
    state.save(root, {"g/r": "x"}, {})
    monkeypatch.setenv("DOCS_DIR", str(root))

    assert "app.py:1:def deploy" in code.search_code("g/r", r"def \w+")
    assert "일치하는 줄이 없다" == code.search_code("g/r", "없는문자열")
    assert "1: def deploy():" in code.read_code("g/r", "app.py")
    assert "app.py" in code.read_code("g/r", "")  # 디렉터리면 목록
    assert code.read_code("g/r", "../../etc/passwd").startswith("없는 경로다")
    assert code.search_code("g/other", "x").startswith("없는 리포다")
