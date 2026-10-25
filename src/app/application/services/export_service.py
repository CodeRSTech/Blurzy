"""
Video export service for rendering blurred videos and detection exports.

See Also:
    - [`ExportWorkerFactoryAdapter`][app.application.adapters.export_worker_factory_adapter.ExportWorkerFactoryAdapter] — creates session export workers
    - [`ExportAllWorkerFactoryAdapter`][app.application.adapters.export_all_worker_factory_adapter.ExportAllWorkerFactoryAdapter] — creates batch export workers

Layer: Application.
Context: Coordinates domain state and infrastructure to complete application use cases.
"""

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
from app.shared.masked_blur import apply_masked_blur
if TYPE_CHECKING:
    from app.domain import SessionId, BBoxViewModel
    from app.infrastructure.session.session import Session
    from app.application.application import Application


logger = get_logger("Application->ExportService")

type ExportProgressCallback = Callable[[int, int], None]


@final
class ExportService(QObject):
    """
    Orchestrates video export.

    Responsibilities:
        - Render blurred video with bounding boxes from `DataLayer.D`.
        - Export annotations as JSON (structured metadata).
        - Export annotations as CSV (spreadsheet format).
        - Report progress during multi-frame export.
        - Apply blur effects to detected/tracked regions.

    Note:
        Prefers Layer D when populated and falls back to Layer C for unseeded sessions.

        Export Formats:
            Video — MP4 with blur overlay, H.264 codec, original FPS/resolution.
            JSON — Metadata per frame: frame_index, timestamp, boxes with labels/confidence.
            CSV — Tab-separated: frame_index, box_id, label, coords, confidence, source.

        Designed to run in background thread (`ExportWorker`) via progress callbacks.
        Processes entire video frame-by-frame (can be slow).
        Blur strength controlled via session settings.
        Exports `DataLayer.D` (user-edited tracking/detection final results).

        Blurs the union of bounding boxes once with a 10-pixel outward feather.
        Kernel size is configurable via `ProcessingSettings.blur_strength`.
        Selected box interiors remain fully blurred; editor preview is unchanged.



    Args:
        app: Application used to resolve the session, read its frames, and coordinate video export.
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
            bool: `True` if session can be exported, `False` if no valid data.

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
            progress_callback (ExportProgressCallback | None): Optional callback `fn(current_frame, total_frames)` for progress updates.

        Example:
            ```python
            export_service.export_session(
                s_id=session_id,
                output_path="/home/user/videos/output.mp4",
                progress_callback=lambda cur, total: print(f"{cur}/{total}")
            )
            ```

        Note:
            Output Files Generated:
                `{output_path}` — Blurred video (MP4).

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
                    if session.state.settings.blur_enabled and boxes:
                        frame = self._apply_masked_blur(
                            frame, boxes, session.state.settings.blur_strength
                        )

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
    def _apply_masked_blur(
        frame: np.ndarray, boxes: list[BBoxViewModel], strength: float
    ) -> np.ndarray:
        """
        Apply shared feathered Gaussian blur to export pixels.
        """
        return apply_masked_blur(frame, boxes, strength)

    def export_annotations_csv(self, s_id: SessionId, output_path: str) -> None:
        """
        Write the session's stored boxes to a CSV file.

        Args:
            s_id: Identifier of the session whose boxes should be exported.
            output_path: Destination path for the CSV file.
        """
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
