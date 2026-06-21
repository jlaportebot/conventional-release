"""Parser for conventional commit messages."""

from __future__ import annotations

import re

from conventional_release.models import CommitType, ConventionalCommit

# Regex pattern for conventional commits
CONVENTIONAL_COMMIT_PATTERN = re.compile(
    r"^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?(?P<breaking>!)?: (?P<description>.+)$"
)

# Footer pattern
FOOTER_PATTERN = re.compile(r"^(?P<key>[A-Za-z-]+): (?P<value>.+)$")

# BREAKING CHANGE in body/footer
BREAKING_CHANGE_PATTERN = re.compile(r"^BREAKING CHANGE: (?P<description>.+)$", re.MULTILINE)


def parse_commit(
    message: str,
    commit_hash: str,
    author: str,
    email: str,
    date: str,
) -> ConventionalCommit:
    """
    Parse a conventional commit message.

    Args:
        message: The commit message
        commit_hash: Full commit hash
        author: Author name
        email: Author email
        date: Commit date (ISO format)

    Returns:
        Parsed ConventionalCommit object
    """
    raw_message = message
    lines = message.strip().split("\n")

    # Parse header line
    header = lines[0] if lines else ""
    match = CONVENTIONAL_COMMIT_PATTERN.match(header)

    if not match:
        # Not a conventional commit, treat as chore
        return ConventionalCommit(
            type=CommitType.CHORE,
            scope=None,
            description=header,
            body="\n".join(lines[1:]) if len(lines) > 1 else "",
            footer={},
            hash=commit_hash,
            author=author,
            email=email,
            date=date,
            raw_message=raw_message,
        )

    commit_type_str = match.group("type")
    scope = match.group("scope")
    breaking = match.group("breaking") is not None
    description = match.group("description")

    # Parse commit type
    try:
        commit_type = CommitType.from_string(commit_type_str)
    except ValueError:
        commit_type = CommitType.CHORE

    # Note: don't override type if breaking - keep original type but mark as breaking
    # The is_breaking property will handle the ! and BREAKING CHANGE footer

    # Parse body and footer
    body_lines = []
    footer: dict[str, str] = {}
    in_footer = False

    for line in lines[1:]:
        if not line.strip() and not in_footer:
            # Empty line - potential separator between body and footer
            # We don't switch to footer mode yet - wait for actual footer line
            body_lines.append(line)
            continue

        if in_footer:
            footer_match = FOOTER_PATTERN.match(line)
            if footer_match:
                footer[footer_match.group("key")] = footer_match.group("value")
            # Continuation of previous footer value
            elif footer:
                last_key = next(reversed(footer))
                footer[last_key] += " " + line.strip()
            else:
                # No footer started yet, this is still body
                body_lines.append(line)
        else:
            # Check if this line is a footer (Key: Value)
            footer_match = FOOTER_PATTERN.match(line)
            if footer_match:
                # This is a footer line - switch to footer mode
                in_footer = True
                footer[footer_match.group("key")] = footer_match.group("value")
            else:
                body_lines.append(line)

    body = "\n".join(body_lines).strip()

    # Check for BREAKING CHANGE in body
    if not breaking:
        breaking_match = BREAKING_CHANGE_PATTERN.search(body)
        if breaking_match:
            footer["BREAKING CHANGE"] = breaking_match.group("description")
            # Remove the BREAKING CHANGE line from body
            body = BREAKING_CHANGE_PATTERN.sub("", body).strip()

    return ConventionalCommit(
        type=commit_type,
        scope=scope,
        description=description,
        body=body,
        footer=footer,
        hash=commit_hash,
        author=author,
        email=email,
        date=date,
        raw_message=raw_message,
    )


def parse_commits(commits_data: list[tuple[str, str, str, str, str]]) -> list[ConventionalCommit]:
    """
    Parse multiple commits.

    Args:
        commits_data: List of (message, hash, author, email, date) tuples

    Returns:
        List of parsed ConventionalCommit objects
    """
    return [
        parse_commit(msg, hsh, author, email, date)
        for msg, hsh, author, email, date in commits_data
    ]


def extract_commits_from_git(
    repo_path: str = ".",
    since_tag: str | None = None,
    until: str = "HEAD",
    limit: int | None = None,
) -> list[ConventionalCommit]:
    """
    Extract commits from a git repository.

    Args:
        repo_path: Path to git repository
        since_tag: Tag to start from (exclusive)
        until: Revision to stop at (inclusive)
        limit: Maximum number of commits to return

    Returns:
        List of parsed ConventionalCommit objects
    """
    from git import Repo

    repo = Repo(repo_path)

    # Build rev-list arguments
    rev_range = f"{since_tag}..{until}" if since_tag else until

    commits = [
        (
            commit.message.strip(),
            commit.hexsha,
            commit.author.name,
            commit.author.email,
            commit.authored_datetime.isoformat(),
        )
        for commit in repo.iter_commits(rev_range, max_count=limit)
    ]

    return parse_commits(commits)


def get_latest_tag(repo_path: str = ".", pattern: str = "v*") -> str | None:
    """Get the latest tag matching pattern."""
    from git import Repo

    repo = Repo(repo_path)
    tags = [tag for tag in repo.tags if tag.name.startswith(pattern.rstrip("*"))]
    if not tags:
        return None

    # Sort by commit date
    tags.sort(key=lambda t: t.commit.committed_datetime, reverse=True)
    return tags[0].name


def get_commits_since_last_release(
    repo_path: str = ".",
    tag_prefix: str = "v",
) -> list[ConventionalCommit]:
    """Get all commits since the last release tag."""
    latest_tag = get_latest_tag(repo_path, tag_prefix)
    return extract_commits_from_git(repo_path, since_tag=latest_tag)
