"""Tests for generator."""

import pytest

from conventional_release.generator import (
    determine_version_bump,
    generate_release_notes,
    get_current_version,
    prepare_release,
    update_changelog,
    update_version_file,
)
from conventional_release.models import (
    CommitType,
    ConventionalCommit,
    ReleaseConfig,
    ReleaseNotes,
    Version,
)


def make_commit(
    type: CommitType, scope: str | None = None, desc: str = "test", breaking: bool = False
) -> ConventionalCommit:
    """Helper to create a test commit."""
    footer = {"BREAKING CHANGE": "breaking"} if breaking else {}
    return ConventionalCommit(
        type=type,
        scope=scope,
        description=desc,
        body="",
        footer=footer,
        hash="abc123",
        author="Test",
        email="test@example.com",
        date="2024-01-01T00:00:00Z",
    )


class TestDetermineVersionBump:
    """Tests for determine_version_bump."""

    def test_breaking_bumps_major(self):
        commits = [make_commit(CommitType.FEAT, breaking=True)]
        current = Version(1, 0, 0)
        next_version = determine_version_bump(commits, current)
        assert str(next_version) == "2.0.0"

    def test_features_bumps_minor(self):
        commits = [
            make_commit(CommitType.FEAT),
            make_commit(CommitType.FEAT, "api", "another feature"),
        ]
        current = Version(1, 0, 0)
        next_version = determine_version_bump(commits, current)
        assert str(next_version) == "1.1.0"

    def test_fixes_bumps_patch(self):
        commits = [
            make_commit(CommitType.FIX),
            make_commit(CommitType.FIX, "parser", "another fix"),
        ]
        current = Version(1, 0, 0)
        next_version = determine_version_bump(commits, current)
        assert str(next_version) == "1.0.1"

    def test_only_chore_bumps_patch(self):
        commits = [make_commit(CommitType.CHORE), make_commit(CommitType.DOCS)]
        current = Version(1, 0, 0)
        next_version = determine_version_bump(commits, current)
        assert str(next_version) == "1.0.1"

    def test_mixed_commits_priority_breaking(self):
        commits = [
            make_commit(CommitType.FEAT),
            make_commit(CommitType.FIX),
            make_commit(CommitType.FEAT, breaking=True),
        ]
        current = Version(1, 0, 0)
        next_version = determine_version_bump(commits, current)
        assert str(next_version) == "2.0.0"

    def test_mixed_commits_priority_features(self):
        commits = [
            make_commit(CommitType.FIX),
            make_commit(CommitType.FEAT),
        ]
        current = Version(1, 0, 0)
        next_version = determine_version_bump(commits, current)
        assert str(next_version) == "1.1.0"


class TestGenerateReleaseNotes:
    """Tests for generate_release_notes."""

    def test_basic_generation(self):
        commits = [
            make_commit(CommitType.FEAT, "cli", "add command"),
            make_commit(CommitType.FIX, "parser", "fix bug"),
            make_commit(CommitType.DOCS, None, "update readme"),
        ]
        notes = generate_release_notes(commits, "1.0.0")
        assert notes.version == "1.0.0"
        assert len(notes.features) == 1
        assert len(notes.fixes) == 1
        assert len(notes.others.get(CommitType.DOCS, [])) == 1

    def test_with_breaking_changes(self):
        commits = [
            make_commit(CommitType.FEAT, "api", "new endpoint", breaking=True),
            make_commit(CommitType.FIX, "parser", "fix bug"),
        ]
        notes = generate_release_notes(commits, "2.0.0")
        assert len(notes.breaking_changes) == 1
        assert notes.breaking_changes[0].description == "breaking"

    def test_with_version_object(self):
        commits = [make_commit(CommitType.FEAT, "cli", "add command")]
        notes = generate_release_notes(commits, Version(1, 0, 0))
        assert notes.version == "1.0.0"

    def test_custom_config(self):
        commits = [make_commit(CommitType.FEAT, "cli", "add command")]
        config = ReleaseConfig(tag_prefix="release/")
        notes = generate_release_notes(commits, "1.0.0", config)
        assert notes.version == "1.0.0"


class TestGetCurrentVersion:
    """Tests for get_current_version."""

    def test_default_version(self, tmp_path):
        """Test default version when no tags or version file."""
        # Create a temp git repo
        import subprocess

        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=repo_path, capture_output=True
        )
        # Create initial commit
        (repo_path / "README.md").write_text("# Test")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial commit"], cwd=repo_path, capture_output=True
        )

        version = get_current_version(str(repo_path))
        assert str(version) == "0.1.0"

    def test_from_tag(self, tmp_path):
        """Test version from latest tag."""
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
            ["git", "commit", "-m", "initial commit"], cwd=repo_path, capture_output=True
        )
        subprocess.run(["git", "tag", "v1.2.3"], cwd=repo_path, capture_output=True)

        version = get_current_version(str(repo_path))
        assert str(version) == "1.2.3"

    def test_from_version_file(self, tmp_path):
        """Test version from version file."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("2.5.0")

        version = get_current_version(str(tmp_path), version_file=str(version_file))
        assert str(version) == "2.5.0"


class TestPrepareRelease:
    """Tests for prepare_release."""

    def test_prepare_release_no_commits(self, tmp_path):
        """Test prepare_release with no commits since last tag."""
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
            ["git", "commit", "-m", "initial commit"], cwd=repo_path, capture_output=True
        )
        subprocess.run(["git", "tag", "v1.0.0"], cwd=repo_path, capture_output=True)

        version, notes = prepare_release(str(repo_path))
        assert str(version) == "1.0.1"  # patch bump for no commits
        assert len(notes.commits) == 0


class TestUpdateChangelog:
    """Tests for update_changelog."""

    def test_create_new_changelog(self, tmp_path):
        """Test creating a new changelog."""
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
        content = update_changelog(notes, str(changelog_path))
        assert "# Changelog" in content
        assert "## 1.0.0 (2024-01-15)" in content

    def test_prepend_to_existing_changelog(self, tmp_path):
        """Test prepending to existing changelog."""
        changelog_path = tmp_path / "CHANGELOG.md"
        existing = "# Changelog\n\n## 0.1.0 (2024-01-01)\n\n### Features\n- initial"
        changelog_path.write_text(existing)

        notes = ReleaseNotes(
            version="1.0.0",
            date="2024-01-15",
            commits=[],
            breaking_changes=[],
            features=[],
            fixes=[],
            others={},
        )
        content = update_changelog(notes, str(changelog_path))
        lines = content.split("\n")
        # New version should be after header
        assert lines[0] == "# Changelog"
        assert "## 1.0.0 (2024-01-15)" in content
        assert "## 0.1.0 (2024-01-01)" in content


class TestUpdateVersionFile:
    """Tests for update_version_file."""

    def test_update_version_file(self, tmp_path):
        """Test updating version file."""
        version_file = tmp_path / "VERSION"
        update_version_file(Version(1, 2, 3), str(version_file))
        assert version_file.read_text().strip() == "1.2.3"

    def test_update_with_prerelease(self, tmp_path):
        """Test updating version file with prerelease."""
        version_file = tmp_path / "VERSION"
        update_version_file(Version(1, 0, 0, prerelease="alpha.1"), str(version_file))
        assert version_file.read_text().strip() == "1.0.0-alpha.1"
