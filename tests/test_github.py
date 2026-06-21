"""Tests for GitHub integration."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from conventional_release.github import (
    GitHubReleaseError,
    create_github_client,
    create_github_release,
    create_github_release_async,
    create_or_update_tag,
    get_repo_info_from_remote,
)
from conventional_release.models import (
    BreakingChange,
    CommitType,
    ConventionalCommit,
    ReleaseConfig,
    ReleaseNotes,
    Version,
)


def make_release_notes() -> ReleaseNotes:
    """Create a test ReleaseNotes object."""
    commits = [
        ConventionalCommit(
            type=CommitType.FEAT,
            scope="cli",
            description="add command",
            body="",
            footer={},
            hash="abc123",
            author="Test",
            email="test@example.com",
            date="2024-01-01T00:00:00Z",
        )
    ]
    return ReleaseNotes(
        version="1.0.0",
        date="2024-01-15",
        commits=commits,
        breaking_changes=[],
        features=commits,
        fixes=[],
        others={},
    )


class TestCreateGithubClient:
    """Tests for create_github_client."""

    def test_with_token_param(self):
        """Test creating client with explicit token."""
        with patch("conventional_release.github.GitHub") as mock_github:
            create_github_client("test-token")
            mock_github.assert_called_once_with("test-token")

    def test_with_env_var(self):
        """Test creating client with GITHUB_TOKEN env var."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}):
            with patch("conventional_release.github.GitHub") as mock_github:
                create_github_client(None)
                mock_github.assert_called_once_with("env-token")

    def test_without_token_raises(self):
        """Test error when no token available."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(GitHubReleaseError, match="GITHUB_TOKEN"):
                create_github_client(None)


class TestCreateGithubRelease:
    """Tests for create_github_release."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock GitHub client."""
        client = Mock()
        # The actual method is async_create_release (async)
        mock_response = Mock()
        mock_response.parsed_data = {
            "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0"
        }
        client.rest.repos.async_create_release = AsyncMock(return_value=mock_response)
        return client

    @pytest.fixture
    def release_notes(self):
        """Create test release notes."""
        return make_release_notes()

    @pytest.fixture
    def config(self):
        """Create test config."""
        return ReleaseConfig(
            tag_prefix="v",
            release_name_template="Release {version}",
            draft=False,
            prerelease=False,
            target_commitish="main",
        )

    @pytest.mark.asyncio
    async def test_create_release_basic(self, mock_client, release_notes, config):
        """Test creating a basic release."""
        # The function is async internally but called sync
        # We need to test the async version or run the sync wrapper
        from conventional_release.github import create_github_release_async

        result = await create_github_release_async(
            "owner", "repo", release_notes, config, mock_client
        )

        assert result["html_url"] == "https://github.com/owner/repo/releases/tag/v1.0.0"
        mock_client.rest.repos.async_create_release.assert_called_once()

        # Check the call arguments
        call_args = mock_client.rest.repos.async_create_release.call_args
        assert call_args.kwargs["owner"] == "owner"
        assert call_args.kwargs["repo"] == "repo"
        data = call_args.kwargs["data"]
        assert data.tag_name == "v1.0.0"
        assert data.name == "Release 1.0.0"
        assert data.draft is False
        assert data.prerelease is False

    @pytest.mark.asyncio
    async def test_create_release_with_custom_config(self, mock_client, release_notes):
        """Test release creation with custom config."""
        config = ReleaseConfig(
            tag_prefix="release/",
            release_name_template="v{version}",
            draft=True,
            prerelease=True,
            target_commitish="develop",
        )
        from conventional_release.github import create_github_release_async

        await create_github_release_async("owner", "repo", release_notes, config, mock_client)

        call_args = mock_client.rest.repos.async_create_release.call_args
        data = call_args.kwargs["data"]
        assert data.tag_name == "release/1.0.0"
        assert data.name == "v1.0.0"
        assert data.draft is True
        assert data.prerelease is True
        assert data.target_commitish == "develop"


class TestCreateGithubReleaseAsync:
    """Tests for create_github_release_async."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock async GitHub client."""
        client = Mock()
        mock_response = Mock()
        mock_response.parsed_data = {
            "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0"
        }
        client.rest.repos.async_create_release = AsyncMock(return_value=mock_response)
        return client

    @pytest.fixture
    def release_notes(self):
        """Create test release notes."""
        return make_release_notes()

    @pytest.fixture
    def config(self):
        """Create test config."""
        return ReleaseConfig()

    @pytest.mark.asyncio
    async def test_create_release_async(self, mock_client, release_notes, config):
        """Test async release creation."""
        result = await create_github_release_async(
            "owner", "repo", release_notes, config, mock_client
        )

        assert result["html_url"] == "https://github.com/owner/repo/releases/tag/v1.0.0"
        mock_client.rest.repos.async_create_release.assert_called_once()


class TestCreateOrUpdateTag:
    """Tests for create_or_update_tag."""

    @pytest.mark.asyncio
    async def test_create_tag(self):
        """Test creating a tag."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.parsed_data = {"sha": "abc123"}
        mock_client.rest.git.async_create_tag = AsyncMock(return_value=mock_response)

        config = ReleaseConfig(
            tag_prefix="v",
            target_commitish="main",
            tagger_name="Test Bot",
            tagger_email="bot@example.com",
        )

        await create_or_update_tag("owner", "repo", Version(1, 0, 0), config, mock_client)

        mock_client.rest.git.async_create_tag.assert_called_once()
        call_args = mock_client.rest.git.async_create_tag.call_args
        assert call_args.kwargs["owner"] == "owner"
        assert call_args.kwargs["repo"] == "repo"
        data = call_args.kwargs["data"]
        assert data.tag == "v1.0.0"
        assert data.message == "Release v1.0.0"
        assert data.object_ == "main"
        assert data.type == "commit"
        assert data.tagger.name == "Test Bot"
        assert data.tagger.email == "bot@example.com"


class TestGetRepoInfoFromRemote:
    """Tests for get_repo_info_from_remote."""

    def test_ssh_url(self, tmp_path):
        """Test parsing SSH remote URL."""
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
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:owner/repo.git"],
            cwd=repo_path,
            capture_output=True,
        )

        result = get_repo_info_from_remote(str(repo_path))
        assert result == ("owner", "repo")

    def test_https_url(self, tmp_path):
        """Test parsing HTTPS remote URL."""
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
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/owner/repo.git"],
            cwd=repo_path,
            capture_output=True,
        )

        result = get_repo_info_from_remote(str(repo_path))
        assert result == ("owner", "repo")

    def test_no_remote(self, tmp_path):
        """Test with no remote configured."""
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
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_path, capture_output=True)

        result = get_repo_info_from_remote(str(repo_path))
        assert result is None

    def test_invalid_url(self, tmp_path):
        """Test with invalid remote URL."""
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
        subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "invalid-url"], cwd=repo_path, capture_output=True
        )

        result = get_repo_info_from_remote(str(repo_path))
        assert result is None
