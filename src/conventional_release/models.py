"""Data models for conventional commits."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CommitType(StrEnum):
    """Conventional commit types."""

    FEAT = "feat"
    FIX = "fix"
    BREAKING = "breaking"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    PERF = "perf"
    TEST = "test"
    CHORE = "chore"
    CI = "ci"
    BUILD = "build"
    REVERT = "revert"

    @classmethod
    def from_string(cls, value: str) -> CommitType:
        """Create CommitType from string, case-insensitive."""
        normalized = value.lower().strip()
        for member in cls:
            if member.value == normalized:
                return member
            # Handle BREAKING CHANGE alias
            if member == cls.BREAKING and normalized in ("breaking change", "breaking"):
                return member
        msg = f"Unknown commit type: {value}"
        raise ValueError(msg)

    def is_feature(self) -> bool:
        """Check if this type represents a feature."""
        return self == CommitType.FEAT

    def is_fix(self) -> bool:
        """Check if this type represents a fix."""
        return self == CommitType.FIX

    def is_breaking_type(self) -> bool:
        """Check if this type is inherently breaking."""
        return self == CommitType.BREAKING

    def release_section(self) -> str:
        """Get the release notes section for this commit type."""
        mapping = {
            CommitType.FEAT: "Features",
            CommitType.FIX: "Bug Fixes",
            CommitType.BREAKING: "Breaking Changes",
            CommitType.DOCS: "Documentation",
            CommitType.STYLE: "Styles",
            CommitType.REFACTOR: "Refactoring",
            CommitType.PERF: "Performance",
            CommitType.TEST: "Tests",
            CommitType.CHORE: "Chores",
            CommitType.CI: "CI",
            CommitType.BUILD: "Build",
            CommitType.REVERT: "Reverts",
        }
        return mapping.get(self, "Other")


@dataclass
class BreakingChange:
    """Represents a breaking change extracted from a commit."""

    description: str
    commit_hash: str | None = None
    scope: str | None = None


@dataclass
class ConventionalCommit:
    """Parsed conventional commit."""

    type: CommitType
    scope: str | None
    description: str
    body: str
    footer: dict[str, str]
    hash: str
    author: str
    email: str
    date: str
    raw_message: str = ""

    @property
    def is_breaking(self) -> bool:
        """Check if this commit represents a breaking change."""
        if self.type.is_breaking_type():
            return True
        if self.raw_message and "!" in self.raw_message.split(":")[0]:
            return True
        return "BREAKING CHANGE" in self.footer

    @property
    def breaking_changes(self) -> list[BreakingChange]:
        """Extract breaking changes from this commit."""
        changes = []
        if self.is_breaking:
            desc = self.footer.get("BREAKING CHANGE", self.description)
            changes.append(
                BreakingChange(
                    description=desc,
                    commit_hash=self.hash,
                    scope=self.scope,
                )
            )
        return changes

    def short_hash(self, length: int = 7) -> str:
        """Get shortened commit hash."""
        return self.hash[:length]

    def __lt__(self, other: ConventionalCommit) -> bool:
        """Sort by date (newest first)."""
        return self.date > other.date


@dataclass
class ReleaseNotes:
    """Generated release notes."""

    version: str
    date: str
    commits: list[ConventionalCommit]
    breaking_changes: list[BreakingChange]
    features: list[ConventionalCommit]
    fixes: list[ConventionalCommit]
    others: dict[CommitType, list[ConventionalCommit]] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Render release notes as Markdown."""
        lines = [f"## {self.version} ({self.date})", ""]

        if self.breaking_changes:
            lines.append("### Breaking Changes")
            for bc in self.breaking_changes:
                scope_str = f"({bc.scope})" if bc.scope else ""
                lines.append(f"- {scope_str} {bc.description}")
            lines.append("")

        if self.features:
            lines.append("### Features")
            for commit in self.features:
                scope_str = f"({commit.scope})" if commit.scope else ""
                lines.append(f"- {scope_str} {commit.description} ({commit.short_hash()})")
            lines.append("")

        if self.fixes:
            lines.append("### Bug Fixes")
            for commit in self.fixes:
                scope_str = f"({commit.scope})" if commit.scope else ""
                lines.append(f"- {scope_str} {commit.description} ({commit.short_hash()})")
            lines.append("")

        # Other commit types
        for commit_type, commits in self.others.items():
            if not commits:
                continue
            section = commit_type.release_section()
            lines.append(f"### {section}")
            for commit in commits:
                scope_str = f"({commit.scope})" if commit.scope else ""
                lines.append(f"- {scope_str} {commit.description} ({commit.short_hash()})")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"


@dataclass
class Version:
    """Semantic version representation."""

    major: int
    minor: int
    patch: int
    prerelease: str | None = None
    build: str | None = None

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version

    def __lt__(self, other: Version) -> bool:
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch
        # Prerelease versions are less than release versions
        if self.prerelease is None and other.prerelease is not None:
            return False
        if self.prerelease is not None and other.prerelease is None:
            return True
        if self.prerelease is not None and other.prerelease is not None:
            return self.prerelease < other.prerelease
        return False

    def __le__(self, other: Version) -> bool:
        return self == other or self < other

    def __gt__(self, other: Version) -> bool:
        return not self <= other

    def __ge__(self, other: Version) -> bool:
        return not self < other

    def bump_major(self) -> Version:
        """Bump major version."""
        return Version(self.major + 1, 0, 0)

    def bump_minor(self) -> Version:
        """Bump minor version."""
        return Version(self.major, self.minor + 1, 0)

    def bump_patch(self) -> Version:
        """Bump patch version."""
        return Version(self.major, self.minor, self.patch + 1)

    @classmethod
    def parse(cls, version_str: str) -> Version:
        """Parse version string."""
        import semver

        parsed = semver.Version.parse(version_str)
        return cls(
            major=parsed.major,
            minor=parsed.minor,
            patch=parsed.patch,
            prerelease=parsed.prerelease,
            build=parsed.build,
        )


@dataclass
class ReleaseConfig:
    """Configuration for release generation."""

    repo_path: str = "."
    github_token: str | None = None
    github_repo: str | None = None
    changelog_path: str = "CHANGELOG.md"
    version_file: str | None = None
    tag_prefix: str = "v"
    commit_types: dict[str, str] = field(default_factory=dict)
    release_name_template: str = "Release {version}"
    draft: bool = False
    prerelease: bool = False
    target_commitish: str = "main"
    tagger_name: str | None = None
    tagger_email: str | None = None

    def get_section_name(self, commit_type: CommitType) -> str:
        """Get custom section name for commit type."""
        return self.commit_types.get(commit_type.value, commit_type.release_section())

