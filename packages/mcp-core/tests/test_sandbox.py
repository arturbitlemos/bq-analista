import pytest
from pathlib import Path
from mcp_core.sandbox import exec_analysis_path, exec_library_path, PathSandboxError


def test_analysis_path_includes_domain(tmp_path):
    path = exec_analysis_path(tmp_path, "vendas-linx", "user@soma.com.br", "report.html")
    assert path == tmp_path / "analyses" / "vendas-linx" / "user@soma.com.br" / "report.html"


def test_library_path_includes_domain(tmp_path):
    path = exec_library_path(tmp_path, "vendas-linx", "user@soma.com.br")
    assert path == tmp_path / "library" / "vendas-linx" / "user@soma.com.br.json"


def test_analysis_path_blocks_path_traversal(tmp_path):
    with pytest.raises(PathSandboxError):
        exec_analysis_path(tmp_path, "vendas-linx", "user@soma.com.br", "../escape.html")


def test_analysis_path_blocks_subdirectory_in_filename(tmp_path):
    with pytest.raises(PathSandboxError):
        exec_analysis_path(tmp_path, "vendas-linx", "user@soma.com.br", "sub/file.html")


def test_invalid_email_rejected(tmp_path):
    with pytest.raises(PathSandboxError):
        exec_analysis_path(tmp_path, "vendas-linx", "not-an-email", "file.html")


def test_invalid_domain_rejected(tmp_path):
    with pytest.raises(PathSandboxError):
        exec_analysis_path(tmp_path, "Domain With Spaces", "user@soma.com.br", "file.html")


def test_non_html_rejected(tmp_path):
    with pytest.raises(PathSandboxError):
        exec_analysis_path(tmp_path, "vendas-linx", "user@soma.com.br", "file.csv")
