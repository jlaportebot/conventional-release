"""Tests for changelog module."""

import pytest

from conventional_release.changelog import (
    generate_changelog_from_git,
    get_unreleased_section,
    prepend_release_notes,
    read_changelog,
    validate_changelog,
    write_changelog,
)
from conventional_release.models import (
    BreakingChange,
    CommitType,
    ConventionalCommit,
    ReleaseNotes,
    Version,
)


def make_commit(
    type: CommitType, scope: str | None = None, desc: str = "test"
) -> ConventionalCommit:
    return ConventionalCommit(
        type=type,
        scope=scope,
        description=desc,
        body="",
        footer={},
        hash="abc123",
        author="Test",
        email="test@example.com",
        date="2024-01-01T00:00:00Z",
    )


class TestReadWriteChangelog:
    """Tests for read_changelog and write_changelog."""

    def test_read_nonexistent(self, tmp_path):
        """Test reading non-existent changelog."""
        changelog_path = tmp_path / "CHANGELOG.md"
        assert read_changelog(str(changelog_path)) == ""

    def test_read_existing(self, tmp_path):
        """Test reading existing changelog."""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = "# Changelog\n\n## 1.0.0\n\n- feature"
        changelog_path.write_text(content)
        assert read_changelog(str(changelog_path)) == content

    def test_write_changelog(self, tmp_path):
        """Test writing changelog."""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = "# Changelog\n\n## 1.0.0\n\n- feature"
        write_changelog(content, str(changelog_path))
        assert changelog_path.read_text() == content


class TestPrependReleaseNotes:
    """Tests for prepend_release_notes."""

    def test_create_new_changelog(self, tmp_path):
        """Test creating a new changelog with release notes."""
        changelog_path = tmp_path / "CHANGELOG.md"
        notes = ReleaseNotes(
            version="1.0.0",
            date="2024-01-15",
            commits=[],
            breaking_changes=[],
            features=[],
            fixes=[],
            others={},
        )
        content = prepend_release_notes(notes, str(changelog_path))
        assert "# Changelog" in content
        assert "## 1.0.0 (2024-01-15)" in content

    def test_prepend_to_existing(self, tmp_path):
        """Test prepending to existing changelog."""
        changelog_path = tmp_path / "CHANGELOG.md"
        existing = "# Changelog\n\n## 0.1.0 (2024-01-01)\n\n### Features\n- initial"
        changelog_path.write_text(existing)

        notes = ReleaseNotes(
            version="1.0.0",
            date="2024-01-15",
            commits=[],
            breaking_changes=[],
            features=[make_commit(CommitType.FEAT, "cli", "add command")],
            fixes=[],
            others={},
        )
        content = prepend_release_notes(notes, str(changelog_path))
        lines = content.split("\n")
        assert lines[0] == "# Changelog"
        assert "## 1.0.0 (2024-01-15)" in content
        assert "## 0.1.0 (2024-01-01)" in content
        assert "add command" in content

    def test_prepend_with_breaking_changes(self, tmp_path):
        """Test prepending with breaking changes."""
        changelog_path = tmp_path / "CHANGELOG.md"
        existing = "# Changelog\n\n## 0.1.0 (2024-01-01)"
        changelog_path.write_text(existing)

        bc = BreakingChange(description="API removed", scope="api")
        notes = ReleaseNotes(
            version="2.0.0",
            date="2024-01-15",
            commits=[],
            breaking_changes=[bc],
            features=[],
            fixes=[],
            others={},
        )
        content = prepend_release_notes(notes, str(changelog_path))
        assert "### Breaking Changes" in content
        assert "API removed" in content


class TestGetUnreleasedSection:
    """Tests for get_unreleased_section."""

    def test_no_unreleased(self, tmp_path):
        """Test when no unreleased section exists."""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = "# Changelog\n\n## 1.0.0\n\n- feature"
        changelog_path.write_text(content)
        assert get_unreleased_section(str(changelog_path)) is None

    def test_with_unreleased_brackets(self, tmp_path):
        """Test with [Unreleased] section."""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = "# Changelog\n\n## [Unreleased]\n\n### Features\n- new feature\n\n## 1.0.0\n\n- old feature"
        changelog_path.write_text(content)
        result = get_unreleased_section(str(changelog_path))
        assert result is not None
        assert "new feature" in result

    def test_with_unreleased_no_brackets(self, tmp_path):
        """Test with Unreleased section (no brackets)."""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = "# Changelog\n\n## Unreleased\n\n### Features\n- new feature\n\n## 1.0.0\n\n- old feature"
        changelog_path.write_text(content)
        result = get_unreleased_section(str(changelog_path))
        assert result is not None
        assert "new feature" in result


class TestValidateChangelog:
    """Tests for validate_changelog."""

    def test_empty_changelog(self, tmp_path):
        """Test empty changelog validation."""
        changelog_path = tmp_path / "CHANGELOG.md"
        issues = validate_changelog(str(changelog_path))
        assert "Changelog is empty" in issues

    def test_missing_header(self, tmp_path):
        """Test missing header validation."""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = "## 1.0.0\n\n- feature"
        changelog_path.write_text(content)
        issues = validate_changelog(str(changelog_path))
        assert any("should start with" in issue for issue in issues)

    def test_no_version_sections(self, tmp_path):
        """Test no version sections validation."""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = "# Changelog\n\nNo versions here"
        changelog_path.write_text(content)
        issues = validate_changelog(str(changelog_path))
        assert any("No version sections" in issue for issue in issues)

    def test_duplicate_versions(self, tmp_path):
        """Test duplicate version detection."""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = "# Changelog\n\n## 1.0.0\n\n- feature\n\n## 1.0.0\n\n- another"
        changelog_path.write_text(content)
        issues = validate_changelog(str(changelog_path))
        assert any("Duplicate version" in issue for issue in issues)

    def test_valid_changelog(self, tmp_path):
        """Test valid changelog passes validation."""
        changelog_path = tmp_path / "CHANGELOG.md"
        content = "# Changelog\n\n## 1.0.0\n\n- feature\n\n## 0.9.0\n\n- initial"
        changelog_path.write_text(content)
        issues = validate_changelog(str(changelog_path))
        assert len(issues) == 0


class TestGenerateChangelogFromGit:
    """Tests for generate_changelog_from_git."""

    def test_generate_basic(self, tmp_path):
        """Test generating changelog from git history."""
        import subprocess

        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True
        )

        (repo_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: initial feature"], cwd=repo_path, capture_output=True
        )
        subprocess.run(["git", "tag", "v1.0.0"], cwd=repo_path, capture_output=True)

        (repo_path / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "fix: bug fix"], cwd=repo_path, capture_output=True)

        changelog = generate_changelog_from_git(str(repo_path))
        assert "# Changelog" in changelog
        assert "1.0.0" in changelog or "0.1.0" in changelog

    def test_generate_no_tags(self, tmp_path):
        """Test generating changelog with no tags."""
        import subprocess

        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True
        )

        (repo_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: initial feature"], cwd=repo_path, capture_output=True
        )

        changelog = generate_changelog_from_git(str(repo_path))
        assert "# Changelog" in changelog
