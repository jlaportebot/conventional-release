"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner

from conventional_release.cli import load_config, main
from conventional_release.models import ReleaseConfig


class TestCLI:
    """Tests for CLI commands."""

    def test_version_option(self):
        """Test --version option."""
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_help(self):
        """Test --help option."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Generate release notes" in result.output

    def test_commits_help(self):
        """Test commits --help."""
        runner = CliRunner()
        result = runner.invoke(main, ["commits", "--help"])
        assert result.exit_code == 0
        assert "List commits" in result.output

    def test_notes_help(self):
        """Test notes --help."""
        runner = CliRunner()
        result = runner.invoke(main, ["notes", "--help"])
        assert result.exit_code == 0
        assert "Generate release notes" in result.output

    def test_release_help(self):
        """Test release --help."""
        runner = CliRunner()
        result = runner.invoke(main, ["release", "--help"])
        assert result.exit_code == 0
        assert "Create a release" in result.output

    def test_version_help(self):
        """Test version --help."""
        runner = CliRunner()
        result = runner.invoke(main, ["version", "--help"])
        assert result.exit_code == 0
        assert "Show current version" in result.output

    def test_validate_help(self):
        """Test validate --help."""
        runner = CliRunner()
        result = runner.invoke(main, ["validate", "--help"])
        assert result.exit_code == 0
        assert "Validate changelog" in result.output

    def test_generate_help(self):
        """Test generate --help."""
        runner = CliRunner()
        result = runner.invoke(main, ["generate", "--help"])
        assert result.exit_code == 0
        assert "Generate full changelog" in result.output


class TestCommitsCommand:
    """Tests for commits command."""

    def test_commits_no_repo(self, tmp_path):
        """Test commits command in non-git directory."""
        runner = CliRunner()
        result = runner.invoke(main, ["-r", str(tmp_path), "commits"])
        # Should fail because not a git repo
        assert result.exit_code != 0

    def test_commits_in_git_repo(self, tmp_path):
        """Test commits command in git repo."""
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
        subprocess.run(["git", "commit", "-m", "feat: initial"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "tag", "v1.0.0"], cwd=repo_path, capture_output=True)
        (repo_path / "file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "fix: bug fix"], cwd=repo_path, capture_output=True)

        runner = CliRunner()
        result = runner.invoke(main, ["-r", str(repo_path), "commits", "--format", "markdown"])
        assert result.exit_code == 0
        assert "fix: bug fix" in result.output or "feat: initial" in result.output


class TestNotesCommand:
    """Tests for notes command."""

    def test_notes_no_commits(self, tmp_path):
        """Test notes with no commits since last tag."""
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

        runner = CliRunner()
        result = runner.invoke(main, ["-r", str(repo_path), "notes", "--dry-run"])
        assert result.exit_code == 0
        assert "No commits since last release" in result.output


class TestVersionCommand:
    """Tests for version command."""

    def test_version_no_tags(self, tmp_path):
        """Test version command with no tags."""
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

        runner = CliRunner()
        result = runner.invoke(main, ["-r", str(repo_path), "version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_version_with_tag(self, tmp_path):
        """Test version command with existing tag."""
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
        subprocess.run(["git", "tag", "v2.3.4"], cwd=repo_path, capture_output=True)

        runner = CliRunner()
        result = runner.invoke(main, ["-r", str(repo_path), "version"])
        assert result.exit_code == 0
        assert "2.3.4" in result.output


class TestValidateCommand:
    """Tests for validate command."""

    def test_validate_missing_changelog(self, tmp_path):
        """Test validate with missing changelog."""
        runner = CliRunner()
        result = runner.invoke(main, ["-r", str(tmp_path), "validate"])
        assert result.exit_code != 0
        assert "Changelog is empty" in result.output

    def test_validate_valid_changelog(self, tmp_path):
        """Test validate with valid changelog."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        changelog_path = repo_path / "CHANGELOG.md"
        content = "# Changelog\n\n## 1.0.0\n\n- feature"
        changelog_path.write_text(content)

        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(repo_path)
            runner = CliRunner()
            result = runner.invoke(main, ["-r", str(repo_path), "validate"])
            assert result.exit_code == 0
            assert "valid" in result.output.lower()
        finally:
            os.chdir(old_cwd)


class TestGenerateCommand:
    """Tests for generate command."""

    def test_generate_basic(self, tmp_path):
        """Test generate command."""
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
        subprocess.run(["git", "commit", "-m", "feat: initial"], cwd=repo_path, capture_output=True)

        runner = CliRunner()
        result = runner.invoke(
            main, ["-r", str(repo_path), "generate", "-o", str(tmp_path / "CHANGELOG.md")]
        )
        assert result.exit_code == 0
        assert "Generated changelog" in result.output
        assert (tmp_path / "CHANGELOG.md").exists()


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_from_yaml(self, tmp_path):
        """Test loading config from YAML file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("""
tag_prefix: "release/"
changelog_path: "CHANGES.md"
release_name_template: "v{version}"
""")

        config = load_config(str(config_path), str(tmp_path))
        assert config.tag_prefix == "release/"
        assert config.changelog_path == "CHANGES.md"
        assert config.release_name_template == "v{version}"

    def test_load_config_nonexistent(self, tmp_path):
        """Test loading non-existent config file."""
        config = load_config(None, str(tmp_path))
        assert isinstance(config, ReleaseConfig)
        assert config.tag_prefix == "v"

    def test_load_config_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML config."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("invalid: yaml: content:")

        config = load_config(str(config_path), str(tmp_path))
        # Should fall back to defaults
        assert config.tag_prefix == "v"
