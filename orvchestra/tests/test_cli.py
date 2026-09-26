from __future__ import annotations

from click.testing import CliRunner

from orvchestra.cli import main
from conftest import make_flac


def test_cli_roots_scan_stats_end_to_end(isolated_app_data, tmp_path):
    music = tmp_path / "music"
    make_flac(
        music / "Artist" / "Album" / "01.flac",
        tags={"TITLE": "One", "ARTIST": "Artist", "ALBUM": "Album", "ALBUMARTIST": "Artist", "DATE": "2022"},
    )
    make_flac(
        music / "Artist" / "Album" / "02.flac",
        tags={
            "TITLE": "Two", "ARTIST": "Artist", "ALBUM": "Album", "ALBUMARTIST": "Artist",
            "DATE": "2022", "DISCNUMBER": "1",
        },
        bit_depth=24,
        samplerate=96000,
    )

    runner = CliRunner()

    result = runner.invoke(main, ["roots", "add", str(music), "--label", "Test Library"])
    assert result.exit_code == 0, result.output
    assert "Added root" in result.output

    result = runner.invoke(main, ["roots", "list"])
    assert result.exit_code == 0, result.output
    assert "Test Library" in result.output
    assert "[online]" in result.output

    result = runner.invoke(main, ["scan"])
    assert result.exit_code == 0, result.output
    assert "+2 added" in result.output

    result = runner.invoke(main, ["stats"])
    assert result.exit_code == 0, result.output
    assert "Tracks:  2" in result.output
    assert "Albums:  1" in result.output
    assert "FLAC: 2" in result.output
    # One of the two tracks is 24-bit/96kHz, so hi-res share should be 50%.
    assert "Hi-res" in result.output and "50%" in result.output

    # Re-running scan should be a no-op.
    result = runner.invoke(main, ["scan"])
    assert result.exit_code == 0, result.output
    assert "=2 unchanged" in result.output

    result = runner.invoke(main, ["roots", "remove", str(music)])
    assert result.exit_code == 0, result.output
    assert "Removed root" in result.output
    result = runner.invoke(main, ["roots", "list"])
    assert "No roots configured" in result.output


def test_cli_handles_empty_library_and_missing_root(isolated_app_data, tmp_path):
    runner = CliRunner()

    result = runner.invoke(main, ["scan"])
    assert result.exit_code == 0, result.output
    assert "No roots configured" in result.output

    result = runner.invoke(main, ["stats"])
    assert result.exit_code == 0, result.output
    assert "Tracks:  0" in result.output

    result = runner.invoke(main, ["roots", "remove", str(tmp_path / "nope")])
    assert result.exit_code != 0
    assert "No such root" in result.output
