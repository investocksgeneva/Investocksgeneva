from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
import uvicorn
from async_upnp_client.utils import get_local_ip

from orvchestra import paths
from orvchestra.db.connection import connect
from orvchestra.db.repository import (
    add_root,
    count_offline_tracks,
    find_duplicate_tracks,
    get_root_by_path,
    library_stats,
    list_roots,
    purge_offline_tracks,
    remove_root,
)
from orvchestra.dlna.server import DlnaMediaServer
from orvchestra.playback.keepawake import KeepAwakeController
from orvchestra.playback.service import PlaybackService
from orvchestra.scanner.scan import scan_all_roots
from orvchestra.scanner.volume import get_volume_uuid
from orvchestra.webapp.app import create_app as create_web_app


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

    resolved_path = Path(resolved)
    for existing in list_roots(conn):
        existing_path = Path(existing["path"])
        if resolved_path.is_relative_to(existing_path):
            click.echo(
                f"Refusing to add: {resolved} is inside the already-tracked root {existing_path} "
                "-- adding it too would scan the same files twice under two roots. "
                "If you meant to replace the existing root, remove it first with "
                f'"orvchestra roots remove \\"{existing_path}\\"".',
                err=True,
            )
            sys.exit(1)
        if existing_path.is_relative_to(resolved_path):
            click.echo(
                f"Refusing to add: the already-tracked root {existing_path} is inside {resolved}, "
                "so adding this broader folder would scan those same files a second time. "
                f'Remove the narrower root first with "orvchestra roots remove \\"{existing_path}\\"" '
                "if you meant to widen it.",
                err=True,
            )
            sys.exit(1)

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
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Re-read every file's tags even if its size/mtime look unchanged "
    "(e.g. after upgrading Orvchestra to read a tag it didn't before).",
)
def scan(only_path: str | None, force: bool) -> None:
    """Scan configured roots for new, changed, or missing tracks."""
    conn = connect(paths.db_path())
    if only_path is not None:
        only_path = str(Path(only_path).resolve())

    all_stats = scan_all_roots(conn, paths.artwork_dir(), only_path=only_path, force=force)
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


@main.command("purge-offline")
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
def purge_offline(yes: bool) -> None:
    """Permanently delete every track currently marked offline, along with
    its ratings and play history. Use this only for files you know are gone
    for good -- a drive that's just temporarily unplugged should be left
    alone, since reconnecting it brings those tracks back online with their
    history intact. This never touches anything on disk; it only removes
    the now-stale database rows those missing files left behind."""
    conn = connect(paths.db_path())
    count = count_offline_tracks(conn)
    if count == 0:
        click.echo("No offline tracks to purge.")
        return

    click.echo(f"{count} track(s) are currently offline.")
    if not yes and not click.confirm(
        "Permanently delete their database records (ratings and play history included)? "
        "This cannot be undone, and doesn't affect any files on disk"
    ):
        click.echo("Cancelled.")
        return

    purged = purge_offline_tracks(conn)
    click.echo(f"Purged {purged} track(s).")


@main.command()
def duplicates() -> None:
    """List tracks that look like duplicate files: same album, disc, and
    track number appearing more than once. Read-only -- nothing is ever
    deleted or moved; review the listed paths and remove extras yourself."""
    conn = connect(paths.db_path())
    groups = find_duplicate_tracks(conn)
    if not groups:
        click.echo("No likely duplicates found.")
        return

    for group in groups:
        first = group[0]
        click.echo(f"\n{first['group_album_artist']} — {first['group_album']} — track {first['track_number']}: {first['title']}")
        for row in group:
            full_path = Path(row["root_path"]) / row["rel_path"]
            duration = _human_duration(row["duration_seconds"] or 0)
            size = _human_size(row["size"])
            click.echo(f"  {duration:>8}  {size:>8}  {full_path}")


@main.command()
@click.option("--dlna-port", default=8200, show_default=True, help="Port for DLNA device description/SOAP control.")
@click.option("--web-port", default=8347, show_default=True, help="Port for the web app, JSON API, and media streaming.")
@click.option("--host", default=None, help="LAN address to advertise; auto-detected if omitted.")
def serve(dlna_port: int, web_port: int, host: str | None) -> None:
    """Run the DLNA MediaServer and the web app. Ctrl-C to stop."""
    asyncio.run(_serve(dlna_port, web_port, host))


async def _serve(dlna_port: int, web_port: int, host: str | None) -> None:
    conn = connect(paths.db_path())
    local_ip = host or get_local_ip()
    web_base_url = f"http://{local_ip}:{web_port}"

    keep_awake = KeepAwakeController()
    playback = PlaybackService(conn, web_base_url, keep_awake)

    web_app = create_web_app(conn, web_base_url, playback)
    uvicorn_server = uvicorn.Server(
        uvicorn.Config(web_app, host="0.0.0.0", port=web_port, log_level="warning")
    )

    dlna_server = DlnaMediaServer(conn, web_base_url, dlna_port, host=local_ip)
    await dlna_server.start()

    click.echo("Orvchestra is serving:")
    click.echo(f"  DLNA device description: http://{local_ip}:{dlna_port}/upnp/device.xml")
    click.echo(f"  Web app:                 {web_base_url}")
    click.echo("Look for \"Orvchestra (MacBook)\" in WiiM Home's music library sources,")
    click.echo("or open the web app above on your phone/laptop.")
    click.echo("Press Ctrl-C to stop.")

    try:
        await uvicorn_server.serve()
    finally:
        await dlna_server.stop()
        keep_awake.shutdown()


if __name__ == "__main__":
    main()
