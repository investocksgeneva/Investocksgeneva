"""Test fixture generation.

Every audio file used by the tests is a real, valid, decodable file — a few
hundred milliseconds of silence — with real tags written by mutagen. FLAC and
WAV are encoded with `soundfile` (libsndfile); MP3 is encoded with `lameenc`
(a real LAME binding). None of this is imported by orvchestra itself: it
exists purely so the scanner is tested against genuine codec bitstreams
instead of hand-built byte stubs.
"""

from __future__ import annotations

import wave as wave_module
from pathlib import Path

import lameenc
import mutagen.flac
import mutagen.id3
import mutagen.mp3
import numpy as np
import pytest
import soundfile as sf

from orvchestra.db.connection import connect


@pytest.fixture(autouse=True)
def isolated_app_data(tmp_path, monkeypatch):
    """Every test gets its own app-data dir; never the real one on the machine."""
    data_dir = tmp_path / "app-data"
    monkeypatch.setenv("ORVCHESTRA_DATA_DIR", str(data_dir))
    return data_dir


@pytest.fixture
def db_conn(isolated_app_data):
    from orvchestra import paths

    conn = connect(paths.db_path())
    yield conn
    conn.close()


def _silence(seconds: float, samplerate: int, channels: int) -> np.ndarray:
    frames = int(seconds * samplerate)
    return np.zeros((frames, channels), dtype=np.float64)


def make_flac(
    path: Path,
    *,
    seconds: float = 0.2,
    samplerate: int = 44100,
    channels: int = 2,
    bit_depth: int = 16,
    tags: dict[str, str] | None = None,
    picture_bytes: bytes | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subtype = {16: "PCM_16", 24: "PCM_24"}[bit_depth]
    sf.write(str(path), _silence(seconds, samplerate, channels), samplerate, subtype=subtype, format="FLAC")

    audio = mutagen.flac.FLAC(str(path))
    for key, value in (tags or {}).items():
        audio[key] = value
    if picture_bytes is not None:
        pic = mutagen.flac.Picture()
        pic.data = picture_bytes
        pic.type = 3  # front cover
        pic.mime = "image/png"
        audio.add_picture(pic)
    audio.save()
    return path


def make_wav(
    path: Path,
    *,
    seconds: float = 0.2,
    samplerate: int = 44100,
    channels: int = 2,
    bit_depth: int = 16,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(seconds * samplerate)
    with wave_module.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(bit_depth // 8)
        w.setframerate(samplerate)
        w.writeframes(b"\x00" * n_frames * channels * (bit_depth // 8))
    return path


def _tiny_png() -> bytes:
    # A minimal valid 1x1 PNG, built once by hand rather than shipped as a
    # binary test fixture.
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
        "53de000000097048597300000ec300000ec301c76fa8640000000c49444154"
        "789c6360606060000000050001a5f645400000000049454e44ae426082"
    )


def make_mp3(
    path: Path,
    *,
    seconds: float = 0.2,
    samplerate: int = 44100,
    channels: int = 2,
    tags: dict[str, str] | None = None,
    picture_bytes: bytes | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_frames = int(seconds * samplerate)
    pcm = np.zeros(n_frames * channels, dtype=np.int16).tobytes()

    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(samplerate)
    encoder.set_channels(channels)
    encoder.set_quality(2)
    mp3_data = encoder.encode(pcm) + encoder.flush()
    path.write_bytes(mp3_data)

    audio = mutagen.mp3.MP3(str(path))
    if audio.tags is None:
        audio.add_tags()
    frame_map = {
        "title": ("TIT2", mutagen.id3.TIT2),
        "artist": ("TPE1", mutagen.id3.TPE1),
        "albumartist": ("TPE2", mutagen.id3.TPE2),
        "album": ("TALB", mutagen.id3.TALB),
        "tracknumber": ("TRCK", mutagen.id3.TRCK),
        "discnumber": ("TPOS", mutagen.id3.TPOS),
        "date": ("TDRC", mutagen.id3.TDRC),
        "genre": ("TCON", mutagen.id3.TCON),
        "compilation": ("TCMP", mutagen.id3.TCMP),
    }
    for key, value in (tags or {}).items():
        if key in frame_map:
            frame_id, frame_cls = frame_map[key]
            audio.tags.add(frame_cls(encoding=3, text=[value]))
        else:
            audio.tags.add(mutagen.id3.TXXX(encoding=3, desc=key.upper(), text=[value]))
    if picture_bytes is not None:
        audio.tags.add(
            mutagen.id3.APIC(encoding=3, mime="image/png", type=3, desc="cover", data=picture_bytes)
        )
    audio.save(v2_version=3)
    return path


@pytest.fixture
def tiny_png_bytes() -> bytes:
    return _tiny_png()
