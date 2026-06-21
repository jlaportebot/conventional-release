"""Tests for conventional commit parsing."""

import pytest

from conventional_release.models import BreakingChange, CommitType, ConventionalCommit
from conventional_release.parser import parse_commit, parse_commits


class TestCommitType:
    """Tests for CommitType enum."""

    def test_commit_types_exist(self):
        assert CommitType.FEAT.value == "feat"
        assert CommitType.FIX.value == "fix"
        assert CommitType.BREAKING.value == "breaking"
        assert CommitType.DOCS.value == "docs"
        assert CommitType.STYLE.value == "style"
        assert CommitType.REFACTOR.value == "refactor"
        assert CommitType.PERF.value == "perf"
        assert CommitType.TEST.value == "test"
        assert CommitType.CHORE.value == "chore"
        assert CommitType.CI.value == "ci"
        assert CommitType.BUILD.value == "build"
        assert CommitType.REVERT.value == "revert"

    def test_from_string_valid(self):
        assert CommitType.from_string("feat") == CommitType.FEAT
        assert CommitType.from_string("fix") == CommitType.FIX
        assert CommitType.from_string("BREAKING CHANGE") == CommitType.BREAKING

    def test_from_string_invalid(self):
        with pytest.raises(ValueError):
            CommitType.from_string("invalid")


class TestBreakingChange:
    """Tests for BreakingChange model."""

    def test_breaking_change_creation(self):
        bc = BreakingChange(description="API changed", commit_hash="abc123")
        assert bc.description == "API changed"
        assert bc.commit_hash == "abc123"

    def test_breaking_change_optional_fields(self):
        bc = BreakingChange(description="API changed")
        assert bc.commit_hash is None
        assert bc.scope is None


class TestConventionalCommit:
    """Tests for ConventionalCommit model."""

    def test_basic_commit(self):
        commit = ConventionalCommit(
            type=CommitType.FEAT,
            scope="cli",
            description="add new command",
            body="",
            footer={},
            hash="abc123",
            author="John Doe",
            email="john@example.com",
            date="2024-01-15T10:00:00Z",
        )
        assert commit.type == CommitType.FEAT
        assert commit.scope == "cli"
        assert commit.description == "add new command"
        assert commit.is_breaking is False

    def test_breaking_commit_with_exclamation(self):
        commit = ConventionalCommit(
            type=CommitType.FEAT,
            scope="api",
            description="change response format",
            body="",
            footer={"BREAKING CHANGE": "Response format changed"},
            hash="abc123",
            author="John Doe",
            email="john@example.com",
            date="2024-01-15T10:00:00Z",
        )
        assert commit.is_breaking is True

    def test_breaking_commit_with_footer(self):
        commit = ConventionalCommit(
            type=CommitType.FIX,
            scope=None,
            description="fix bug",
            body="",
            footer={"BREAKING CHANGE": "Removed deprecated API"},
            hash="abc123",
            author="John Doe",
            email="john@example.com",
            date="2024-01-15T10:00:00Z",
        )
        assert commit.is_breaking is True

    def test_commit_with_scope(self):
        commit = ConventionalCommit(
            type=CommitType.FIX,
            scope="parser",
            description="handle empty scope",
            body="",
            footer={},
            hash="abc123",
            author="John Doe",
            email="john@example.com",
            date="2024-01-15T10:00:00Z",
        )
        assert commit.scope == "parser"

    def test_commit_without_scope(self):
        commit = ConventionalCommit(
            type=CommitType.DOCS,
            scope=None,
            description="update readme",
            body="",
            footer={},
            hash="abc123",
            author="John Doe",
            email="john@example.com",
            date="2024-01-15T10:00:00Z",
        )
        assert commit.scope is None

    def test_commit_with_body(self):
        commit = ConventionalCommit(
            type=CommitType.FEAT,
            scope="core",
            description="add feature",
            body="This adds a new feature\n\nWith multiple paragraphs.",
            footer={},
            hash="abc123",
            author="John Doe",
            email="john@example.com",
            date="2024-01-15T10:00:00Z",
        )
        assert "multiple paragraphs" in commit.body

    def test_commit_with_multiple_footers(self):
        commit = ConventionalCommit(
            type=CommitType.FEAT,
            scope="cli",
            description="add command",
            body="",
            footer={"Closes": "#123", "Co-authored-by": "Jane <jane@example.com>"},
            hash="abc123",
            author="John Doe",
            email="john@example.com",
            date="2024-01-15T10:00:00Z",
        )
        assert commit.footer["Closes"] == "#123"
        assert "Co-authored-by" in commit.footer


class TestParseCommit:
    """Tests for parse_commit function."""

    def test_parse_simple_feat(self):
        message = "feat(cli): add new command"
        commit = parse_commit(
            message, "abc123", "John Doe", "john@example.com", "2024-01-15T10:00:00Z"
        )
        assert commit.type == CommitType.FEAT
        assert commit.scope == "cli"
        assert commit.description == "add new command"

    def test_parse_simple_fix(self):
        message = "fix: resolve memory leak"
        commit = parse_commit(
            message, "abc123", "John Doe", "john@example.com", "2024-01-15T10:00:00Z"
        )
        assert commit.type == CommitType.FIX
        assert commit.scope is None
        assert commit.description == "resolve memory leak"

    def test_parse_breaking_with_exclamation(self):
        message = "feat(api)!: change response format"
        commit = parse_commit(
            message, "abc123", "John Doe", "john@example.com", "2024-01-15T10:00:00Z"
        )
        assert commit.type == CommitType.FEAT
        assert commit.scope == "api"
        assert commit.is_breaking is True

    def test_parse_breaking_with_footer(self):
        message = (
            "fix: remove deprecated endpoint\n\nBREAKING CHANGE: The /v1 endpoint has been removed"
        )
        commit = parse_commit(
            message, "abc123", "John Doe", "john@example.com", "2024-01-15T10:00:00Z"
        )
        assert commit.type == CommitType.FIX
        assert commit.is_breaking is True
        assert "removed" in commit.footer.get("BREAKING CHANGE", "").lower()

    def test_parse_with_body(self):
        message = "feat(core): add new feature\n\nThis is the body\nWith multiple lines"
        commit = parse_commit(
            message, "abc123", "John Doe", "john@example.com", "2024-01-15T10:00:00Z"
        )
        assert commit.type == CommitType.FEAT
        assert commit.scope == "core"
        assert "multiple lines" in commit.body

    def test_parse_with_footers(self):
        message = "fix(parser): handle edge case\n\nCloses: #456\nReviewed-by: Jane"
        commit = parse_commit(
            message, "abc123", "John Doe", "john@example.com", "2024-01-15T10:00:00Z"
        )
        assert commit.type == CommitType.FIX
        assert commit.scope == "parser"
        assert commit.footer.get("Closes") == "#456"
        assert commit.footer.get("Reviewed-by") == "Jane"

    def test_parse_revert_commit(self):
        message = "revert: feat(cli): add command\n\nThis reverts commit abc123."
        commit = parse_commit(
            message, "abc123", "John Doe", "john@example.com", "2024-01-15T10:00:00Z"
        )
        assert commit.type == CommitType.REVERT

    def test_parse_invalid_format(self):
        message = "not a conventional commit"
        commit = parse_commit(
            message, "abc123", "John Doe", "john@example.com", "2024-01-15T10:00:00Z"
        )
        # Should still parse but with type CHORE or similar fallback
        assert commit.type in (CommitType.CHORE, CommitType.FEAT, CommitType.FIX)


class TestParseCommits:
    """Tests for parse_commits function."""

    def test_parse_multiple_commits(self):
        commits_data = [
            (
                "feat(cli): add command",
                "abc123",
                "John",
                "john@example.com",
                "2024-01-15T10:00:00Z",
            ),
            ("fix: resolve bug", "def456", "Jane", "jane@example.com", "2024-01-16T10:00:00Z"),
            ("docs: update readme", "ghi789", "Bob", "bob@example.com", "2024-01-17T10:00:00Z"),
        ]
        commits = parse_commits(commits_data)
        assert len(commits) == 3
        assert commits[0].type == CommitType.FEAT
        assert commits[1].type == CommitType.FIX
        assert commits[2].type == CommitType.DOCS

    def test_parse_empty_list(self):
        commits = parse_commits([])
        assert commits == []
