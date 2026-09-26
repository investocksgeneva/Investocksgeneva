from __future__ import annotations

import sys
from pathlib import Path

import click

from orvchestra import paths
from orvchestra.db.connection import connect
from orvchestra.db.repository import add_root, get_root_by_path, library_stats, list_roots, remove_root
from orvchestra.scanner.scan import scan_all_roots
from orvchestra.scanner.volume import get_volume_uuid


def _human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _human_duration(seconds: float) -> str:
    seconds = int(seconds)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {seconds}s"


@click.group()
def main() -> None:
    """Orvchestra: a private, streaming-style player for a local music library."""


@main.group()
def roots() -> None:
    """Manage the folders Orvchestra scans."""


@roots.command("add")
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--label", default=None, help="Friendly name for this root (e.g. 'External SSD').")
def roots_add(path: str, label: str | None) -> None:
    conn = connect(paths.db_path())
    resolved = str(Path(path).resolve())
    if get_root_by_path(conn, resolved) is not None:
        click.echo(f"Already tracked: {resolved}")
        return
    volume_uuid = get_volume_uuid(Path(resolved))
    add_root(conn, resolved, label, volume_uuid)
    click.echo(f"Added root: {resolved}")


@roots.command("remove")
@click.argument("path")
def roots_remove(path: str) -> None:
    conn = connect(paths.db_path())
    resolved = str(Path(path).resolve())
    if remove_root(conn, resolved):
        click.echo(f"Removed root: {resolved}")
    else:
        click.echo(f"No such root: {resolved}", err=True)
        sys.exit(1)


@roots.command("list")
def roots_list() -> None:
    conn = connect(paths.db_path())
    rows = list_roots(conn)
    if not rows:
        click.echo("No roots configured. Add one with: orvchestra roots add /path/to/music")
        return
    for row in rows:
        status = "online" if row["online"] else "OFFLINE"
        label = f" ({row['label']})" if row["label"] else ""
        click.echo(f"[{status}] {row['path']}{label}")


@main.command()
@click.option("--root", "only_path", default=None, help="Only scan this root path.")
def scan(only_path: str | None) -> None:
    """Scan configured roots for new, changed, or missing tracks."""
    conn = connect(paths.db_path())
    if only_path is not None:
        only_path = str(Path(only_path).resolve())

    all_stats = scan_all_roots(conn, paths.artwork_dir(), only_path=only_path)
    if not all_stats:
        click.echo("No roots configured. Add one with: orvchestra roots add /path/to/music")
        return

    for stats in all_stats:
        if not stats.reachable:
            click.echo(f"{stats.root_path}: unreachable (drive unplugged?) — tracks marked offline")
            continue
        click.echo(
            f"{stats.root_path}: scanned {stats.scanned} in {stats.duration_seconds:.1f}s "
            f"(+{stats.added} added, ~{stats.updated} updated, ={stats.unchanged} unchanged, "
            f"-{stats.marked_offline} now offline, +{stats.marked_online} back online, "
            f"{stats.skipped_dataless} dataless skipped, {stats.skipped_unreadable} unreadable)"
        )


@main.command()
def stats() -> None:
    """Show library counts, format mix, and hi-res share."""
    conn = connect(paths.db_path())
    s = library_stats(conn)
    click.echo(f"Tracks:  {s['total_tracks']} ({s['offline_tracks']} offline)")
    click.echo(f"Albums:  {s['albums']}")
    click.echo(f"Artists: {s['artists']}")
    click.echo(f"Total time: {_human_duration(s['total_duration_seconds'])}")
    click.echo(f"Total size: {_human_size(s['total_size_bytes'])}")
    click.echo(f"Hi-res (>16-bit or >44.1kHz): {s['hires_tracks']} ({s['hires_share']:.0%})")
    click.echo("By codec:")
    for codec, count in s["by_codec"].items():
        click.echo(f"  {codec}: {count}")


if __name__ == "__main__":
    main()
