"""CLI for conventional-release."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from conventional_release.changelog import (
    generate_changelog_from_git,
    prepend_release_notes,
    validate_changelog,
)
from conventional_release.generator import (
    determine_version_bump,
    generate_release_notes,
    get_current_version,
    prepare_release,
    update_version_file,
)
from conventional_release.models import ReleaseConfig, Version
from conventional_release.parser import get_commits_since_last_release

console = Console()


@click.group()
@click.version_option(version="0.1.0")
@click.option(
    "--repo-path",
    "-r",
    default=".",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to git repository",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Path to config file (YAML)",
)
@click.pass_context
def main(ctx: click.Context, repo_path: str, config: str | None) -> None:
    """Generate release notes from conventional commits."""
    ctx.ensure_object(dict)
    ctx.obj["repo_path"] = repo_path
    ctx.obj["config_path"] = config
    ctx.obj["config"] = load_config(config, repo_path)


def load_config(config_path: str | None, repo_path: str) -> ReleaseConfig:
    """Load configuration from file and environment."""
    config = ReleaseConfig(repo_path=repo_path)

    if config_path:
        import yaml

        try:
            with Path(config_path).open() as f:
                data = yaml.safe_load(f)
                if data:
                    for key, value in data.items():
                        if hasattr(config, key):
                            setattr(config, key, value)
        except yaml.YAMLError:
            # Invalid YAML - use defaults
            pass

    # Override with environment variables
    if token := os.environ.get("GITHUB_TOKEN"):
        config.github_token = token
    if repo := os.environ.get("GITHUB_REPO"):
        config.github_repo = repo

    return config


@main.command()
@click.option(
    "--since",
    "-s",
    help="Start revision (tag or commit)",
)
@click.option(
    "--until",
    "-u",
    default="HEAD",
    help="End revision (default: HEAD)",
)
@click.option(
    "--limit",
    "-l",
    type=int,
    help="Maximum number of commits",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["table", "json", "markdown"]),
    default="table",
    help="Output format",
)
@click.pass_context
def commits(
    ctx: click.Context,
    since: str | None,
    until: str,
    limit: int | None,
    output_format: str,
) -> None:
    """List commits since last release."""
    repo_path = ctx.obj["repo_path"]
    config = ctx.obj["config"]

    if since:
        from conventional_release.parser import extract_commits_from_git

        commits_list = extract_commits_from_git(
            repo_path, since_tag=since, until=until, limit=limit
        )
    else:
        commits_list = get_commits_since_last_release(repo_path, config.tag_prefix)
        if limit:
            commits_list = commits_list[:limit]

    if output_format == "table":
        table = Table(title=f"Commits since last release ({len(commits_list)} commits)")
        table.add_column("Type", style="cyan")
        table.add_column("Scope", style="magenta")
        table.add_column("Description", style="green")
        table.add_column("Hash", style="dim")
        table.add_column("Author", style="yellow")

        for commit in commits_list:
            scope = commit.scope or ""
            table.add_row(
                commit.type.value,
                scope,
                commit.description[:60] + ("..." if len(commit.description) > 60 else ""),
                commit.short_hash(),
                commit.author,
            )
        console.print(table)

    elif output_format == "markdown":
        for commit in commits_list:
            scope_str = f"({commit.scope})" if commit.scope else ""
            breaking = "!" if commit.is_breaking else ""
            console.print(
                f"- {commit.type.value}{scope_str}{breaking}: "
                f"{commit.description} ({commit.short_hash()})"
            )

    elif output_format == "json":
        import json

        data = [
            {
                "type": c.type.value,
                "scope": c.scope,
                "description": c.description,
                "body": c.body,
                "footer": c.footer,
                "hash": c.hash,
                "author": c.author,
                "email": c.email,
                "date": c.date,
                "breaking": c.is_breaking,
            }
            for c in commits_list
        ]
        console.print(json.dumps(data, indent=2))


@main.command()
@click.option(
    "--version",
    "-v",
    help="Version to generate notes for (default: auto-detect)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file (default: stdout)",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["markdown", "json"]),
    default="markdown",
    help="Output format",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be generated without writing",
)
@click.pass_context
def notes(
    ctx: click.Context,
    version: str | None,
    output: str | None,
    output_format: str,
    dry_run: bool,
) -> None:
    """Generate release notes."""
    repo_path = ctx.obj["repo_path"]
    config = ctx.obj["config"]

    commits_list = get_commits_since_last_release(repo_path, config.tag_prefix)

    if not commits_list:
        console.print("[yellow]No commits since last release[/yellow]")
        return

    # Determine version
    if version:
        version_obj = Version.parse(version)
    else:
        current_version = get_current_version(repo_path, config.version_file, config.tag_prefix)
        version_obj = determine_version_bump(commits_list, current_version)

    release_notes = generate_release_notes(commits_list, version_obj, config)

    if output_format == "markdown":
        content = release_notes.to_markdown()
    else:
        import json

        content = json.dumps(
            {
                "version": release_notes.version,
                "date": release_notes.date,
                "breaking_changes": [
                    {
                        "description": bc.description,
                        "scope": bc.scope,
                        "commit_hash": bc.commit_hash,
                    }
                    for bc in release_notes.breaking_changes
                ],
                "features": [
                    {"scope": c.scope, "description": c.description, "hash": c.short_hash()}
                    for c in release_notes.features
                ],
                "fixes": [
                    {"scope": c.scope, "description": c.description, "hash": c.short_hash()}
                    for c in release_notes.fixes
                ],
            },
            indent=2,
        )

    if output:
        Path(output).write_text(content)
        console.print(f"[green]Release notes written to {output}[/green]")
    elif not dry_run:
        console.print(content)


@main.command()
@click.option(
    "--version",
    "-v",
    help="Version to release (default: auto-detect)",
)
@click.option(
    "--changelog",
    is_flag=True,
    help="Update CHANGELOG.md",
)
@click.option(
    "--version-file",
    type=click.Path(),
    help="Update version file",
)
@click.option(
    "--github",
    is_flag=True,
    help="Create GitHub release",
)
@click.option(
    "--tag",
    is_flag=True,
    help="Create git tag",
)
@click.option(
    "--push",
    is_flag=True,
    help="Push tag to remote",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without executing",
)
@click.pass_context
def release(
    ctx: click.Context,
    version: str | None,
    changelog: bool,
    version_file: str | None,
    github: bool,
    tag: bool,
    push: bool,
    dry_run: bool,
) -> None:
    """Create a release."""
    repo_path = ctx.obj["repo_path"]
    config = ctx.obj["config"]

    if version_file:
        config.version_file = version_file

    # Prepare release
    new_version, release_notes = prepare_release(repo_path, config)

    if version:
        new_version = Version.parse(version)

    console.print(f"[bold]Preparing release {config.tag_prefix}{new_version}[/bold]")

    if dry_run:
        console.print("[yellow]DRY RUN - no changes will be made[/yellow]")
        console.print(release_notes.to_markdown())
        return

    # Update changelog
    if changelog:
        prepend_release_notes(release_notes, config.changelog_path)
        console.print(f"[green]Updated {config.changelog_path}[/green]")

    # Update version file
    if config.version_file or version_file:
        target_file = version_file or config.version_file
        update_version_file(new_version, target_file)
        console.print(f"[green]Updated version file: {target_file}[/green]")

    # Create git tag
    if tag:
        from git import Repo

        repo = Repo(repo_path)
        tag_name = f"{config.tag_prefix}{new_version}"
        repo.create_tag(tag_name, message=f"Release {tag_name}")
        console.print(f"[green]Created tag: {tag_name}[/green]")

        if push:
            origin = repo.remotes.origin
            origin.push(tag_name)
            console.print(f"[green]Pushed tag: {tag_name}[/green]")

    # Create GitHub release
    if github:
        from conventional_release.github import (
            create_github_client,
            create_github_release,
            get_repo_info_from_remote,
        )

        repo_info = get_repo_info_from_remote(repo_path)
        if not repo_info:
            console.print("[red]Could not determine GitHub repo from remote[/red]")
            sys.exit(1)

        owner, repo = repo_info
        client = create_github_client(config.github_token)

        try:
            result = create_github_release(owner, repo, release_notes, config, client)
            console.print(f"[green]Created GitHub release: {result['html_url']}[/green]")
        except (RuntimeError, ValueError, KeyError) as e:
            error_msg = f"Failed to create GitHub release: {e}"
            console.print(f"[red]{error_msg}[/red]")
            sys.exit(1)


@main.command()
@click.option(
    "--version-file",
    type=click.Path(),
    help="Path to version file",
)
@click.pass_context
def version(
    ctx: click.Context,
    version_file: str | None,
) -> None:
    """Show current version."""
    repo_path = ctx.obj["repo_path"]
    config = ctx.obj["config"]

    if version_file:
        config.version_file = version_file

    current = get_current_version(repo_path, config.version_file, config.tag_prefix)
    console.print(f"Current version: [bold]{config.tag_prefix}{current}[/bold]")

    # Show next version
    commits_list = get_commits_since_last_release(repo_path, config.tag_prefix)
    if commits_list:
        next_version = determine_version_bump(commits_list, current)
        console.print(f"Next version: [bold]{config.tag_prefix}{next_version}[/bold]")
        console.print(f"  Based on {len(commits_list)} commits since last release")
    else:
        console.print("[yellow]No commits since last release[/yellow]")


@main.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Validate changelog format."""
    ctx.obj["repo_path"]
    config = ctx.obj["config"]

    issues = validate_changelog(config.changelog_path)
    if issues:
        console.print("[red]Changelog validation failed:[/red]")
        for issue in issues:
            console.print(f"  - {issue}")
        sys.exit(1)
    else:
        console.print("[green]Changelog is valid[/green]")


@main.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file (default: CHANGELOG.md)",
)
@click.pass_context
def generate(ctx: click.Context, output: str | None) -> None:
    """Generate full changelog from git history."""
    repo_path = ctx.obj["repo_path"]
    config = ctx.obj["config"]

    changelog_path = output or config.changelog_path
    content = generate_changelog_from_git(repo_path, config.tag_prefix)

    if output:
        Path(output).write_text(content)
    else:
        Path(changelog_path).write_text(content)

    console.print(f"[green]Generated changelog: {changelog_path}[/green]")


if __name__ == "__main__":
    main()

