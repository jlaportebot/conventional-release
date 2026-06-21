"""GitHub integration for creating releases."""

from __future__ import annotations

import os
from typing import Any

from githubkit import GitHub
from githubkit_schemas.latest.models import ReposOwnerRepoReleasesPostBody as CreateReleaseRequest

from conventional_release.models import ReleaseConfig, ReleaseNotes, Version


class GitHubReleaseError(Exception):
    """Error during GitHub release creation."""
def create_github_client(token: str | None = None) -> GitHub:
    """Create GitHub API client."""
    if token is None:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            msg = "GITHUB_TOKEN environment variable not set"
            raise GitHubReleaseError(msg)

    return GitHub(token)


def create_github_release(
    owner: str,
    repo: str,
    release_notes: ReleaseNotes,
    config: ReleaseConfig | None = None,
    client: GitHub | None = None,
) -> dict[str, Any]:
    """
    Create a GitHub release.

    Args:
        owner: Repository owner
        repo: Repository name
        release_notes: Release notes to publish
        config: Release configuration
        client: Optional GitHub client (will create if not provided)

    Returns:
        Release data from GitHub API
    """
    if config is None:
        config = ReleaseConfig()

    if client is None:
        client = create_github_client(config.github_token)

    tag_name = f"{config.tag_prefix}{release_notes.version}"
    release_name = config.release_name_template.format(version=release_notes.version)
    body = release_notes.to_markdown()

    request = CreateReleaseRequest(
        tag_name=tag_name,
        name=release_name,
        body=body,
        draft=config.draft,
        prerelease=config.prerelease,
        target_commitish=config.target_commitish,
        generate_release_notes=False,
    )

    response = client.rest.repos.async_create_release(
        owner=owner,
        repo=repo,
        data=request,
    )

    return response.parsed_data


async def create_github_release_async(
    owner: str,
    repo: str,
    release_notes: ReleaseNotes,
    config: ReleaseConfig | None = None,
    client: GitHub | None = None,
) -> dict[str, Any]:
    """Async version of create_github_release."""
    if config is None:
        config = ReleaseConfig()

    if client is None:
        client = create_github_client(config.github_token)

    tag_name = f"{config.tag_prefix}{release_notes.version}"
    release_name = config.release_name_template.format(version=release_notes.version)
    body = release_notes.to_markdown()

    request = CreateReleaseRequest(
        tag_name=tag_name,
        name=release_name,
        body=body,
        draft=config.draft,
        prerelease=config.prerelease,
        target_commitish=config.target_commitish,
        generate_release_notes=False,
    )

    response = await client.rest.repos.async_create_release(
        owner=owner,
        repo=repo,
        data=request,
    )

    return response.parsed_data


async def create_or_update_tag(
    owner: str,
    repo: str,
    version: Version,
    config: ReleaseConfig | None = None,
    client: GitHub | None = None,
) -> dict[str, Any]:
    """Create or update a git tag for the release."""
    if config is None:
        config = ReleaseConfig()

    if client is None:
        client = create_github_client(config.github_token)

    tag_name = f"{config.tag_prefix}{version}"
    sha = config.target_commitish or "main"

    # Create tag
    tag_data = {
        "tag": tag_name,
        "message": f"Release {tag_name}",
        "object": sha,
        "type": "commit",
        "tagger": {
            "name": config.tagger_name or "conventional-release",
            "email": config.tagger_email or "noreply@example.com",
            "date": None,  # Will use current time
        },
    }

    # This uses the Git API to create a tag object
    response = await client.rest.git.async_create_tag(
        owner=owner,
        repo=repo,
        data=tag_data,
    )

    return response.parsed_data


def get_repo_info_from_remote(repo_path: str = ".") -> tuple[str, str] | None:
    """Extract owner/repo from git remote URL."""
    from git import Repo

    try:
        repo = Repo(repo_path)
        origin = repo.remotes.origin
        url = origin.url

        # Handle SSH: git@github.com:owner/repo.git
        # Handle HTTPS: https://github.com/owner/repo.git
        if url.startswith("git@"):
            parts = url.split(":")[-1].replace(".git", "").split("/")
        elif url.startswith("https://"):
            parts = url.replace(".git", "").split("/")[-2:]
        else:
            return None

        if len(parts) == 2:
            return parts[0], parts[1]
    except (AttributeError, ValueError, IndexError):
        pass

    return None

