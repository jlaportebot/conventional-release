"""Release notes generator."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from conventional_release.models import (
    CommitType,
    ConventionalCommit,
    ReleaseConfig,
    ReleaseNotes,
    Version,
)
from conventional_release.parser import get_commits_since_last_release, get_latest_tag


def determine_version_bump(commits: list[ConventionalCommit], current_version: Version) -> Version:
    """
    Determine the next version based on commits.

    Args:
        commits: List of commits since last release
        current_version: Current version

    Returns:
        Next version
    """
    has_breaking = any(c.is_breaking for c in commits)
    has_features = any(c.type == CommitType.FEAT for c in commits)
    has_fixes = any(c.type == CommitType.FIX for c in commits)

    if has_breaking:
        return current_version.bump_major()
    if has_features:
        return current_version.bump_minor()
    if has_fixes:
        return current_version.bump_patch()
    # Only chore/docs/style/etc - patch bump
    return current_version.bump_patch()


def generate_release_notes(
    commits: list[ConventionalCommit],
    version: str | Version,
    config: ReleaseConfig | None = None,
) -> ReleaseNotes:
    """
    Generate release notes from commits.

    Args:
        commits: List of commits to include
        version: Version string or Version object
        config: Release configuration

    Returns:
        ReleaseNotes object
    """
    if config is None:
        config = ReleaseConfig()

    if isinstance(version, str):
        version_obj = Version.parse(version)
    else:
        version_obj = version

    version_str = str(version_obj)
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")

    # Categorize commits
    breaking_changes: list[Any] = []
    features: list[ConventionalCommit] = []
    fixes: list[ConventionalCommit] = []
    others: dict[CommitType, list[ConventionalCommit]] = defaultdict(list)

    for commit in commits:
        if commit.is_breaking:
            breaking_changes.extend(commit.breaking_changes)

        if commit.type == CommitType.FEAT:
            features.append(commit)
        elif commit.type == CommitType.FIX:
            fixes.append(commit)
        elif commit.type != CommitType.REVERT:
            others[commit.type].append(commit)

    # Sort commits by date (newest first)
    features.sort()
    fixes.sort()
    for commit_list in others.values():
        commit_list.sort()

    return ReleaseNotes(
        version=version_str,
        date=date_str,
        commits=commits,
        breaking_changes=breaking_changes,
        features=features,
        fixes=fixes,
        others=dict(others),
    )


def get_current_version(
    repo_path: str = ".", version_file: str | None = None, tag_prefix: str = "v"
) -> Version:
    """Get current version from tag or version file."""
    # Try version file first
    if version_file:
        version_path = Path(version_file)

        if version_path.exists():
            with version_path.open() as f:
                content = f.read().strip()
                if content:
                    return Version.parse(content)

    # Try git tag
    latest_tag = get_latest_tag(repo_path, tag_prefix)
    if latest_tag:
        # Strip prefix
        version_str = latest_tag
        version_str = version_str.removeprefix(tag_prefix)
        return Version.parse(version_str)

    # Default to 0.1.0
    return Version(0, 1, 0)


def prepare_release(
    repo_path: str = ".",
    config: ReleaseConfig | None = None,
) -> tuple[Version, ReleaseNotes]:
    """
    Prepare a release by analyzing commits since last tag.

    Args:
        repo_path: Path to git repository
        config: Release configuration

    Returns:
        Tuple of (new_version, release_notes)
    """
    if config is None:
        config = ReleaseConfig(repo_path=repo_path)

    # Get current version
    current_version = get_current_version(
        repo_path,
        config.version_file,
        config.tag_prefix,
    )

    # Get commits since last release
    commits = get_commits_since_last_release(repo_path, config.tag_prefix)

    # Determine next version
    new_version = determine_version_bump(commits, current_version)

    # Generate release notes
    release_notes = generate_release_notes(commits, new_version, config)

    return new_version, release_notes


def update_changelog(
    release_notes: ReleaseNotes,
    changelog_path: str = "CHANGELOG.md",
) -> str:
    """
    Update changelog file with new release notes.

    Args:
        release_notes: Release notes to add
        changelog_path: Path to changelog file

    Returns:
        Updated changelog content
    """
    changelog_file = Path(changelog_path)
    new_entry = release_notes.to_markdown()

    if changelog_file.exists():
        with changelog_file.open() as f:
            existing = f.read()

        # Insert after first heading
        lines = existing.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("# "):
                insert_idx = i + 1
                break

        lines.insert(insert_idx, "\n" + new_entry)
        updated = "\n".join(lines)
    else:
        updated = f"# Changelog\n\n{new_entry}"

    with changelog_file.open("w") as f:
        f.write(updated)

    return updated


def update_version_file(
    version: Version,
    version_file: str,
) -> None:
    """Update version file with new version."""
    version_path = Path(version_file)
    with version_path.open("w") as f:
        f.write(str(version))
