"""Tag + stream-info extraction, one function per container format.

mutagen gives every format a different tag object shape (Vorbis comments are
a case-insensitive multi-map of strings; ID3 is a bag of typed frame
objects; MP4 atoms mix strings, byte blobs and (track, total) tuples), so
there's no single generic path that stays correct. Each `_read_*` function
below normalizes its format's quirks into the same `TrackTags` shape.
"""

from __future__ import annotations

import re
from pathlib import Path

import mutagen
from mutagen.dsdiff import DSDIFF
from mutagen.dsf import DSF
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.wave import WAVE

from orvchestra.models import TrackTags

_YEAR_RE = re.compile(r"(\d{4})")


class UnsupportedAudioFile(Exception):
    pass


def _year_from(text: str | None) -> int | None:
    if not text:
        return None
    m = _YEAR_RE.search(text)
    return int(m.group(1)) if m else None


def _parse_pair(text: str | None) -> tuple[int | None, int | None]:
    """Parse a "3/12" style tag value into (3, 12)."""
    if not text:
        return None, None
    parts = text.split("/", 1)
    try:
        num = int(parts[0]) if parts[0].strip() else None
    except ValueError:
        num = None
    total = None
    if len(parts) > 1:
        try:
            total = int(parts[1]) if parts[1].strip() else None
        except ValueError:
            total = None
    return num, total


def _int_or_none(text: str | None) -> int | None:
    if text and text.strip().isdigit():
        return int(text.strip())
    return None


def _to_float(text: str | None) -> float | None:
    if not text:
        return None
    try:
        # ReplayGain values are stored like "-6.32 dB"; peak values are plain floats.
        return float(text.split()[0])
    except (ValueError, IndexError):
        return None


def _truthy(text: str | None) -> bool:
    return text is not None and text.strip() not in ("", "0", "false", "False")


# --- FLAC / Vorbis comments ------------------------------------------------

def _vc_first(tags, *keys: str) -> str | None:
    if tags is None:
        return None
    for key in keys:
        values = tags.get(key)
        if values:
            return str(values[0])
    return None


def _read_flac(mfile: FLAC) -> tuple[TrackTags, object | None]:
    info = mfile.info
    tags = mfile.tags
    disc_num, disc_total = _parse_pair(_vc_first(tags, "DISCNUMBER"))
    if disc_total is None:
        disc_total = _int_or_none(_vc_first(tags, "DISCTOTAL", "TOTALDISCS"))
    track_num, track_total = _parse_pair(_vc_first(tags, "TRACKNUMBER"))
    if track_total is None:
        track_total = _int_or_none(_vc_first(tags, "TRACKTOTAL", "TOTALTRACKS"))

    genres = tags.get("GENRE") if tags else None
    genre = "; ".join(str(g) for g in genres) if genres else None

    picture = mfile.pictures[0] if mfile.pictures else None

    return TrackTags(
        duration_seconds=info.length,
        codec="FLAC",
        sample_rate=info.sample_rate,
        bit_depth=info.bits_per_sample,
        channels=info.channels,
        bitrate=getattr(info, "bitrate", None) or None,
        title=_vc_first(tags, "TITLE"),
        artist=_vc_first(tags, "ARTIST"),
        album_artist=_vc_first(tags, "ALBUMARTIST"),
        album=_vc_first(tags, "ALBUM"),
        disc_number=disc_num,
        disc_total=disc_total,
        track_number=track_num,
        track_total=track_total,
        year=_year_from(_vc_first(tags, "DATE", "YEAR", "ORIGINALDATE")),
        genre=genre,
        compilation=_truthy(_vc_first(tags, "COMPILATION")),
        musicbrainz_track_id=_vc_first(tags, "MUSICBRAINZ_RELEASETRACKID", "MUSICBRAINZ_TRACKID"),
        musicbrainz_album_id=_vc_first(tags, "MUSICBRAINZ_ALBUMID"),
        musicbrainz_artist_id=_vc_first(tags, "MUSICBRAINZ_ARTISTID"),
        replaygain_track_gain=_to_float(_vc_first(tags, "REPLAYGAIN_TRACK_GAIN")),
        replaygain_track_peak=_to_float(_vc_first(tags, "REPLAYGAIN_TRACK_PEAK")),
        replaygain_album_gain=_to_float(_vc_first(tags, "REPLAYGAIN_ALBUM_GAIN")),
        replaygain_album_peak=_to_float(_vc_first(tags, "REPLAYGAIN_ALBUM_PEAK")),
        # SYNCEDLYRICS is an informal convention some taggers use for raw .lrc
        # text embedded whole; prefer it over plain unsynced lyrics when both exist.
        lyrics=_vc_first(tags, "SYNCEDLYRICS", "LYRICS", "UNSYNCEDLYRICS"),
    ), picture


# --- ID3 (MP3, and the ID3 chunk some WAV/DSF files carry) -----------------

def _id3_text(tags, frame_id: str) -> str | None:
    if tags is None:
        return None
    frame = tags.get(frame_id)
    if frame is None or not getattr(frame, "text", None):
        return None
    return str(frame.text[0])


def _id3_lyrics(tags) -> str | None:
    if tags is None:
        return None
    uslt_frames = tags.getall("USLT")
    return str(uslt_frames[0].text) if uslt_frames else None


def _id3_txxx(tags) -> dict[str, str]:
    if tags is None:
        return {}
    out = {}
    for frame in tags.getall("TXXX"):
        if frame.text:
            out[frame.desc.upper()] = str(frame.text[0])
    return out


def _read_id3_tags(tags) -> TrackTags:
    txxx = _id3_txxx(tags)
    disc_num, disc_total = _parse_pair(_id3_text(tags, "TPOS"))
    track_num, track_total = _parse_pair(_id3_text(tags, "TRCK"))

    genre = None
    tcon = tags.get("TCON") if tags else None
    if tcon is not None:
        try:
            genre = "; ".join(tcon.genres)  # resolves numeric ID3v1 genre codes too
        except AttributeError:
            genre = _id3_text(tags, "TCON")

    date_text = _id3_text(tags, "TDRC") or _id3_text(tags, "TYER") or _id3_text(tags, "TDAT")

    mb_track_id = txxx.get("MUSICBRAINZ RELEASE TRACK ID")
    ufid = tags.get("UFID:http://musicbrainz.org") if tags else None
    if mb_track_id is None and ufid is not None:
        try:
            mb_track_id = ufid.data.decode("ascii")
        except (AttributeError, UnicodeDecodeError):
            mb_track_id = None

    return TrackTags(
        title=_id3_text(tags, "TIT2"),
        artist=_id3_text(tags, "TPE1"),
        album_artist=_id3_text(tags, "TPE2"),
        album=_id3_text(tags, "TALB"),
        disc_number=disc_num,
        disc_total=disc_total,
        track_number=track_num,
        track_total=track_total,
        year=_year_from(date_text),
        genre=genre,
        compilation=_truthy(_id3_text(tags, "TCMP")),
        musicbrainz_track_id=mb_track_id,
        musicbrainz_album_id=txxx.get("MUSICBRAINZ ALBUM ID"),
        musicbrainz_artist_id=txxx.get("MUSICBRAINZ ARTIST ID"),
        replaygain_track_gain=_to_float(txxx.get("REPLAYGAIN_TRACK_GAIN")),
        replaygain_track_peak=_to_float(txxx.get("REPLAYGAIN_TRACK_PEAK")),
        replaygain_album_gain=_to_float(txxx.get("REPLAYGAIN_ALBUM_GAIN")),
        replaygain_album_peak=_to_float(txxx.get("REPLAYGAIN_ALBUM_PEAK")),
        lyrics=_id3_lyrics(tags),
    )


def _id3_picture(tags):
    if tags is None:
        return None
    apics = tags.getall("APIC")
    return apics[0] if apics else None


def _read_mp3(mfile: MP3) -> tuple[TrackTags, object | None]:
    info = mfile.info
    base = _read_id3_tags(mfile.tags)
    base.duration_seconds = info.length
    base.codec = "MP3"
    base.sample_rate = info.sample_rate
    base.bit_depth = None  # lossy: bit depth is not a meaningful concept
    base.channels = info.channels
    base.bitrate = getattr(info, "bitrate", None)
    if base.bitrate:
        base.bitrate //= 1000  # mutagen reports bps; we store kbps like everything else
    return base, _id3_picture(mfile.tags)


def _read_wave(mfile: WAVE) -> tuple[TrackTags, object | None]:
    info = mfile.info
    tags = mfile.tags if hasattr(mfile.tags, "getall") else None
    base = _read_id3_tags(tags) if tags else TrackTags()
    base.duration_seconds = info.length
    base.codec = "WAV"
    base.sample_rate = info.sample_rate
    base.bit_depth = getattr(info, "bits_per_sample", None)
    base.channels = info.channels
    base.bitrate = getattr(info, "bitrate", None)
    if base.bitrate:
        base.bitrate //= 1000
    return base, _id3_picture(tags)


def _read_dsd(mfile) -> tuple[TrackTags, object | None]:
    info = mfile.info
    tags = mfile.tags if hasattr(mfile.tags, "getall") else None
    base = _read_id3_tags(tags) if tags else TrackTags()
    base.duration_seconds = info.length
    base.codec = "DSD"
    base.sample_rate = getattr(info, "sample_rate", None)
    base.bit_depth = 1
    base.channels = getattr(info, "channels", None)
    base.bitrate = None
    return base, _id3_picture(tags)


# --- MP4 / ALAC -------------------------------------------------------------

def _mp4_text(tags, atom: str) -> str | None:
    values = tags.get(atom)
    return str(values[0]) if values else None


def _mp4_freeform(tags, name: str) -> str | None:
    values = tags.get(f"----:com.apple.iTunes:{name}")
    if not values:
        return None
    raw = values[0]
    try:
        return bytes(raw).decode("utf-8")
    except UnicodeDecodeError:
        return None


def _read_mp4(mfile: MP4) -> tuple[TrackTags, object | None]:
    info = mfile.info
    tags = mfile.tags or {}

    track_num = track_total = disc_num = disc_total = None
    trkn = tags.get("trkn")
    if trkn:
        track_num, track_total = trkn[0][0] or None, trkn[0][1] or None
    disk = tags.get("disk")
    if disk:
        disc_num, disc_total = disk[0][0] or None, disk[0][1] or None

    codec = "ALAC" if str(getattr(info, "codec", "")).startswith("alac") else "AAC"

    picture = None
    covr = tags.get("covr")
    if covr:
        picture = bytes(covr[0])

    return TrackTags(
        duration_seconds=info.length,
        codec=codec,
        sample_rate=info.sample_rate,
        bit_depth=getattr(info, "bits_per_sample", None) if codec == "ALAC" else None,
        channels=info.channels,
        bitrate=(getattr(info, "bitrate", None) or 0) // 1000 or None,
        title=_mp4_text(tags, "\xa9nam"),
        artist=_mp4_text(tags, "\xa9ART"),
        album_artist=_mp4_text(tags, "aART"),
        album=_mp4_text(tags, "\xa9alb"),
        disc_number=disc_num,
        disc_total=disc_total,
        track_number=track_num,
        track_total=track_total,
        year=_year_from(_mp4_text(tags, "\xa9day")),
        genre=_mp4_text(tags, "\xa9gen"),
        compilation=bool(tags.get("cpil", [False])[0]),
        musicbrainz_track_id=_mp4_freeform(tags, "MusicBrainz Release Track Id")
        or _mp4_freeform(tags, "MusicBrainz Track Id"),
        musicbrainz_album_id=_mp4_freeform(tags, "MusicBrainz Album Id"),
        musicbrainz_artist_id=_mp4_freeform(tags, "MusicBrainz Artist Id"),
        replaygain_track_gain=_to_float(_mp4_freeform(tags, "replaygain_track_gain")),
        replaygain_track_peak=_to_float(_mp4_freeform(tags, "replaygain_track_peak")),
        replaygain_album_gain=_to_float(_mp4_freeform(tags, "replaygain_album_gain")),
        replaygain_album_peak=_to_float(_mp4_freeform(tags, "replaygain_album_peak")),
        lyrics=_mp4_text(tags, "\xa9lyr"),
    ), picture


# --- dispatch ----------------------------------------------------------------

def read_tags(path: Path) -> tuple[TrackTags, object | None]:
    """Returns (TrackTags, embedded_picture_or_none).

    embedded_picture is either a mutagen Picture/APIC-like object with
    `.data`/`.mime`, or raw cover bytes (MP4 'covr' atoms) — see
    scanner/artwork.py for how each shape is normalized.
    """
    mfile = mutagen.File(path)
    if mfile is None:
        raise UnsupportedAudioFile(f"mutagen could not identify {path}")

    if isinstance(mfile, FLAC):
        return _read_flac(mfile)
    if isinstance(mfile, MP3):
        return _read_mp3(mfile)
    if isinstance(mfile, MP4):
        return _read_mp4(mfile)
    if isinstance(mfile, WAVE):
        return _read_wave(mfile)
    if isinstance(mfile, DSF):
        tags = _read_dsd(mfile)
        tags[0].codec = "DSD (DSF)"
        return tags
    if isinstance(mfile, DSDIFF):
        tags = _read_dsd(mfile)
        tags[0].codec = "DSD (DFF)"
        return tags

    raise UnsupportedAudioFile(f"unhandled mutagen type {type(mfile)!r} for {path}")
