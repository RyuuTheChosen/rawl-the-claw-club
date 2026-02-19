"""Pure FLV demuxer for extracting H.264 NAL units from an FLV byte stream.

Reads from an asyncio.StreamReader and yields typed VideoTag objects.
No side effects — stateless, testable with synthetic byte streams.
"""
from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass
from typing import AsyncIterator

# FLV constants
FLV_HEADER_MAGIC = b"FLV"
TAG_TYPE_VIDEO = 0x09
AVC_CODEC_ID = 7
ANNEX_B_START_CODE = b"\x00\x00\x00\x01"
MAX_TAG_SIZE = 1 * 1024 * 1024  # 1MB safety cap


class FLVDemuxError(Exception):
    """Raised on malformed FLV data."""


@dataclass(frozen=True, slots=True)
class VideoTag:
    """Parsed H.264 video tag from FLV stream."""

    timestamp_ms: int
    is_keyframe: bool
    is_sequence_header: bool
    nal_data: bytes  # Annex B format (with start codes)


async def _read_exact(reader: asyncio.StreamReader, n: int) -> bytes:
    """Read exactly n bytes or raise FLVDemuxError on short read."""
    data = await reader.readexactly(n)
    if len(data) != n:
        raise FLVDemuxError(f"Short read: expected {n} bytes, got {len(data)}")
    return data


def _avcc_to_annex_b(avcc_body: bytes) -> bytes:
    """Convert AVCC length-prefixed NALUs to Annex B start-code format.

    AVCC format: [4-byte BE length][NALU][4-byte BE length][NALU]...
    Annex B format: [0x00 0x00 0x00 0x01][NALU][0x00 0x00 0x00 0x01][NALU]...
    """
    result = bytearray()
    offset = 0
    body_len = len(avcc_body)

    while offset < body_len:
        if offset + 4 > body_len:
            raise FLVDemuxError(
                f"AVCC truncated: need 4 bytes at offset {offset}, have {body_len - offset}"
            )
        nalu_len = struct.unpack(">I", avcc_body[offset : offset + 4])[0]
        offset += 4

        if nalu_len == 0:
            continue
        if offset + nalu_len > body_len:
            raise FLVDemuxError(
                f"AVCC NALU overflows: length={nalu_len}, remaining={body_len - offset}"
            )

        result.extend(ANNEX_B_START_CODE)
        result.extend(avcc_body[offset : offset + nalu_len])
        offset += nalu_len

    return bytes(result)


def _parse_sps_pps(avcc_body: bytes) -> bytes:
    """Parse SPS and PPS from an AVC sequence header (AVCDecoderConfigurationRecord).

    Format:
      [1] version
      [1] profile
      [1] compat
      [1] level
      [1] 0xFC | (lengthSizeMinusOne & 0x03)  -- we ignore this
      [1] 0xE0 | numSPS
      For each SPS: [2 BE] spsLength, [spsLength] spsData
      [1] numPPS
      For each PPS: [2 BE] ppsLength, [ppsLength] ppsData
    """
    if len(avcc_body) < 7:
        raise FLVDemuxError(f"SPS/PPS record too short: {len(avcc_body)} bytes")

    result = bytearray()
    offset = 5  # Skip version, profile, compat, level, lengthSizeMinusOne

    num_sps = avcc_body[offset] & 0x1F
    offset += 1

    for _ in range(num_sps):
        if offset + 2 > len(avcc_body):
            raise FLVDemuxError("SPS length truncated")
        sps_len = struct.unpack(">H", avcc_body[offset : offset + 2])[0]
        offset += 2
        if offset + sps_len > len(avcc_body):
            raise FLVDemuxError("SPS data truncated")
        result.extend(ANNEX_B_START_CODE)
        result.extend(avcc_body[offset : offset + sps_len])
        offset += sps_len

    if offset >= len(avcc_body):
        raise FLVDemuxError("PPS count missing")

    num_pps = avcc_body[offset]
    offset += 1

    for _ in range(num_pps):
        if offset + 2 > len(avcc_body):
            raise FLVDemuxError("PPS length truncated")
        pps_len = struct.unpack(">H", avcc_body[offset : offset + 2])[0]
        offset += 2
        if offset + pps_len > len(avcc_body):
            raise FLVDemuxError("PPS data truncated")
        result.extend(ANNEX_B_START_CODE)
        result.extend(avcc_body[offset : offset + pps_len])
        offset += pps_len

    return bytes(result)


async def parse_flv_tags(reader: asyncio.StreamReader) -> AsyncIterator[VideoTag]:
    """Async generator yielding VideoTag from an FLV byte stream.

    Handles:
    - FLV header validation (magic bytes, version)
    - Tag boundary parsing with size cross-checks
    - AVCC -> Annex B NAL unit conversion
    - SPS/PPS extraction from sequence headers
    - Skips non-video tags (audio, script data)
    - Raises FLVDemuxError on corrupt data
    """
    # Parse FLV header: "FLV" (3) + version (1) + flags (1) + data_offset (4)
    header = await _read_exact(reader, 9)
    if header[:3] != FLV_HEADER_MAGIC:
        raise FLVDemuxError(f"Bad FLV magic: {header[:3]!r}")

    data_offset = struct.unpack(">I", header[5:9])[0]
    # Skip any extra header bytes (usually data_offset=9, so 0 extra)
    if data_offset > 9:
        await _read_exact(reader, data_offset - 9)

    # Skip first PreviousTagSize (always 0)
    await _read_exact(reader, 4)

    while True:
        # Read tag header: type(1) + data_size(3) + timestamp(3) + ts_ext(1) + stream_id(3) = 11
        try:
            tag_header = await _read_exact(reader, 11)
        except (asyncio.IncompleteReadError, FLVDemuxError):
            return  # Stream ended

        tag_type = tag_header[0]
        data_size = struct.unpack(">I", b"\x00" + tag_header[1:4])[0]
        ts_low = struct.unpack(">I", b"\x00" + tag_header[4:7])[0]
        ts_ext = tag_header[7]
        timestamp_ms = (ts_ext << 24) | ts_low

        if data_size > MAX_TAG_SIZE:
            raise FLVDemuxError(f"Tag too large: {data_size} bytes (max {MAX_TAG_SIZE})")

        if data_size == 0:
            # Read PreviousTagSize and skip
            await _read_exact(reader, 4)
            continue

        # Read tag body
        body = await _read_exact(reader, data_size)

        # Read PreviousTagSize (4 bytes after each tag)
        prev_tag_size_bytes = await _read_exact(reader, 4)
        prev_tag_size = struct.unpack(">I", prev_tag_size_bytes)[0]
        expected_prev = data_size + 11
        if prev_tag_size != expected_prev:
            raise FLVDemuxError(
                f"PreviousTagSize mismatch: got {prev_tag_size}, expected {expected_prev}"
            )

        # Skip non-video tags
        if tag_type != TAG_TYPE_VIDEO:
            continue

        if len(body) < 5:
            continue  # Too short for a valid AVC video tag

        # Parse video tag header
        frame_type = (body[0] >> 4) & 0x0F
        codec_id = body[0] & 0x0F

        if codec_id != AVC_CODEC_ID:
            continue  # Not H.264

        avc_packet_type = body[1]
        # composition_time = struct.unpack(">I", b"\x00" + body[2:5])[0]  # usually 0
        avcc_body = body[5:]

        is_keyframe = frame_type == 1

        if avc_packet_type == 0:
            # Sequence header (SPS + PPS)
            nal_data = _parse_sps_pps(avcc_body)
            yield VideoTag(
                timestamp_ms=timestamp_ms,
                is_keyframe=True,
                is_sequence_header=True,
                nal_data=nal_data,
            )
        elif avc_packet_type == 1:
            # NALU(s)
            nal_data = _avcc_to_annex_b(avcc_body)
            if nal_data:
                yield VideoTag(
                    timestamp_ms=timestamp_ms,
                    is_keyframe=is_keyframe,
                    is_sequence_header=False,
                    nal_data=nal_data,
                )
        elif avc_packet_type == 2:
            # End of sequence — ignore
            continue
