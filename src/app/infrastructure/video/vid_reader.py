"""PyAV-based video reader with GPU acceleration, rotation extraction, and frame seeking."""

from __future__ import annotations

import os
import struct
from typing import final, override, cast

import av
import numpy as np
from av.container import InputContainer
from av.video.stream import VideoStream

from app.domain.video.metadata import VideoMetadata
from app.infrastructure.dtypes import RGBFrame
from app.shared.logging_cfg import get_logger

logger = get_logger("Infrastructure->Video->Reader")

# [NOTE]:
#  A. Explicit is better than implicit. (Silent Exceptions)
#  (Check: old_copy_2/app/infrastructure/video/vid_reader.py and decode_worker.py)


class ZeroStreamsInVideoException(Exception):
    def __init__(self, msg: str, path: str) -> None:
        super().__init__(f"No video stream found in file: {path}")
        self.path = path


@final
class VideoReader:
    """
    Opens and decodes video files using PyAV (ffmpeg wrapper) with GPU acceleration and rotation support.

    Attributes:
        _path (str): Video file path.
        _container (InputContainer | None): PyAV container handle.
        _stream (VideoStream | None): First video stream extracted from the container.
        _current_index (int): Current sequential frame position.
        _frame_iter: Iterator over decoded frames from the current stream.
        _base_rotation (int): Rotation degrees extracted from video metadata.
        _manual_rotation (int): User-applied rotation from the UI.
        _w (int): Final width after total rotation is applied.
        _h (int): Final height after total rotation is applied.

    Note:
        Rotation extraction fallback order:
            1. ``stream.metadata.get("rotate")``.
            2. ``stream.side_data[...].rotation``.
            3. Android MP4 fallback via ``_get_mp4_rotation()``.

        Frame seeking modes:
            - Sequential path: buffer-friendly for playback or batch processing.
            - Hard seek path: fast jump to an arbitrary frame via FFmpeg seek.
            - Post-seek anchor: single-use frame timestamp recovery after a seek.

        Rotation handling:
            - Metadata rotation is extracted when the reader opens.
            - Additional rotation can be applied through ``manual_rotation``.
            - Final dimensions use ``(base_rot + manual_rot) % 360`` and swap width and
              height for 90 or 270 degrees.
            - Each frame is rotated with ``np.rot90()`` and normalized with
              ``ascontiguousarray()``.

        ``VideoReader`` is not thread-safe. Use a separate instance per decoding thread.

    Example:
        reader = VideoReader("/path/to/video.mp4")
        frame = reader.read_frame_at_index(100)
        idx, frame = reader.read_next_frame()
        metadata = reader.metadata
        reader.close()
    """
    def __init__(self, path: str) -> None:
        """Open video file at ``path`` using PyAV (calls ``open()`` automatically)."""
        self._path: str = path
        logger.debug("Initializing AvVideoReader for: {}", self.path_file_name)
        self._current_index: int = 0
        self._frame_iter = None

        self._w = 0
        self._h = 0
        self._base_rotation = 0  # Natively extracted from video file
        self._manual_rotation = 0  # From user clicking Rotate CW/CCW UI buttons

        self._container: InputContainer | None = None
        self._stream: VideoStream | None = None

        try:
            self.open()
        except ValueError as e:
            logger.opt(exception=False).exception("Unable to open video file. Error: {}", e)

    def open(self) -> None:
        """Open ``_path`` via ``av.open()`` with GPU acceleration (``hwaccel=auto``)."""
        try:
            # Using {"hwaccel": "auto"} to take advantage of GPU if available
            self.container = av.open(self._path, options={"hwaccel": "auto"})

            # Enable FFmpeg's internal multi-threading for faster decoding
            self.stream.thread_type = "AUTO"
        except av.error.InvalidDataError as e:
            raise RuntimeError(f"Unable to read video file. Check if the file is valid.\n{e}")
        except av.error.FileNotFoundError as e:
            raise ValueError(f"Unable to open video file: {self._path}. Error: {e}")

    @staticmethod
    def _get_mp4_rotation(file_path: str) -> int:
        """
        Extract rotation degrees (0, 90, 180, 270) from MP4 tkhd detection transformation matrix.

        Note:
            This fallback is used for Android videos or MP4 files where PyAV cannot read
            rotation metadata. It parses MP4 detection headers, locates the ``tkhd`` detection,
            extracts the 9-element transformation matrix, and decodes the angle.

        Returns:
            int: Rotation in degrees, or ``0`` if no rotation is found or parsing fails.
        """
        try:
            with open(file_path, "rb") as f:
                while True:
                    header = f.read(8)
                    if len(header) < 8:
                        break
                    size, box_type = struct.unpack(">I4s", header)
                    box_type = box_type.decode("ascii", errors="ignore")

                    if size == 1:
                        header_size = 16
                        size = struct.unpack(">Q", f.read(8))[0]
                    elif size == 0:
                        break
                    else:
                        header_size = 8

                    if 0 < size < header_size:
                        break
                    if box_type in ("moov", "trak"):
                        continue

                    if box_type == "tkhd":
                        box_start = f.tell() - header_size
                        version = struct.unpack(">B", f.read(1))[0]
                        f.seek(3, os.SEEK_CUR)
                        f.seek(32 if version == 1 else 20, os.SEEK_CUR)
                        f.seek(16, os.SEEK_CUR)

                        matrix = struct.unpack(">9i", f.read(36))
                        a, b, u, c, d, v, x, y, w = matrix

                        if a == 0 and b == 65536 and c == -65536 and d == 0:
                            return 90
                        if a == 0 and b == -65536 and c == 65536 and d == 0:
                            return 270
                        if a == -65536 and b == 0 and c == 0 and d == -65536:
                            return 180
                        f.seek(box_start + size, os.SEEK_SET)
                    else:
                        if size > 0:
                            f.seek(size - header_size, os.SEEK_CUR)
        except Exception:
            logger.opt(exception=True).exception("Unable to get rotation matrix")
        return 0

    @property
    def basename(self):
        """Return filename only (no directory path)."""
        return os.path.basename(self._path)

    @property
    def container(self) -> InputContainer:
        """Get PyAV ``InputContainer`` (video file handle)."""
        if self._container is None:
            raise ValueError("Video container is not initialized")
        return self._container

    @container.setter
    def container(self, container: InputContainer) -> None:
        """Set container and extract video stream (calls 3-tier rotation extraction)."""
        try:
            self.stream = container.streams.video[0]
        except IndexError:
            raise ZeroStreamsInVideoException(f"No video stream found in file container", path=self._path)
        except ValueError as e:
            logger.opt(exception=True).exception("Unable to set video file container . Error: {}", e)
        except Exception as e:
            logger.opt(exception=True).exception("Unable to set video stream in container")
            raise e

        self._container = container
        # --- Extact Base Rotation ---
        self._base_rotation = 0

        # 1. Standard Metadata Dictionary Check
        rot_meta = self.stream.metadata.get("rotate")
        if rot_meta is not None:
            try:
                self._base_rotation = int(float(rot_meta))
            except ValueError:
                logger.opt(exception=True).exception(
                    "Error while setting _base_rotation from rot_meta = {}", rot_meta
                )

        # 2. Modern PyAV Side Data Check
        if self._base_rotation == 0 and hasattr(self.stream, "side_data"):
            for sd in self.stream.side_data:
                if "DISPLAYMATRIX" in str(sd.type).upper() and hasattr(sd, "rotation"):
                    self._base_rotation = int(sd.rotation)
                    break

        # 3. Android Pure Python MP4 Check
        if self._base_rotation == 0 and self._path.lower().endswith((".mp4", ".mov")):
            self._base_rotation = self._get_mp4_rotation(self._path)

        self._recalculate_dimensions()

    @container.deleter
    def container(self) -> None:
        """Close and release video container."""
        if self._container is not None:
            self._container.close()
            self._container = None
        self._frame_iter = None
        del self.stream

    @property
    def stream(self) -> VideoStream:
        """Get PyAV ``VideoStream`` (first video track)."""
        if self._stream is None:
            raise ValueError("Video stream is not initialized")
        return self._stream

    @stream.setter
    def stream(self, stream: VideoStream) -> None:
        """Set the video stream."""
        self._stream = stream

    @stream.deleter
    def stream(self) -> None:
        """Clear stream reference."""
        self._stream = None

    @property
    def path(self) -> str:
        """Return full file path."""
        return self._path

    @property
    def path_file_name(self) -> str:
        """Return filename only (split on `/`)."""
        return self._path.split("/")[-1]

    @property
    def manual_rotation(self) -> int:
        """Get user-applied rotation (0, 90, 180, 270 degrees)."""
        return self._manual_rotation

    @manual_rotation.setter
    def manual_rotation(self, value: int) -> None:
        """Set user rotation, recalculate dimensions based on total rotation."""
        self._manual_rotation = value % 360
        self._recalculate_dimensions()

    def _recalculate_dimensions(self) -> None:
        """Update ``_w`` and ``_h`` by applying total rotation (base + manual)."""
        if self._stream is None:
            return

        w = self.stream.codec_context.width
        h = self.stream.codec_context.height
        total_rot = (self._base_rotation + self._manual_rotation) % 360

        if total_rot in (90, 270):
            self._w, self._h = h, w
        else:
            self._w, self._h = w, h

    @property
    def frame_count(self) -> int:
        """Total frames in video (or 0 if unknown)."""
        return self.stream.frames or 0

    @property
    def fps(self) -> float:
        """Frames per second (playback speed)."""
        if self.stream.average_rate is None:
            raise ValueError("Video stream average rate is None")
        return float(self.stream.average_rate)

    @property
    def width(self) -> int:
        """Final width after rotation applied (may be swapped with height)."""
        return self._w

    @property
    def height(self) -> int:
        """Final height after rotation applied (may be swapped with width)."""
        return self._h

    @property
    def metadata(self) -> VideoMetadata:
        """Return ``VideoMetadata`` snapshot (static; immutable after creation)."""
        return VideoMetadata(
            _path=self._path,
            _width=self.width,
            _height=self.height,
            _fps=self.fps,
            _frame_count=self.frame_count,
        )

    def close(self) -> None:
        """Close and release video file handle."""
        logger.debug("Closing AvVideoReader for: {}", self._path)
        del self.container

    def _apply_rotation(self, arr: np.ndarray) -> RGBFrame:
        """
        Apply total rotation (base + manual) and fix non-contiguous memory layout.

        Note:
            Steps:
                1. Calculate total rotation with ``(base_rot + manual_rot) % 360``.
                2. Apply ``np.rot90(k=...)`` when rotation is needed.
                3. Call ``ascontiguousarray()`` to remove padding artifacts.

            ``ascontiguousarray()`` avoids PySide6 ``QImage`` crashes caused by padding
            bytes that PyAV may add.
        """
        total_rot = (self._base_rotation + self._manual_rotation) % 360

        if total_rot == 90:
            rotated = np.rot90(arr, k=-1)
        elif total_rot == 180:
            rotated = np.rot90(arr, k=-2)
        elif total_rot == 270:
            rotated = np.rot90(arr, k=1)
        else:
            rotated = arr

        # FIX 2: ascontiguousarray strips padding bytes so PySide6 doesn't crash!
        return np.ascontiguousarray(rotated)

    def read_frame_at_index(self, frame_index: int) -> RGBFrame | None:
        """
        Read frame at ``frame_index`` (0-based), using fast or hard seek path.

        Note:
            Three-path logic:
                - Path 1: sequential buffer iteration when the target is within ±60 frames.
                - Path 2: hard seek to PTS, then anchor on the first decoded frame timestamp.
                - Fallback: return ``None`` if the frame cannot be reached.

            Implementation details:
                - ``_current_index`` tracks a pure sequential count and ignores variable
                  frame rate timestamps.
                - After a seek, timestamp data is used once to re-anchor
                  ``_current_index``.
                - Subsequent frames switch back to sequential counting.
                - Permission errors trigger a close, reopen, and retry path.

        Returns:
            RGBFrame | None: The requested RGB frame, or ``None`` on failure.
        """
        # 1. Initialize stream if fresh
        if self._frame_iter is None:
            self._frame_iter = self.container.decode(self._stream)
            self._current_index = 0

        # 2. Fast Path (Sequential Read)
        # Increased to +60 to give the buffer plenty of room
        if self._current_index <= frame_index <= self._current_index + 60:
            for frame in self._frame_iter:
                # PURE SEQUENTIAL COUNTING: Ignore VFR timestamps completely
                current_idx = self._current_index
                self._current_index += 1

                if current_idx >= frame_index:
                    if hasattr(frame, "to_ndarray"):
                        return self._apply_rotation(frame.to_ndarray(format="rgb24"))
                    else:
                        logger.warning(
                            "Frame {} (type={}) does not have `to_ndarray` attribute method",
                            frame_index,
                            type(frame),
                        )
                        return cast(RGBFrame, frame)

        # 3. Hard Seek Calculation
        target_sec: float = frame_index / self.fps
        if self.stream.time_base is None:
            raise ValueError("stream.time_base is None")
        target_pts: int = int(target_sec / float(self.stream.time_base))

        # --- SEEK BLOCK ---
        try:
            if frame_index == 0 and (self._frame_iter is None or self._current_index == 0):
                self._frame_iter = self.container.decode(self._stream)
                self._current_index = 0
            else:
                self.container.seek(target_pts, stream=self._stream)
                self._frame_iter = self.container.decode(self._stream)

            anchored = False
            for frame in self._frame_iter:
                # ANCHOR ONCE: Only use timestamp math on the very first frame after a seek
                if not anchored:
                    if frame.time is not None:
                        self._current_index = round(frame.time * self.fps)
                    elif frame.pts is not None and self.stream.time_base is not None:
                        self._current_index = round((frame.pts * float(self.stream.time_base)) * self.fps)
                    anchored = True

                    if self._current_index < 0:
                        self._current_index = 0

                # Switch back to pure sequential counting for the rest of the loop
                current_idx = self._current_index
                self._current_index += 1

                if current_idx >= frame_index:
                    return self._apply_rotation(frame.to_ndarray(format="rgb24"))

        except av.error.PermissionError as e:
            logger.warning(f"PyAV Permission Error. Rebuilding stream.\n{e}")
            self.close()
            self.open()
            self._frame_iter = self.container.decode(self._stream)
            self._current_index = 0

        except Exception as e:
            logger.error(f"Fatal error during Hard Seek: {e}")

        return None

    def read_next_frame(self) -> tuple[int, RGBFrame]:
        """
        Read next frame sequentially, return ``(frame_index, rgb_frame)``.

        Note:
            Increments ``_current_index`` by 1, uses pure sequential counting, and
            returns the current index before incrementing.

        Raises:
            ValueError: If the stream ends and ``StopIteration`` is raised.
        """
        if self._frame_iter is None:
            self._frame_iter = self.container.decode(self._stream)

        try:
            frame = next(self._frame_iter)

            # PURE SEQUENTIAL COUNTING
            actual_index = self._current_index
            self._current_index += 1

            return actual_index, self._apply_rotation(frame.to_ndarray(format="rgb24"))

        except StopIteration:
            raise ValueError(f"End of stream reached for: {self._path}")

    @override
    def __str__(self) -> str:
        """Return string representation showing path, frame count, and FPS."""
        return f"AvVideoReader(path={self._path}: {self.frame_count} frames, {self.fps} fps)"
