"""Tests for models."""

import pytest

from conventional_release.models import (
    BreakingChange,
    CommitType,
    ConventionalCommit,
    ReleaseConfig,
    ReleaseNotes,
    Version,
)


class TestCommitType:
    """Tests for CommitType enum."""

    def test_all_types_defined(self):
        expected = {
            "feat",
            "fix",
            "breaking",
            "docs",
            "style",
            "refactor",
            "perf",
            "test",
            "chore",
            "ci",
            "build",
            "revert",
        }
        actual = {t.value for t in CommitType}
        assert actual == expected

    def test_release_section_mapping(self):
        assert CommitType.FEAT.release_section() == "Features"
        assert CommitType.FIX.release_section() == "Bug Fixes"
        assert CommitType.BREAKING.release_section() == "Breaking Changes"
        assert CommitType.DOCS.release_section() == "Documentation"
        assert CommitType.CHORE.release_section() == "Chores"

    def test_is_feature_fix_breaking(self):
        assert CommitType.FEAT.is_feature()
        assert CommitType.FIX.is_fix()
        assert CommitType.BREAKING.is_breaking_type()
        assert not CommitType.DOCS.is_feature()
        assert not CommitType.FEAT.is_fix()


class TestBreakingChange:
    """Tests for BreakingChange model."""

    def test_creation(self):
        bc = BreakingChange(description="API changed", commit_hash="abc123", scope="api")
        assert bc.description == "API changed"
        assert bc.commit_hash == "abc123"
        assert bc.scope == "api"

    def test_defaults(self):
        bc = BreakingChange(description="API changed")
        assert bc.commit_hash is None
        assert bc.scope is None


class TestConventionalCommit:
    """Tests for ConventionalCommit model."""

    def make_commit(self, **kwargs) -> ConventionalCommit:
        defaults = {
            "type": CommitType.FEAT,
            "scope": "test",
            "description": "test commit",
            "body": "",
            "footer": {},
            "hash": "abc123",
            "author": "Test",
            "email": "test@example.com",
            "date": "2024-01-01T00:00:00Z",
        }
        defaults.update(kwargs)
        return ConventionalCommit(**defaults)

    def test_is_breaking_false_by_default(self):
        commit = self.make_commit(type=CommitType.FEAT)
        assert commit.is_breaking is False

    def test_is_breaking_with_exclamation_in_raw(self):
        commit = self.make_commit(
            type=CommitType.FEAT,
            raw_message="feat(api)!: breaking change",
        )
        assert commit.is_breaking is True

    def test_is_breaking_with_footer(self):
        commit = self.make_commit(
            type=CommitType.FIX,
            footer={"BREAKING CHANGE": "Removed API"},
        )
        assert commit.is_breaking is True

    def test_breaking_changes_property(self):
        commit = self.make_commit(
            type=CommitType.FIX,
            footer={"BREAKING CHANGE": "Removed endpoint"},
            hash="def456",
            scope="api",
        )
        changes = commit.breaking_changes
        assert len(changes) == 1
        assert changes[0].description == "Removed endpoint"
        assert changes[0].commit_hash == "def456"
        assert changes[0].scope == "api"

    def test_short_hash(self):
        commit = self.make_commit(hash="abcdef1234567890")
        assert commit.short_hash() == "abcdef1"
        assert commit.short_hash(10) == "abcdef1234"

    def test_sorting_by_date(self):
        c1 = self.make_commit(date="2024-01-01T00:00:00Z")
        c2 = self.make_commit(date="2024-01-02T00:00:00Z")
        # Newer dates are "less than" older dates (sort descending)
        assert c2 < c1


class TestVersion:
    """Tests for Version model."""

    def test_str_representation(self):
        v = Version(1, 2, 3)
        assert str(v) == "1.2.3"

    def test_str_with_prerelease(self):
        v = Version(1, 2, 3, prerelease="alpha.1")
        assert str(v) == "1.2.3-alpha.1"

    def test_str_with_build(self):
        v = Version(1, 2, 3, build="build.123")
        assert str(v) == "1.2.3+build.123"

    def test_bump_major(self):
        v = Version(1, 2, 3)
        assert str(v.bump_major()) == "2.0.0"

    def test_bump_minor(self):
        v = Version(1, 2, 3)
        assert str(v.bump_minor()) == "1.3.0"

    def test_bump_patch(self):
        v = Version(1, 2, 3)
        assert str(v.bump_patch()) == "1.2.4"

    def test_parse(self):
        v = Version.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_parse_with_prerelease(self):
        v = Version.parse("1.2.3-alpha.1")
        assert v.prerelease == "alpha.1"

    def test_parse_with_build(self):
        v = Version.parse("1.2.3+build.123")
        assert v.build == "build.123"

    def test_comparison(self):
        v1 = Version(1, 0, 0)
        v2 = Version(1, 1, 0)
        v3 = Version(1, 1, 1)
        v4 = Version(2, 0, 0)

        assert v1 < v2 < v3 < v4
        assert v4 > v3 > v2 > v1
        assert v1 <= v1
        assert v2 >= v2

    def test_prerelease_comparison(self):
        v_release = Version(1, 0, 0)
        v_pre = Version(1, 0, 0, prerelease="alpha.1")
        assert v_pre < v_release


class TestReleaseConfig:
    """Tests for ReleaseConfig model."""

    def test_defaults(self):
        config = ReleaseConfig()
        assert config.repo_path == "."
        assert config.tag_prefix == "v"
        assert config.changelog_path == "CHANGELOG.md"
        assert config.release_name_template == "Release {version}"
        assert config.draft is False
        assert config.prerelease is False
        assert config.target_commitish == "main"

    def test_custom_values(self):
        config = ReleaseConfig(
            tag_prefix="release/",
            changelog_path="CHANGES.md",
            release_name_template="v{version}",
            draft=True,
        )
        assert config.tag_prefix == "release/"
        assert config.changelog_path == "CHANGES.md"
        assert config.release_name_template == "v{version}"
        assert config.draft is True


class TestReleaseNotes:
    """Tests for ReleaseNotes model."""

    def make_commit(
        self, type: CommitType, scope: str | None = None, desc: str = "test"
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

    def test_to_markdown_basic(self):
        commits = [
            self.make_commit(CommitType.FEAT, "cli", "add command"),
            self.make_commit(CommitType.FIX, "parser", "fix bug"),
        ]
        notes = ReleaseNotes(
            version="1.0.0",
            date="2024-01-15",
            commits=commits,
            breaking_changes=[],
            features=[commits[0]],
            fixes=[commits[1]],
            others={},
        )
        md = notes.to_markdown()
        assert "## 1.0.0 (2024-01-15)" in md
        assert "### Features" in md
        assert "### Bug Fixes" in md
        assert "add command" in md
        assert "fix bug" in md

    def test_to_markdown_with_breaking(self):
        bc = BreakingChange(description="API changed", scope="api")
        commits = [
            self.make_commit(CommitType.FEAT, "api", "new endpoint"),
        ]
        notes = ReleaseNotes(
            version="2.0.0",
            date="2024-01-15",
            commits=commits,
            breaking_changes=[bc],
            features=commits,
            fixes=[],
            others={},
        )
        md = notes.to_markdown()
        assert "### Breaking Changes" in md
        assert "API changed" in md

    def test_to_markdown_other_types(self):
        commits = [
            self.make_commit(CommitType.DOCS, None, "update readme"),
            self.make_commit(CommitType.REFACTOR, "core", "cleanup"),
        ]
        notes = ReleaseNotes(
            version="1.0.1",
            date="2024-01-15",
            commits=commits,
            breaking_changes=[],
            features=[],
            fixes=[],
            others={
                CommitType.DOCS: [commits[0]],
                CommitType.REFACTOR: [commits[1]],
            },
        )
        md = notes.to_markdown()
        assert "### Documentation" in md
        assert "### Refactoring" in md
