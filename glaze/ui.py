"""Terminal UI interface for Glaze, powered by Rime."""

from __future__ import annotations

from rime import (
    UI,
    Spinner,
    add_color_args,
    apply_color_args,
    confirm_input,
    detect_color_support,
    get_terminal_columns,
    handle_color_args,
    multiselect_menu,
    prompt_input,
    render_error_panel,
    render_panel,
    select_menu,
    spinner_context,
    strip_ansi,
    visual_len,
)

ui = UI(app_name="glaze", icon="✨", badge_color="1;36")

__all__ = [
    "ui",
    "UI",
    "Spinner",
    "spinner_context",
    "detect_color_support",
    "add_color_args",
    "apply_color_args",
    "handle_color_args",
    "render_panel",
    "render_error_panel",
    "prompt_input",
    "confirm_input",
    "select_menu",
    "multiselect_menu",
    "strip_ansi",
    "visual_len",
    "get_terminal_columns",
]
