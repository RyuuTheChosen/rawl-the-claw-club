"""Verify FIX 6: recorder.close() double-call guard.

Second close() must be a no-op — no file truncation.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path
from tempfile import TemporaryDirectory

from rawl.engine.replay_recorder import ReplayRecorder


def test_close_idempotent():
    """Calling close() twice doesn't truncate JSON/IDX files."""
    with TemporaryDirectory() as tmpdir:
        rec = ReplayRecorder("test-match", work_dir=Path(tmpdir))

        # Write some frames
        for i in range(10):
            jpeg = b"\xff\xd8\xff\xe0" + bytes([i]) * 100  # fake JPEG
            state = {"p1_health": 0.8, "p2_health": 0.5} if i % 6 == 0 else None
            rec.write_frame(jpeg, state)

        # First close — writes JSON and IDX
        rec.close()

        json_path = Path(tmpdir) / "test-match.json"
        idx_path = Path(tmpdir) / "test-match.idx"
        mjpeg_path = Path(tmpdir) / "test-match.mjpeg"

        json_size_1 = json_path.stat().st_size
        idx_size_1 = idx_path.stat().st_size
        mjpeg_size_1 = mjpeg_path.stat().st_size

        # Verify files are non-empty
        assert json_size_1 > 0
        assert idx_size_1 > 0
        assert mjpeg_size_1 > 0

        # Verify JSON is valid and has entries
        data = json.loads(json_path.read_text())
        assert len(data) == 2  # frames 0 and 6

        # Verify IDX has correct number of offsets
        idx_bytes = idx_path.read_bytes()
        num_offsets = len(idx_bytes) // 8
        assert num_offsets == 10

        # Second close — must be a no-op
        rec.close()

        json_size_2 = json_path.stat().st_size
        idx_size_2 = idx_path.stat().st_size
        mjpeg_size_2 = mjpeg_path.stat().st_size

        assert json_size_2 == json_size_1, "JSON file was truncated on second close"
        assert idx_size_2 == idx_size_1, "IDX file was truncated on second close"
        assert mjpeg_size_2 == mjpeg_size_1, "MJPEG file was truncated on second close"

        # Verify data integrity preserved
        data_after = json.loads(json_path.read_text())
        assert data_after == data


def test_closed_flag():
    """_closed flag is set after first close."""
    with TemporaryDirectory() as tmpdir:
        rec = ReplayRecorder("flag-test", work_dir=Path(tmpdir))
        assert rec._closed is False

        rec.close()
        assert rec._closed is True

        # Third call — still no-op
        rec.close()
        assert rec._closed is True
