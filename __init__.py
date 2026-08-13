"""KREA 2 · One Node for ComfyUI."""

import logging

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from . import server as _server  # noqa: F401 - registers local PromptServer routes

WEB_DIRECTORY = "./web"

_studio_logger = logging.getLogger("Krea2FilmStudio")
_studio_logger.setLevel(logging.INFO)
_studio_logger.info(
    "Krea 2 Film Studio by VIONEX loaded: native KSampler and RES4LYF film workflows are ready."
)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
