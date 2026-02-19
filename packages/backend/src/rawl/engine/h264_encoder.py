"""H.264 encoder managing an FFmpeg subprocess and publishing NAL units to Redis.

Thread safety: NOT thread-safe. Must be used from a single asyncio event loop.
Lifecycle: start() -> feed_frame() x N -> stop(). Must call stop() even on error.
"""
from __future__ import annotations

import asyncio
import logging
import struct
import time

import numpy as np

from rawl.config import settings
from rawl.engine.flv_demuxer import FLVDemuxError, VideoTag, parse_flv_tags
from rawl.redis_client import redis_pool

logger = logging.getLogger(__name__)


class H264EncoderError(Exception):
    """Raised when encoder fails to start or crashes mid-stream."""


class H264Encoder:
    """Manages an FFmpeg subprocess encoding raw RGB frames to H.264.

    Reads FLV output, demuxes to H.264 NAL units, publishes to Redis streams.
    """

    def __init__(self, match_id: str, width: int = 256, height: int = 256) -> None:
        self._match_id = match_id
        self._width = width
        self._height = height
        self._frame_bytes = width * height * 3  # RGB24
        self._proc: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None
        self._seq = 0
        self._started = False
        self._stopped = False
        self._sps_pps: bytes | None = None
        self._start_time: float = 0.0
        self.frames_encoded = 0
        self.frames_published = 0

    @property
    def is_running(self) -> bool:
        return self._started and not self._stopped and self._proc is not None

    async def start(self) -> None:
        """Spawn FFmpeg subprocess and start background reader.

        Raises H264EncoderError if FFmpeg fails to start.
        """
        if self._started:
            raise H264EncoderError("Encoder already started")

        cmd = [
            settings.ffmpeg_path,
            "-f", "rawvideo",
            "-pixel_format", "rgb24",
            "-video_size", f"{self._width}x{self._height}",
            "-framerate", str(settings.streaming_fps),
            "-i", "pipe:0",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-profile:v", "baseline",
            "-level", "3.1",
            "-bf", "0",
            "-g", str(settings.h264_keyframe_interval),
            "-crf", str(settings.h264_crf),
            "-maxrate", "1M",
            "-bufsize", "500K",
            "-f", "flv",
            "-flvflags", "no_duration_filesize",
            "pipe:1",
        ]

        try:
            self._proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError, OSError) as e:
            raise H264EncoderError(f"Failed to start FFmpeg: {e}") from e

        self._started = True
        self._start_time = time.monotonic()

        self._reader_task = asyncio.create_task(
            self._read_output(), name=f"h264-reader-{self._match_id}"
        )
        self._stderr_task = asyncio.create_task(
            self._log_stderr(), name=f"h264-stderr-{self._match_id}"
        )

        logger.info("H264 encoder started", extra={"match_id": self._match_id, "cmd": cmd[0]})

    async def feed_frame(self, rgb_frame: np.ndarray) -> None:
        """Write one RGB frame to FFmpeg stdin.

        Args:
            rgb_frame: numpy array shape (H, W, 3) dtype uint8 in RGB order.

        Raises:
            H264EncoderError: If encoder is not running.
            ValueError: If frame shape doesn't match expected dimensions.
        """
        if not self.is_running:
            raise H264EncoderError("Encoder is not running")

        if rgb_frame.shape != (self._height, self._width, 3):
            raise ValueError(
                f"Frame shape {rgb_frame.shape} doesn't match "
                f"expected ({self._height}, {self._width}, 3)"
            )

        frame_data = rgb_frame.tobytes()
        assert len(frame_data) == self._frame_bytes

        try:
            self._proc.stdin.write(frame_data)
            await self._proc.stdin.drain()
            self.frames_encoded += 1
        except (BrokenPipeError, ConnectionResetError):
            logger.warning(
                "FFmpeg stdin pipe broken",
                extra={"match_id": self._match_id, "frames": self.frames_encoded},
            )
            self._stopped = True
            raise H264EncoderError("FFmpeg stdin pipe broken")

    async def stop(self) -> None:
        """Gracefully shut down encoder. Safe to call multiple times."""
        if self._stopped:
            return
        self._stopped = True

        # 1. Close stdin to signal FFmpeg to flush + exit
        if self._proc and self._proc.stdin:
            try:
                self._proc.stdin.close()
                await self._proc.stdin.wait_closed()
            except Exception:
                pass

        # 2. Wait for process exit (5s timeout, then kill)
        if self._proc:
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._proc.kill()
                await self._proc.wait()

        # 3. Cancel background tasks
        for task in (self._reader_task, self._stderr_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

        # 4. Publish EOS sentinel
        try:
            await redis_pool.stream_publish(
                f"match:{self._match_id}:video",
                {b"type": b"eos"},
                maxlen=settings.redis_video_stream_maxlen,
            )
        except Exception:
            logger.warning("Failed to publish EOS sentinel", extra={"match_id": self._match_id})

        # 5. Set TTL on Redis keys for cleanup
        try:
            ttl = settings.redis_stream_ttl_seconds
            client = redis_pool.client
            await client.expire(f"match:{self._match_id}:video", ttl)
            await client.expire(f"match:{self._match_id}:data", ttl)
            await client.expire(f"match:{self._match_id}:sps_pps", ttl)
        except Exception:
            pass

        logger.info(
            "H264 encoder stopped",
            extra={
                "match_id": self._match_id,
                "frames_encoded": self.frames_encoded,
                "frames_published": self.frames_published,
            },
        )

    async def _read_output(self) -> None:
        """Background task: read FFmpeg stdout, parse FLV, publish to Redis."""
        stream_key = f"match:{self._match_id}:video"
        sps_pps_key = f"match:{self._match_id}:sps_pps"

        try:
            async for tag in parse_flv_tags(self._proc.stdout):
                if self._stopped:
                    return
                await self._publish_tag(tag, stream_key, sps_pps_key)
        except FLVDemuxError as e:
            logger.error(
                "FLV demux error [%s]: %s", self._match_id, e,
            )
        except asyncio.IncompleteReadError as e:
            logger.warning(
                "FFmpeg stdout EOF [%s]: partial=%d expected=%d",
                self._match_id, len(e.partial), e.expected,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Unexpected error in FLV reader", extra={"match_id": self._match_id})
        finally:
            if not self._stopped:
                logger.warning(
                    "FLV reader exited unexpectedly",
                    extra={"match_id": self._match_id},
                )
                self._stopped = True

    async def _publish_tag(self, tag: VideoTag, stream_key: str, sps_pps_key: str) -> None:
        """Publish a single parsed VideoTag to Redis."""
        self._seq += 1

        if tag.is_sequence_header:
            tag_type = b"seq"
            self._sps_pps = tag.nal_data
            # Cache SPS+PPS for late joiners
            try:
                await redis_pool.client.set(
                    sps_pps_key, tag.nal_data, ex=settings.redis_stream_ttl_seconds
                )
            except Exception:
                logger.debug("Failed to cache SPS+PPS", extra={"match_id": self._match_id})
        elif tag.is_keyframe:
            tag_type = b"key"
        else:
            tag_type = b"delta"

        elapsed_us = int((time.monotonic() - self._start_time) * 1_000_000)

        data = {
            b"nal": tag.nal_data,
            b"type": tag_type,
            b"ts": str(elapsed_us).encode(),
            b"seq": str(self._seq).encode(),
        }

        try:
            await redis_pool.stream_publish(
                stream_key, data, maxlen=settings.redis_video_stream_maxlen
            )
            self.frames_published += 1
        except Exception:
            logger.debug(
                "Failed to publish NAL to Redis",
                extra={"match_id": self._match_id, "seq": self._seq},
            )

    async def _log_stderr(self) -> None:
        """Background task: read FFmpeg stderr and log warnings/errors."""
        try:
            while True:
                line = await self._proc.stderr.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip()
                if not text:
                    continue
                # Log ALL FFmpeg stderr at warning level so it's visible in Railway
                logger.warning("FFmpeg [%s]: %s", self._match_id, text)
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
