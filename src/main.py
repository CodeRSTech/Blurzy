from __future__ import annotations

import sys

from app.shared.logging_cfg import configure_logging, get_logger
from app.shared.runtime_config import StartupConfig, StartupConfigurationError

logger = get_logger("Main")


def _load_startup_config() -> StartupConfig:
    try:
        return StartupConfig.from_env()
    except StartupConfigurationError as exc:
        print(
            "Blurzy failed to start because startup configuration is invalid: "
            f"{exc}",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc


def main() -> None:
    startup_config = _load_startup_config()
    configure_logging(
        console_level=startup_config.console_level,
        file_level=startup_config.file_level,
        log_file_path=startup_config.log_file_path,
        enabled_areas=startup_config.enabled_areas_for_logging(),
    )
    logger.info(
        "Startup configuration loaded: console_level={} file_level={} area_filter={} log_file_path={}",
        startup_config.console_level,
        startup_config.file_level,
        startup_config.enabled_areas or "<all>",
        startup_config.log_file_path,
    )

    from PySide6.QtWidgets import QApplication

    from app.application.application import Application
    from app.ui.qt.main_window import MainWindow
    from app.ui.qt.shared.qt_debug_repr import apply_custom_qt_reprs
    from app.ui.uicontroller import UIController

    apply_custom_qt_reprs()

    logger.info("Starting the application...")
    q_app = QApplication(sys.argv)

    app = Application()
    window = MainWindow()
    UIController(q_app, window, app)

    window.show()
    sys.exit(q_app.exec())


if __name__ == "__main__":
    main()


# [NOTE] [URGENT] [30-07-2024: 11 PM]
# All class must be based on base classes (such as DetectionResult based on BaseBox / Box)
# On top, there is `app`, `window` and instantiation of `UIController`
#
#   UI Controller is the main character, it also holds refs to app, window and all the handlers
#   So do the Handlers
#
# **Handlers** work with their refs to `_app`, `_window` and `_controller` to do their job
#
# Each of the handlers should have a dedicated interface/protocol/adapter for app, window and controller
#
# for example:
# 'src/app/ui/handlers/detection_handler.py'
# has refs to all three (app, window and controller)
# could use:
# `AppDetectionHandlerInterface`, 'AppDetectionHandlerAdapter`, 'WindowDetectionHandlerInterface', 'WindowDetectionHandlerAdapter', 'ControllerDetectionHandlerInterface', 'ControllerDetectionHandlerAdapter`
#
# [UPDATE] [31-07-2024: 12 AM]
#