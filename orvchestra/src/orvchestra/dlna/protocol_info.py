"""Maps our stored `codec` string to what DLNA/HTTP needs to describe it:
a MIME type, and (when DLNA defines one) an official DLNA.ORG_PN media
profile.

FLAC has no official DLNA media profile -- DLNA's standard profile set
predates FLAC's adoption by AV receivers -- so the field is simply left out
for it, same as most real-world DLNA servers (minidlna, Gerbera) do. The
WiiM Amp Pro plays FLAC over DLNA regardless, since it (like most modern
renderers) falls back to the declared MIME type when no profile is given.
"""

from __future__ import annotations

# DLNA.ORG_FLAGS for "this is a plain streamable file, byte-range seek only,
# no transcoding" -- the same flag value used by minidlna/Gerbera-style
# servers for local, untranscoded audio. See the DLNA/DTCP-IP media format
# profile guidelines for the bit layout; there's no need to hand-roll this
# per file since none of our flags vary by track.
_DLNA_FLAGS = "01700000000000000000000000000000"

_CODEC_INFO: dict[str, tuple[str, str | None]] = {
    "FLAC": ("audio/flac", None),
    "MP3": ("audio/mpeg", "MP3"),
    "WAV": ("audio/wav", None),
    "AAC": ("audio/mp4", None),
    "ALAC": ("audio/mp4", None),
}


def mime_type_for(codec: str | None) -> str:
    if codec is None:
        return "application/octet-stream"
    mime, _pn = _CODEC_INFO.get(codec, ("application/octet-stream", None))
    return mime


def dlna_content_features(codec: str | None) -> str:
    """The value shared by the `<res protocolInfo=...>` 4th field and the
    `contentFeatures.dlna.org` HTTP response header -- both describe the same
    resource, so they must always agree."""
    if codec is None:
        return "*"
    mime, pn = _CODEC_INFO.get(codec, ("application/octet-stream", None))
    parts = []
    if pn:
        parts.append(f"DLNA.ORG_PN={pn}")
    parts.append("DLNA.ORG_OP=01")  # byte-range seek supported, time-seek not
    parts.append("DLNA.ORG_CI=0")  # original content, not a live conversion
    parts.append(f"DLNA.ORG_FLAGS={_DLNA_FLAGS}")
    return ";".join(parts)


def protocol_info(codec: str | None) -> str:
    """The full `protocolInfo` string for a `<res>` element."""
    mime = mime_type_for(codec)
    return f"http-get:*:{mime}:{dlna_content_features(codec)}"
