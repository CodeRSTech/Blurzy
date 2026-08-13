"""Video export service for rendering blurred videos and detection exports."""

from __future__ import annotations

import csv
import os
from collections.abc import Callable
from typing import TYPE_CHECKING, final, override

import cv2
import numpy as np
from PySide6.QtCore import QObject

from app.application.adapters import ApplicationAdapter
from app.domain import VideoDataLayer

from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from app.domain import SessionId, BBoxXYXYTuple
    from app.infrastructure.session.session import Session


logger = get_logger("Application->ExportService")

if TYPE_CHECKING:
    from app.application.application import Application

type ExportProgressCallback = Callable[[int, int], None]


@final
class ExportService(QObject):
    """
    Orchestrates video export.

    Responsibilities:
        - Render blurred video with bounding boxes from ``DataLayer.D``.
        - Export annotations as JSON (structured metadata).
        - Export annotations as CSV (spreadsheet format).
        - Report progress during multi-frame export.
        - Apply blur effects to detected/tracked regions.

    Note:
        Populates Layer D data Just-in-time during the process.

        Export Formats:
            Video — MP4 with blur overlay, H.264 codec, original FPS/resolution.
            JSON — Metadata per frame: frame_index, timestamp, boxes with labels/confidence.
            CSV — Tab-separated: frame_index, box_id, label, coords, confidence, source.

        Designed to run in background thread (``ExportWorker``) via progress callbacks.
        Processes entire video frame-by-frame (can be slow).
        Blur strength controlled via session settings.
        Exports ``DataLayer.D`` (user-edited tracking/detection final results).

        Applies Gaussian blur to regions within bounding boxes.
        Strength (sigma) configurable via ``ProcessingSettings.blur_strength``.
        Uses OpenCV ``cv2.GaussianBlur()`` with adaptive kernel size.
    """

    def __init__(self, app: Application) -> None:
        super().__init__(parent=app)
        # self._app = app
        self._app_adapter = ApplicationAdapter(app)

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def session_is_ready_for_export(self, s_id: SessionId) -> bool:
        """
        Check if a session has data ready to export.
    
        Args:
            s_id (SessionId): Session ID.
    
        Returns:
            bool: ``True`` if session can be exported, ``False`` if no valid data.
    
        Note:
            Export favors editable tracking output (Layer D). For sessions where
            Layer D has not been seeded yet, raw tracking output (Layer C) is
            accepted as a fallback.
        """
        session = self._app_adapter.get_session_by_id(s_id)
        return session.has_boxes_for_layer(VideoDataLayer.D) or session.has_boxes_for_layer(VideoDataLayer.C)

    def export_session(
            self, s_id: SessionId, output_path: str, progress_callback: ExportProgressCallback | None = None
    ) -> None:
        """
        Export session to a blurred MP4 video file.
    
        Args:
            s_id (SessionId): Session ID to export.
            output_path (str): File path for output video (e.g., "/path/video_exported.mp4").
            progress_callback (ExportProgressCallback | None): Optional callback ``fn(current_frame, total_frames)`` for progress updates.
    
        Example:
            ::

                export_service.export_session(
                    s_id=session_id,
                    output_path="/home/user/videos/output.mp4",
                    progress_callback=lambda cur, total: print(f"{cur}/{total}")
                )
            # Creates: output.mp4
    
        Note:
            Output Files Generated:
                ``{output_path}`` — Blurred video (MP4).
    
            Flow:
                export_session(s_id, output_path, progress_callback)
                  └──> Render blurred video with progress callback
        """
        # ====================================================================
        # 1. GET SESSION INSTANCE
        # ====================================================================
        session = self._app_adapter.get_session_by_id(s_id)
        if not self.session_is_ready_for_export(s_id):
            raise RuntimeError(f"Session '{s_id}' has no tracking data to export.")

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # ====================================================================
        # 2. RENDER BLURRED VIDEO WITH BOXES
        # ====================================================================
        self._render_blurred_video(session, output_path, progress_callback)

        logger.info("Export complete for session '{}': {}", s_id, output_path)

    def _render_blurred_video(
            self, session: Session, output_path: str, progress_callback: ExportProgressCallback | None = None
    ) -> None:
        export_layer = self._resolve_export_layer(session)
        m = session.state.metadata
        if hasattr(cv2, "VideoWriter_fourcc"):
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(output_path, fourcc, m.fps, (m.width, m.height))

            if not writer.isOpened():
                raise RuntimeError(f"Could not open VideoWriter for: {output_path}")

            try:
                for frame_index in range(m.frame_count):
                    frame = session.video_reader.read_frame_at_index(frame_index)
                    if frame is None or not isinstance(frame, np.ndarray):
                        logger.warning("Null frame at index {} — skipping", frame_index)
                        continue
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                    boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(layer=export_layer,
                                                                                    frame_index=frame_index)
                    if session.state.settings.blur_enabled:
                        for item in boxes:
                            frame = self._blur_region(
                                frame,
                                item.bbox_xyxy,
                                session.state.settings.blur_strength)

                    writer.write(frame)

                    if progress_callback is not None:
                        progress_callback(frame_index + 1, m.frame_count)

            finally:
                writer.release()

            logger.info("Blurred video written to {}", output_path)
            return
        else:  # VideoWriter_fourcc not available in OpenCV
            logger.warning("OpenCV version is too old to write blurred video")
            raise RuntimeError("OpenCV version is too old to write blurred video")

    @staticmethod
    def _resolve_export_layer(session: Session) -> VideoDataLayer:
        if session.has_boxes_for_layer(VideoDataLayer.D):
            return VideoDataLayer.D
        if session.has_boxes_for_layer(VideoDataLayer.C):
            return VideoDataLayer.C
        raise RuntimeError(f"Session '{session.s_id}' has no tracking data in Layer C or Layer D.")

    # [NOTE] : This method began glitching and had to be disabled

    # def export_annotations_json(self, s_id: SessionId, output_path: str) -> None:
    #     session = self._app_adapter.get_session_by_id(s_id)
    #     session_state = session.view_state
    #     frames: dict[str, list[dict[str, object]]] = {}
    #     data: dict[str, object] = {
    #         "s_id": session_state.s_id,
    #         "metadata": {
    #             "width": session_state.metadata.width,
    #             "height": session_state.metadata.height,
    #             "fps": session_state.metadata.fps,
    #             "frame_count": session_state.metadata.frame_count,
    #         },
    #         "frames": frames,
    #     }
    #
    #     for frame_index, boxes in sorted(
    #             session.data.get_all_boxes_for_layer_as_dict_of_lists(layer=DataLayer.C).items()):
    #         frames[str(frame_index)] = [
    #             {
    #                 "item_id": i.id,
    #                 "source": i.source,
    #                 "label": i.label,
    #                 "bbox_xyxy": list(i.bbox_xyxy),
    #                 "confidence": i.confidence,
    #                 "color_hex": i.color_hex,
    #             }
    #             for i in boxes
    #         ]
    #
    #     os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    #     try:
    #         with open(output_path, "w", encoding="utf-8") as f:
    #             json.dump(data, f, indent=2)
    #     except TypeError:
    #         logger.opt(exception=True).error("Failed to export annotations JSON to {}", output_path)
    #         raise RuntimeError("Failed to export annotations JSON to {}", output_path)
    #
    #     logger.info("JSON annotations written to {}", output_path)

    @staticmethod
    def _blur_region(frame: np.ndarray, bbox_xyxy: BBoxXYXYTuple, strength: float) -> np.ndarray:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox_xyxy
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return frame

        ksize = max(3, int(strength) | 1)  # must be odd and >= 3
        roi = frame[y1:y2, x1:x2]
        blurred = cv2.GaussianBlur(roi, (ksize, ksize), 0)
        frame[y1:y2, x1:x2] = blurred
        return frame

    def export_annotations_csv(self, s_id: SessionId, output_path: str) -> None:
        session_state = self._app_adapter.get_session_by_id(s_id).state
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["frame_index", "item_id", "source", "label", "x1", "y1", "x2", "y2", "confidence", "color_hex"]
            )
            for frame_index, boxes in sorted(session_state.items()):
                for i in boxes:
                    x1, y1, x2, y2 = i.bbox_xyxy
                    writer.writerow(
                        [
                            frame_index,
                            i.id,
                            i.source,
                            i.label,
                            x1,
                            y1,
                            x2,
                            y2,
                            "" if i.confidence is None else f"{i.confidence:.4f}",
                            i.color_hex,
                        ]
                    )

        logger.info("CSV annotations written to {}", output_path)
