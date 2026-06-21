"""Changelog management."""

from __future__ import annotations

import re
from pathlib import Path

from conventional_release.models import ReleaseNotes, Version


def read_changelog(changelog_path: str = "CHANGELOG.md") -> str:
    """Read changelog file."""
    path = Path(changelog_path)
    if path.exists():
        return path.read_text()
    return ""


def write_changelog(content: str, changelog_path: str = "CHANGELOG.md") -> None:
    """Write changelog file."""
    path = Path(changelog_path)
    path.write_text(content)


def prepend_release_notes(
    release_notes: ReleaseNotes,
    changelog_path: str = "CHANGELOG.md",
) -> str:
    """
    Prepend release notes to changelog.

    Args:
        release_notes: Release notes to prepend
        changelog_path: Path to changelog file

    Returns:
        Updated changelog content
    """
    existing = read_changelog(changelog_path)
    new_entry = release_notes.to_markdown()

    if not existing:
        # Create new changelog with header
        updated = f"# Changelog\n\n{new_entry}"
    else:
        # Insert after first heading
        lines = existing.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("# "):
                insert_idx = i + 1
                # Skip any blank lines after the header
                while insert_idx < len(lines) and not lines[insert_idx].strip():
                    insert_idx += 1
                break

        if insert_idx == 0:
            # No header found, prepend
            updated = f"# Changelog\n\n{new_entry}\n\n{existing}"
        else:
            lines.insert(insert_idx, "\n" + new_entry)
            updated = "\n".join(lines)

    write_changelog(updated, changelog_path)
    return updated


def get_unreleased_section(changelog_path: str = "CHANGELOG.md") -> str | None:
    """Extract the unreleased section from changelog."""
    content = read_changelog(changelog_path)
    if not content:
        return None

    # Look for ## [Unreleased] or ## Unreleased section
    pattern = r"^##\s*\[?Unreleased\]?(.*?)(?=^##\s|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def update_unreleased_section(
    content: str,
    changelog_path: str = "CHANGELOG.md",
) -> str:
    """Update the unreleased section with new content."""
    write_changelog(content, changelog_path)
    return content


def generate_changelog_from_git(
    repo_path: str = ".",
    tag_prefix: str = "v",
    since_version: Version | None = None,
) -> str:
    """Generate full changelog from git history."""
    from conventional_release.generator import generate_release_notes, get_current_version
    from conventional_release.parser import extract_commits_from_git

    current_version = get_current_version(repo_path, tag_prefix=tag_prefix)
    if since_version is None:
        since_version = Version(0, 1, 0)

    # Get all tags
    from git import Repo

    repo = Repo(repo_path)
    tags = [tag for tag in repo.tags if tag.name.startswith(tag_prefix)]
    tags.sort(key=lambda t: t.commit.committed_datetime)

    entries = []
    prev_tag = None

    for tag in tags:
        version_str = tag.name[len(tag_prefix):]
        try:
            version = Version.parse(version_str)
        except ValueError:
            continue

        if version < since_version:
            continue

        if prev_tag:
            commits = extract_commits_from_git(repo_path, since_tag=prev_tag.name, until=tag.name)
        else:
            commits = extract_commits_from_git(repo_path, until=tag.name)

        if commits:
            release_notes = generate_release_notes(commits, version)
            entries.append(release_notes.to_markdown())

        prev_tag = tag

    # Add commits since last tag
    if prev_tag:
        commits = extract_commits_from_git(repo_path, since_tag=prev_tag.name)
        if commits:
            release_notes = generate_release_notes(commits, current_version)
            entries.append(release_notes.to_markdown())

    if not entries:
        return "# Changelog\n\nNo releases yet."

    return "# Changelog\n\n" + "\n".join(reversed(entries))


def validate_changelog(changelog_path: str = "CHANGELOG.md") -> list[str]:
    """Validate changelog format, return list of issues."""
    issues = []
    content = read_changelog(changelog_path)

    if not content:
        issues.append("Changelog is empty")
        return issues

    # Check for required header
    if not content.startswith("# Changelog"):
        issues.append("Changelog should start with '# Changelog'")

    # Check for version sections
    version_sections = re.findall(r"^##\s+([\d.]+)", content, re.MULTILINE)
    if not version_sections:
        issues.append("No version sections found")

    # Check for duplicate versions
    seen = set()
    for version in version_sections:
        if version in seen:
            issues.append(f"Duplicate version section: {version}")
        seen.add(version)

    return issues


