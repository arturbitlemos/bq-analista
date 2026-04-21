from pathlib import Path

import pytest

from mcp_core.sandbox import PathSandboxError, exec_analysis_path, exec_library_path


def test_analysis_path_is_under_exec_dir(tmp_path: Path) -> None:
    p = exec_analysis_path(repo_root=tmp_path, exec_email="fulano@x.com", filename="foo.html")
    expected = tmp_path / "analyses" / "fulano@x.com" / "foo.html"
    assert p == expected


def test_rejects_traversal(tmp_path: Path) -> None:
    for bad in ["../foo.html", "foo/../../bar.html", "/etc/passwd"]:
        with pytest.raises(PathSandboxError):
            exec_analysis_path(repo_root=tmp_path, exec_email="fulano@x.com", filename=bad)


def test_rejects_non_html(tmp_path: Path) -> None:
    with pytest.raises(PathSandboxError):
        exec_analysis_path(repo_root=tmp_path, exec_email="fulano@x.com", filename="foo.sh")


def test_library_path(tmp_path: Path) -> None:
    p = exec_library_path(repo_root=tmp_path, exec_email="fulano@x.com")
    assert p == tmp_path / "library" / "fulano@x.com.json"


def test_library_rejects_weird_email(tmp_path: Path) -> None:
    for bad in ["../x", "x/y", "x\n"]:
        with pytest.raises(PathSandboxError):
            exec_library_path(repo_root=tmp_path, exec_email=bad)
