"""Tests for the .nsignore file reader."""

from __future__ import annotations

import io
import tarfile

import pytest

from nightshift.nsignore import DEFAULT_EXCLUDE_PATTERNS, read_nsignore, should_exclude


# ── read_nsignore ──────────────────────────────────────────────


class TestReadNsignore:
    def test_returns_defaults_when_no_file(self, tmp_path):
        patterns = read_nsignore(str(tmp_path))
        assert patterns == set(DEFAULT_EXCLUDE_PATTERNS)

    def test_merges_user_patterns_with_defaults(self, tmp_path):
        (tmp_path / ".nsignore").write_text("secrets/\n*.log\n")
        patterns = read_nsignore(str(tmp_path))
        assert "secrets/" in patterns
        assert "*.log" in patterns
        # defaults still present
        assert ".git" in patterns
        assert "__pycache__" in patterns

    def test_ignores_comment_lines(self, tmp_path):
        (tmp_path / ".nsignore").write_text("# this is a comment\nbuild/\n")
        patterns = read_nsignore(str(tmp_path))
        assert "# this is a comment" not in patterns
        assert "build/" in patterns

    def test_ignores_blank_lines(self, tmp_path):
        (tmp_path / ".nsignore").write_text("\n\nbuild/\n\n")
        patterns = read_nsignore(str(tmp_path))
        assert "" not in patterns
        assert "build/" in patterns

    def test_strips_whitespace_from_patterns(self, tmp_path):
        (tmp_path / ".nsignore").write_text("  dist/  \n")
        patterns = read_nsignore(str(tmp_path))
        assert "dist/" in patterns
        assert "  dist/  " not in patterns


# ── should_exclude ─────────────────────────────────────────────


class TestShouldExclude:
    def test_exact_name_match(self):
        patterns = {".git", "node_modules"}
        assert should_exclude(".git", patterns) is True
        assert should_exclude("node_modules", patterns) is True
        assert should_exclude("src", patterns) is False

    def test_wildcard_suffix_match(self):
        patterns = {"*.pyc", "*.log"}
        assert should_exclude("module.pyc", patterns) is True
        assert should_exclude("app.log", patterns) is True
        assert should_exclude("module.py", patterns) is False

    def test_path_component_match(self):
        patterns = {"__pycache__"}
        assert should_exclude("src/__pycache__/mod.pyc", patterns) is True
        assert should_exclude("src/utils.py", patterns) is False

    def test_no_match_returns_false(self):
        patterns = {".git", "*.pyc"}
        assert should_exclude("main.py", patterns) is False
        assert should_exclude("README.md", patterns) is False


# ── integration with _make_archive ────────────────────────────


def _archive_dir(project_dir: str) -> dict[str, str]:
    """Build a tar.gz of *project_dir* using read_nsignore/should_exclude and return its contents."""
    import os

    patterns = read_nsignore(project_dir)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if not should_exclude(d, patterns)]
            for f in files:
                if should_exclude(f, patterns):
                    continue
                full_path = os.path.join(root, f)
                arcname = os.path.relpath(full_path, project_dir)
                tar.add(full_path, arcname=arcname)
    buf.seek(0)
    result: dict[str, str] = {}
    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile():
                fh = tar.extractfile(member)
                if fh:
                    result[member.name] = fh.read().decode()
    return result


class TestNsignoreInDeploy:
    """Verify that .nsignore patterns are honoured during archive creation."""

    def test_nsignore_excludes_custom_dir(self, tmp_path):
        (tmp_path / "main.py").write_text("# entry")
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "bundle.js").write_text("bundle")
        (tmp_path / ".nsignore").write_text("dist\n")

        files = _archive_dir(str(tmp_path))
        assert "main.py" in files
        assert not any("dist" in name for name in files)

    def test_nsignore_excludes_wildcard_files(self, tmp_path):
        (tmp_path / "main.py").write_text("# entry")
        (tmp_path / "output.log").write_text("log data")
        (tmp_path / ".nsignore").write_text("*.log\n")

        files = _archive_dir(str(tmp_path))
        assert "main.py" in files
        assert "output.log" not in files

    def test_defaults_always_excluded_even_without_nsignore(self, tmp_path):
        (tmp_path / "main.py").write_text("# entry")
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "main.cpython-313.pyc").write_text("bytecode")

        files = _archive_dir(str(tmp_path))
        assert "main.py" in files
        assert not any("__pycache__" in name for name in files)

    def test_nsignore_file_itself_not_excluded(self, tmp_path):
        """The .nsignore file should appear in the archive (it's a config file)."""
        (tmp_path / "main.py").write_text("# entry")
        (tmp_path / ".nsignore").write_text("dist\n")

        files = _archive_dir(str(tmp_path))
        assert "main.py" in files
        # .nsignore is not in DEFAULT_PATTERNS so it should be included
        assert ".nsignore" in files
