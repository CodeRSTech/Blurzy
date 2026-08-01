from typing import TYPE_CHECKING, final, cast

from PySide6.QtCore import Signal, Slot, Qt, QSignalBlocker
from PySide6.QtWidgets import QWidget, QPushButton, QTableWidget, QTabWidget, QListWidget, \
    QVBoxLayout, QSplitter, QListWidgetItem, QTableWidgetItem

from app.domain import SessionId, VideoDataLayerGroup
from app.shared.logging_cfg import get_logger
from app.ui.qt.utilities.helpers import create_qhbox_with_widgets, post_data_table_init

if TYPE_CHECKING:
    from app.domain.views import SessionFileListViewModel
    from app.domain.base.dtypes import ListOfBoxes

logger = get_logger("UI->Bottom Data Panel")


@final
class BottomDataPanelContainer(QWidget):

    # --- Signals echoed up to the Controller and MainWindow ---
    session_selected = Signal(object)  # Connected to SessionHandler.on_session_selected() method via Controller.
    tab_changed = Signal(int)       # Connected to MainWindow._on_tab_changed() method via MainWindow itself.

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._init_widgets()
        self._build_ui()
        self._initialize_data_panels()
        self._connect_signals()
        self._update_frame_box_buttons_state()

    def _build_ui(self):
        self.data_tab.addTab(self.detection_tab_frame_data_table, "Detected objects")
        self.data_tab.addTab(self.tracker_tab_frame_data_table, "Tracking results")
        self.session_tab.addTab(self.session_file_list, "Opened files")

        bottom_layout = QVBoxLayout(self)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        bottom_splitter.addWidget(self.data_tab)
        bottom_splitter.addWidget(self.session_tab)
        bottom_splitter.setStretchFactor(0, 6)
        bottom_splitter.setStretchFactor(1, 5)

        # Action row 1
        action_row_1 = create_qhbox_with_widgets([
            self.edit_item_btn,
            self.delete_item_btn,
            self.copy_to_prev_btn,
            self.copy_to_next_btn,
        ])
        action_row_1.addStretch()

        # Action row 2
        action_row_2 = create_qhbox_with_widgets([
            self.reset_frame_btn,
            self.reset_all_btn,
            self.reset_tracker_frame_btn,
            self.reset_all_trackers_btn,
            self.delete_next_occurrences_btn,
            self.delete_prev_occurrences_btn,
        ])
        action_row_2.addStretch()

        bottom_layout.addWidget(bottom_splitter)
        bottom_layout.addLayout(action_row_1)
        bottom_layout.addLayout(action_row_2)

    def _init_widgets(self) -> None:
        # --- UI Elements: Data tab (Detected objects, Tracking results) ---
        self.detection_tab_frame_data_table = QTableWidget(0, 6)
        self.tracker_tab_frame_data_table = QTableWidget(0, 6)
        self.data_tab = QTabWidget()

        # --- UI Elements: Action Row 1 ---
        self.edit_item_btn = QPushButton("Edit Selected")
        self.delete_item_btn = QPushButton("Delete Selected")
        self.copy_to_next_btn = QPushButton("Dup To Next")
        self.copy_to_prev_btn = QPushButton("Dup To Prev")

        # --- UI Elements: Action Row 2 ---
        self.reset_frame_btn = QPushButton("Reset Review (Frame)")
        self.reset_all_btn = QPushButton("Reset Review (All)")
        self.reset_tracker_frame_btn = QPushButton("Reset Trackers (Frame)")
        self.reset_all_trackers_btn = QPushButton("Reset Trackers (All)")
        self.delete_next_occurrences_btn = QPushButton("Delete Next Occurrences")
        self.delete_prev_occurrences_btn = QPushButton("Delete Prev Occurrences")

        # --- UI Elements: Opened files (session) ---
        self.session_file_list = QListWidget()
        self.session_tab = QTabWidget()

    def _initialize_data_panels(self) -> None:
        detection_data_table = self.detection_tab_frame_data_table
        detection_data_table.setHorizontalHeaderLabels(
            ["ID", "Source", "Label", "Detection Confidence", "BBox", "Color"])
        post_data_table_init(detection_data_table)

        tracker_data_table = self.tracker_tab_frame_data_table
        tracker_data_table.setHorizontalHeaderLabels(
            ["ID", "Source", "Label", "Tracker Confidence", "BBox", "Color"])
        post_data_table_init(tracker_data_table)


    def _connect_signals(self) -> None:
        session_list = self.session_file_list
        data_tab = self.data_tab
        detection_table = self.detection_tab_frame_data_table
        tracker_table = self.tracker_tab_frame_data_table

        for signal, slot in [(detection_table.itemSelectionChanged, self._update_frame_box_buttons_state),
                             (tracker_table.itemSelectionChanged,   self._update_frame_box_buttons_state),
                             (detection_table.cellClicked,          self._update_frame_box_buttons_state),
                             (tracker_table.cellClicked,            self._update_frame_box_buttons_state),
                             (data_tab.currentChanged,              self._emit_tab_changed),
                             (session_list.itemSelectionChanged,    self._emit_selected_session)
                             ]:
            _ = signal.connect(slot)

    @property
    def active_tab_index(self) -> VideoDataLayerGroup:
        return cast(VideoDataLayerGroup, self.data_tab.currentIndex())

    @property
    def active_frame_data_table(self) -> QTableWidget:
        idx = self.active_tab_index
        if idx == VideoDataLayerGroup.TRACKING:
            return self.tracker_tab_frame_data_table
        elif idx == VideoDataLayerGroup.DETECTION:
            return self.detection_tab_frame_data_table
        else:
            raise NotImplementedError(f"Invalid data tab index: {idx}")

    @property
    def selected_s_id(self) -> SessionId:
        """
        Retrieves the selected session ID from the session list.
        """
        # NOTE: Returns "" (empty string) when no session is selected — callers check for "".
        item: QListWidgetItem | None = self.session_file_list.currentItem()
        if item is not None:  # pyright: ignore[reportUnnecessaryComparison]
            s_id: SessionId = cast(SessionId, item.data(Qt.ItemDataRole.UserRole))
            return s_id
        return SessionId("") # pyright: ignore[reportUnreachable]

    @selected_s_id.setter
    def selected_s_id(self, s_id: SessionId) -> None:
        if not s_id:
            logger.warning("Session ID cannot be empty.")
            return
        # NEW: Using signal blocker to avoid issues.
        with QSignalBlocker(self.session_file_list):
            for index in range(self.session_file_list.count()):
                item = self.session_file_list.item(index)
                if item.data(Qt.ItemDataRole.UserRole) == s_id:
                    self.session_file_list.setCurrentItem(item)
                    break

    @property
    def get_selected_box_keys_from_active_tab(self) -> list[str]:
        table = self.active_frame_data_table    # <- Fetch active data table (Detection/Tracking)
        selection_model = table.selectionModel()
        if selection_model is None:
            return []

        selected_keys = []
        seen_keys = set()

        for index in selection_model.selectedRows():
            id_item = table.item(index.row(), 0)
            if id_item is None:
                continue
            item_key = id_item.data(Qt.ItemDataRole.UserRole)
            if item_key not in seen_keys:
                seen_keys.add(item_key)
                selected_keys.append(item_key)

        return selected_keys

    @Slot()
    def _emit_selected_session(self) -> None:
        item = self.session_file_list.currentItem()
        if item is None:
            return
        s_id = cast(SessionId, item.data(Qt.ItemDataRole.UserRole))
        self.session_selected.emit(s_id)

    @Slot()
    def _emit_tab_changed(self) -> None:
        active_tab_index = self.data_tab.currentIndex()
        self.tab_changed.emit(active_tab_index)

    @Slot()
    def _update_frame_box_buttons_state(self) -> None:
        """
        Enables/Disables certain Buttons based on the number of selected boxes under Detection/Tracking tab.
        """
        num_selected_boxes = len(self.get_selected_box_keys_from_active_tab)

        only_one_selected = num_selected_boxes == 1
        one_or_more_selected = num_selected_boxes >= 1

        self.edit_item_btn.setEnabled(only_one_selected)

        for btn in (self.delete_item_btn,
                    self.copy_to_next_btn,
                    self.copy_to_prev_btn,
                    self.delete_next_occurrences_btn,
                    self.delete_prev_occurrences_btn):
            btn.setEnabled(one_or_more_selected)

    def select_session(self, s_id: SessionId) -> None:
        for index in range(self.session_file_list.count()):
            item = self.session_file_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == s_id:
                self.session_file_list.setCurrentItem(item)
                break

    def update_session_file_list(self, session_list: list[SessionFileListViewModel]) -> None:
        """Updates the list of opened sessions (videos) onto the `session_list` ``QListWidget``."""
        # NEW: Using signal blocker to avoid issues
        with QSignalBlocker(self.session_file_list):
            self.session_file_list.clear()
        for session_file in session_list:
            self.add_session_file_to_list(session_file)

    def add_session_file_to_list(self, session_file: SessionFileListViewModel) -> None:
        logger.trace(
            "Adding session file to list: {}",
            session_file.title
        )
        with QSignalBlocker(self.session_file_list):
            item = QListWidgetItem(session_file.title)
            item.setToolTip(session_file.subtitle)
            item.setData(Qt.ItemDataRole.UserRole, session_file.s_id)
            self.session_file_list.addItem(item)

    def set_tracker_data_boxes(self, boxes: ListOfBoxes) -> None:
        data_table = self.tracker_tab_frame_data_table
        selected_box_keys = set(self.get_selected_box_keys_from_active_tab)
        had_focus = data_table.hasFocus()
        self.set_data_table_boxes(boxes, data_table, selected_box_keys)

        if had_focus:
            data_table.setFocus()

        self._update_frame_box_buttons_state()

    def set_data_boxes_for_tab(self, boxes: ListOfBoxes, tab: VideoDataLayerGroup) -> None:
        """
        Updates the frame detection data table with the provided bounding boxes.
        """
        if tab == VideoDataLayerGroup.DETECTION:
            data_table = self.detection_tab_frame_data_table
        elif tab == VideoDataLayerGroup.TRACKING:
            data_table = self.tracker_tab_frame_data_table
        else:
            raise NotImplementedError(f"Unsupported tab: {tab}")

        # FIXME:
        #  This seems fishy.. why only select detection keys from active tab?
        selected_box_keys = set(self.get_selected_box_keys_from_active_tab)
        had_focus = data_table.hasFocus()

        self.set_data_table_boxes(boxes, data_table, selected_box_keys)

        if had_focus:
            data_table.setFocus()

        self._update_frame_box_buttons_state()

    @staticmethod
    def set_data_table_boxes(boxes: ListOfBoxes, data_table: QTableWidget, selected_box_keys: set[str]):
        with QSignalBlocker(data_table):
            data_table.setRowCount(len(boxes))

            rows_to_select: list[int] = []

            for row_idx, item in enumerate(boxes):
                box_id = QTableWidgetItem(item.id)
                box_id.setData(Qt.ItemDataRole.UserRole, item.key)

                data_table.setItem(row_idx, 0, box_id)

                for col_idx, attr in [(1, 'source'),
                                      (2, 'label'),
                                      (3, 'confidence_txt'),
                                      (4, 'bbox_txt'),
                                      (5, 'color_hex')]:
                    data_table.setItem(row_idx,
                                       col_idx,
                                       QTableWidgetItem(item.__getattribute__(attr)))

                if item.key in selected_box_keys:
                    rows_to_select.append(row_idx)

            data_table.clearSelection()

            for row_idx in rows_to_select:
                data_table.selectRow(row_idx)

            if rows_to_select:
                data_table.setCurrentCell(rows_to_select[0], 0)

    def update_video_related_widgets_state(self, is_enabled: bool = False) -> None:
        pass
        #for widget in (self.reset_frame_btn,
        #            self.reset_all_btn,
        #            self.reset_tracker_frame_btn,
        #            self.reset_all_trackers_btn,
        #            self.data_tab):
        #    widget.setEnabled(is_enabled)

        # [INFO] [NOTE]
        # IMPLEMENT THIS
        # WHEN `DetectionWorker` has completed and the cache has been synced
        #
        #  - In MainWindow:
        #      def set_detection_worker_complete_state(self, complete: bool) -> None:
        #         self.bottom_panel.set_detection_worker_complete_state(complete)
        #
        #  - In Controller:
        #      def _connect_and_deploy_detection_thread_and_worker(self,
        #                                                     detection_thread: QThread, detection_worker: ModelLoadWorker
        #                                                     ) -> None:
        #         _ = detection_thread.started.connect(model_load_worker.run)
        #         _ = detection_thread.finished.connect(self.cleanup_detection_synced)
        #
        #  Ensure that `app.sync_detection_cache()` has been run after DetectionWorker.is_complete()
        #
        #  Once DetectionWorker is complete and cache is synced, enable:
        #               self.reset_frame_btn,
        #               self.reset_all_btn,
        #
        #  And, similarly, when tracking is complete, enable:
        #            self.reset_tracker_frame_btn,
        #            self.reset_all_trackers_btn
