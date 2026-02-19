from __future__ import annotations

import json
import logging
import struct
import time
from pathlib import Path

from rawl.s3_client import upload_bytes

logger = logging.getLogger(__name__)


class ReplayRecorder:
    """Records match replays to MJPEG + JSON sidecar + index file.

    Files:
        {match_id}.mjpeg — concatenated JPEG frames (fps from streaming_fps config)
        {match_id}.json  — timestamped data channel messages at 10Hz
        {match_id}.idx   — array of u64 LE byte offsets into MJPEG for O(1) seek
    """

    def __init__(self, match_id: str, work_dir: Path | None = None) -> None:
        self.match_id = match_id
        self._work_dir = work_dir or Path("/tmp/rawl_replays")
        self._work_dir.mkdir(parents=True, exist_ok=True)

        self._mjpeg_path = self._work_dir / f"{match_id}.mjpeg"
        self._json_path = self._work_dir / f"{match_id}.json"
        self._idx_path = self._work_dir / f"{match_id}.idx"

        self._mjpeg_file = open(self._mjpeg_path, "wb")
        self._data_entries: list[dict] = []
        self._frame_offsets: list[int] = []
        self._current_offset = 0
        self._frame_count = 0
        self._start_time = time.monotonic()

    def write_frame(self, jpeg_bytes: bytes, state_dict: dict | None = None) -> None:
        """Write a pre-encoded JPEG frame and optional state data entry."""
        # Record offset before writing
        self._frame_offsets.append(self._current_offset)

        # Write MJPEG frame (already encoded by caller)
        self._mjpeg_file.write(jpeg_bytes)
        self._current_offset += len(jpeg_bytes)
        self._frame_count += 1

        # Write data entry when provided (caller controls the interval)
        if state_dict is not None:
            entry = {
                "t": round(time.monotonic() - self._start_time, 3),
                "frame": self._frame_count,
                **state_dict,
            }
            self._data_entries.append(entry)

    def close(self) -> None:
        """Close file handles."""
        self._mjpeg_file.close()

        # Write JSON sidecar
        with open(self._json_path, "w") as f:
            json.dump(self._data_entries, f, separators=(",", ":"))

        # Write index file (u64 LE byte offsets)
        with open(self._idx_path, "wb") as f:
            for offset in self._frame_offsets:
                f.write(struct.pack("<Q", offset))

        logger.info(
            "Replay recording closed",
            extra={
                "match_id": self.match_id,
                "frames": self._frame_count,
                "data_entries": len(self._data_entries),
            },
        )

    async def upload_to_s3(self) -> bool:
        """Upload all 3 replay files to S3. Returns True if all succeed."""
        files = [
            (f"replays/{self.match_id}.mjpeg", self._mjpeg_path, "video/x-motion-jpeg"),
            (f"replays/{self.match_id}.json", self._json_path, "application/json"),
            (f"replays/{self.match_id}.idx", self._idx_path, "application/octet-stream"),
        ]

        all_ok = True
        for s3_key, local_path, content_type in files:
            data = local_path.read_bytes()
            ok = await upload_bytes(s3_key, data, content_type)
            if not ok:
                all_ok = False
                logger.error("Failed to upload replay file", extra={"key": s3_key})

        return all_ok

    def cleanup(self) -> None:
        """Remove local temp files."""
        for path in (self._mjpeg_path, self._json_path, self._idx_path):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
