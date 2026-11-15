"""Replay viewer: turns a replay into one self-contained HTML page that steps through every event.

Each step carries the engine's own state right after that event (captured while the battle plays), so what
you see is what the engine holds, not a reconstruction from the log.
"""
from .build import build_frames, render_html, write_html  # noqa: F401
