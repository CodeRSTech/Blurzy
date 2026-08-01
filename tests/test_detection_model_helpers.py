Delegate to a dedicated playback service or expand SessionService
        self.session_svc.start_session_playback(s_id=s_id)

    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
    #               LAYER IMPORT / EXPORT DELEGATION METHODS
    # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════

    # Used by ImportExportHandler
    def import_layer(
        self,
        s_id: SessionId,
        layer: VideoDataLayer | str,
        file_path: str,
        mode: ImportMode | str,
    ) -> int:
        """
        Import bounding-box data from ``file_path`` into ``layer`` for ``s_id``.

        Dispatches to :class:`DetectionImportService` for layers A/B and
        :class:`TrackingImportService` for layers C/D.

        Args:
            s_id:      Target session.
            layer:     Target layer (as enum or string; coerced to enum).
            file_path: Path to import file.
            mode:      Merge strategy (enum or string; coerced to enum).

        Returns:
            int: Number of boxes written into the layer.

        Note:
            Accepts string layer names to handle Qt signal/slot type coercion.
        """
        layer = ensure_layer_enum(layer)
        mode = ensure_import_mode(mode)
        from app.domain.video.layer import VideoDataLayer as _L
        if layer in (_L.A, _L.B):
            return self.detection_import_svc.import_layer(s_id, layer, file_path, mode)
        return self.tracking_import_svc.import_layer(s_id, layer, file_path, mode)

    # Used by ImportExportHandler
    def export_layer(
        self,
        s_id: SessionId,