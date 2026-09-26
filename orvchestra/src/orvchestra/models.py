"""Plain dataclasses passed between the scanner and the database layer.

Keeping these separate from the SQLite rows means the tag-reading code never
has to know about SQL, and the DB layer never has to know about mutagen.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrackTags:
    """Everything the scanner could read out of one audio file's tags/stream info."""

    duration_seconds: float | None = None
    codec: str | None = None
    sample_rate: int | None = None
    bit_depth: int | None = None
    channels: int | None = None
    bitrate: int | None = None

    title: str | None = None
    artist: str | None = None
    album_artist: str | None = None
    album: str | None = None
    disc_number: int | None = None
    disc_total: int | None = None
    track_number: int | None = None
    track_total: int | None = None
    year: int | None = None
    genre: str | None = None
    compilation: bool = False

    musicbrainz_track_id: str | None = None
    musicbrainz_album_id: str | None = None
    musicbrainz_artist_id: str | None = None

    replaygain_track_gain: float | None = None
    replaygain_track_peak: float | None = None
    replaygain_album_gain: float | None = None
    replaygain_album_peak: float | None = None


@dataclass
class ScanStats:
    root_path: str
    scanned: int = 0
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    marked_offline: int = 0
    marked_online: int = 0
    skipped_dataless: int = 0
    skipped_unreadable: int = 0
    reachable: bool = True
    duration_seconds: float = 0.0

    def __add__(self, other: "ScanStats") -> "ScanStats":
        merged = ScanStats(root_path=f"{self.root_path}+{other.root_path}")
        for name in (
            "scanned", "added", "updated", "unchanged", "marked_offline",
            "marked_online", "skipped_dataless", "skipped_unreadable", "duration_seconds",
        ):
            setattr(merged, name, getattr(self, name) + getattr(other, name))
        return merged
