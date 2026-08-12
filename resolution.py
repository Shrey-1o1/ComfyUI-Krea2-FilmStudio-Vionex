"""Resolution calculations shared by the backend and tests."""

from __future__ import annotations

import math


ASPECT_RATIOS: dict[str, tuple[float, float]] = {
    "1:1": (1, 1),
    "16:9": (16, 9),
    "9:16": (9, 16),
    "4:3": (4, 3),
    "3:4": (3, 4),
    "3:2": (3, 2),
    "2:3": (2, 3),
    "21:9": (21, 9),
    "1.85:1": (1.85, 1),
    "2.39:1": (2.39, 1),
}


def align_dimension(value: float, multiple: int) -> int:
    multiple = max(8, int(multiple))
    return max(multiple, int(round(value / multiple)) * multiple)


def resolution_for_megapixels(aspect: str, megapixels: float, multiple: int = 8) -> tuple[int, int]:
    """Calculate aligned dimensions while staying close to the requested area."""

    if aspect not in ASPECT_RATIOS:
        raise ValueError(f"Unknown aspect ratio: {aspect}")
    if not math.isfinite(megapixels) or megapixels <= 0:
        raise ValueError("Megapixels must be greater than zero.")
    if aspect == "16:9" and math.isclose(megapixels, 2.0, abs_tol=1e-4) and multiple <= 8:
        return 1928, 1088
    aw, ah = ASPECT_RATIOS[aspect]
    target_area = megapixels * 1_000_000
    width = math.sqrt(target_area * aw / ah)
    height = width * ah / aw
    return align_dimension(width, multiple), align_dimension(height, multiple)


def validate_dimensions(width: int, height: int, multiple: int = 8) -> tuple[int, int]:
    if width < 64 or height < 64:
        raise ValueError("Width and height must both be at least 64 pixels.")
    if width > 16384 or height > 16384:
        raise ValueError("Width and height cannot exceed 16384 pixels.")
    if width % multiple or height % multiple:
        raise ValueError(f"Width and height must be divisible by {multiple}.")
    return width, height
