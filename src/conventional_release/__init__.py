"""conventional-release: Generate release notes from conventional commits."""

from __future__ import annotations

from conventional_release.changelog import prepend_release_notes, validate_changelog
from conventional_release.generator import (
    determine_version_bump,
    generate_release_notes,
    get_current_version,
    prepare_release,
)
from conventional_release.models import (
    BreakingChange,
    CommitType,
    ConventionalCommit,
    ReleaseConfig,
    ReleaseNotes,
    Version,
)
from conventional_release.parser import extract_commits_from_git, parse_commit, parse_commits

__version__ = "0.1.0"

__all__ = [
    "BreakingChange",
    "CommitType",
    "ConventionalCommit",
    "ReleaseConfig",
    "ReleaseNotes",
    "Version",
    "determine_version_bump",
    "extract_commits_from_git",
    "generate_release_notes",
    "get_current_version",
    "parse_commit",
    "parse_commits",
    "prepare_release",
    "prepend_release_notes",
    "validate_changelog",
]
