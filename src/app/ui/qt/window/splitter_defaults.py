from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _WindowSplitterDefaults:
    main_sizes: tuple[int, int] = (980, 320)
    left_sizes: tuple[int, int] = (620, 230)
    main_stretch: tuple[int, int] = (4, 1)
    left_stretch: tuple[int, int] = (5, 2)
    progress_range: tuple[int, int] = (0, 100)
    handle_width: int = 8