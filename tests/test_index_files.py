import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from index import md_files, read_md  # noqa: E402


def test_md_files_skips_git_symlink_and_macos_meta(tmp_path):
    (tmp_path / "g/r/.git").mkdir(parents=True)
    (tmp_path / "g/r/.git/x.md").write_text("x")
    (tmp_path / "g/r/README.MD").write_text("# a")
    (tmp_path / "g/r/._README.md").write_text("meta")
    os.symlink("/etc/hostname", tmp_path / "g/r/link.md")
    assert [p.relative_to(tmp_path).as_posix() for p in md_files(tmp_path)] == ["g/r/README.MD"]


def test_read_md_strips_bom(tmp_path):
    f = tmp_path / "a.md"
    f.write_bytes(b"\xef\xbb\xbf# t\n")
    assert read_md(f) == "# t\n"
