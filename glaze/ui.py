"""Terminal UI, ANSI styling, and robust interactive menu engine for CLI tools."""

import os
import re
import select
import shutil
import sys
import termios
import tty
from typing import Any, Sequence

ANSI_REGEX = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Strips ANSI escape codes to measure true visual character length."""
    return ANSI_REGEX.sub("", text)


class UI:
    def __init__(self, app_name: str = "glaze", icon: str = "✨", badge_color: str = "1;36"):
        self.app_name = app_name
        self.icon = icon
        self.badge_color = badge_color
        self._color_mode = "auto"

    def set_color_mode(self, mode: str):
        self._color_mode = mode.lower()

    @property
    def use_color(self) -> bool:
        if self._color_mode == "never":
            return False
        if self._color_mode == "always":
            return True
        if "NO_COLOR" in os.environ:
            return False
        if os.environ.get("CLICOLOR_FORCE", "0") != "0" or "FORCE_COLOR" in os.environ:
            return True
        return sys.stdout.isatty() or os.environ.get("COLORTERM") in ("truecolor", "24bit")

    def style(self, text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.use_color else text

    def bold(self, text: str) -> str:
        return self.style(text, "1")

    def dim(self, text: str) -> str:
        return self.style(text, "90")

    def blue(self, text: str) -> str:
        return self.style(text, "1;34")

    def cyan(self, text: str) -> str:
        return self.style(text, "0;36")

    def bold_cyan(self, text: str) -> str:
        return self.style(text, "1;36")

    def green(self, text: str) -> str:
        return self.style(text, "0;32")

    def bold_green(self, text: str) -> str:
        return self.style(text, "1;32")

    def yellow(self, text: str) -> str:
        return self.style(text, "1;33")

    def red(self, text: str) -> str:
        return self.style(text, "1;31")

    def magenta(self, text: str) -> str:
        return self.style(text, "1;35")

    def badge(self) -> str:
        return self.style(f"{self.icon} [{self.app_name}]", self.badge_color)

    def status(self, symbol: str, message: str, code: str = "1") -> str:
        return f"{self.badge()} {self.style(f'{symbol} {message}', code)}"

    def success(self, msg: str):
        print(self.status("✔", msg, "1;32"))

    def info(self, msg: str, symbol: str = "ℹ️"):
        print(self.status(symbol, msg, "1;34"))

    def warn(self, msg: str):
        print(self.status("⚠️", msg, "1;33"))

    def error(self, msg: str):
        print(self.status("✘", msg, "1;31"), file=sys.stderr)

    def action(self, msg: str, symbol: str = "⚡"):
        print(self.status(symbol, msg, "0;36"))

    def header(self, title: str, width: int = 76):
        border = self.blue("=" * width)
        print(f"\n{border}\n {self.bold(title)}\n{border}")

    def subheader(self, title: str, width: int = 76):
        rule_part = self.dim("-" * max(0, width - len(title) - 5))
        print(f"\n{self.cyan(f'--- {title}')} {rule_part}")

    # -------------------------------------------------------------------------
    # Robust Terminal Engine (Arrow Keys & Non-Wrapping Width Handling)
    # -------------------------------------------------------------------------
    def _read_key(self) -> str:
        """
        Reads a single raw keypress or ANSI escape sequence directly from stdin.
        Uses os.read() without TextIOWrapper buffering to ensure escape sequences
        arrive atomically and reliably in modern terminal emulators (Kitty, Alacritty, etc.).
        """
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            raw = os.read(fd, 32)
            if not raw:
                return "ctrl_d"

            # Check if this is an escape sequence
            if raw == b"\x1b":
                # Check if more bytes are pending in the kernel pty buffer
                r, _, _ = select.select([fd], [], [], 0.025)
                if r:
                    raw += os.read(fd, 32)
                else:
                    return "esc"

            # Arrow keys & cursor navigation:
            # Handles \x1b[A, \x1bOA (application mode), \x1b[1;2A, \x1b[[A, etc.
            if raw.startswith(b"\x1b") and raw.endswith(b"A"):
                return "up"
            if raw.startswith(b"\x1b") and raw.endswith(b"B"):
                return "down"
            if raw.startswith(b"\x1b") and raw.endswith(b"C"):
                return "right"
            if raw.startswith(b"\x1b") and raw.endswith(b"D"):
                return "left"

            # Enter, space, vim navigation, controls
            if raw in (b"\r", b"\n"):
                return "enter"
            if raw == b" ":
                return "space"
            if raw == b"\x03":  # Ctrl+C
                return "ctrl_c"
            if raw == b"\x04":  # Ctrl+D
                return "ctrl_d"
            if raw in (b"k", b"K"):
                return "up"
            if raw in (b"j", b"J"):
                return "down"
            if raw in (b"a", b"A"):
                return "a"
            if raw in (b"q", b"Q"):
                return "q"

            return raw.decode("utf-8", errors="ignore")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    @staticmethod
    def _fit_line(prefix: str, label_styled: str, label_plain: str, desc: str, max_w: int) -> str:
        """
        Ensures a menu item line never exceeds max_w visual columns.
        Prevents terminal wrapping so cursor up/down operations remain 100% in sync.
        """
        prefix_len = len(strip_ansi(prefix))
        avail = max_w - prefix_len
        if avail <= 5:
            return prefix + label_plain[:max(0, avail)]

        if not desc:
            if len(label_plain) <= avail:
                return f"{prefix}{label_styled}"
            return f"{prefix}{label_plain[:max(0, avail - 3)]}..."

        # Both label and desc present
        if len(label_plain) + 2 + len(desc) <= avail:
            return f"{prefix}{label_styled} \033[90m{desc}\033[0m"

        # Fit label and truncated description
        if len(label_plain) + 6 <= avail:
            rem = avail - len(label_plain) - 4
            trunc_desc = desc[:max(0, rem)] + "..."
            return f"{prefix}{label_styled} \033[90m{trunc_desc}\033[0m"

        # Narrow terminal: label only
        if len(label_plain) <= avail:
            return f"{prefix}{label_styled}"
        return f"{prefix}{label_plain[:max(0, avail - 3)]}..."

    @staticmethod
    def _normalize_options(options: Sequence[Any]) -> list[tuple[str, str, str]]:
        """
        Normalizes option entries into (key, label, description).
        Accepts:
          - "name" -> (name, name, "")
          - ("key", "label") -> (key, label, "")
          - ("key", "label", "description") -> (key, label, description)
        """
        result = []
        for opt in options:
            if isinstance(opt, (list, tuple)):
                if len(opt) == 1:
                    result.append((str(opt[0]), str(opt[0]), ""))
                elif len(opt) == 2:
                    result.append((str(opt[0]), str(opt[1]), ""))
                else:
                    result.append((str(opt[0]), str(opt[1]), str(opt[2])))
            else:
                result.append((str(opt), str(opt), ""))
        return result

    def select(
        self,
        title: str,
        options: Sequence[Any],
        default_index: int = 0,
    ) -> str:
        """
        Single-select interactive menu with arrow key navigation.
        Width & height aware: truncates wide lines and paginates lists to fit any terminal size.
        """
        items = self._normalize_options(options)
        if not items:
            return ""

        # Fallback for non-interactive / non-TTY
        if not sys.stdin.isatty():
            print(f"\n{self.badge()} {self.bold(title)}")
            for idx, (k, lbl, desc) in enumerate(items, 1):
                extra = f" - {desc}" if desc else ""
                print(f"  [{idx}] {lbl}{extra}")
            ans = input("Choice [1]: ").strip()
            if ans.isdigit() and 1 <= int(ans) <= len(items):
                return items[int(ans) - 1][0]
            return items[0][0]

        current = max(0, min(default_index, len(items) - 1))
        scroll_offset = 0
        rendered_lines = 0

        # Hide cursor
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        try:
            while True:
                term_size = shutil.get_terminal_size(fallback=(80, 24))
                cols, term_rows = term_size.columns, term_size.lines
                max_w = max(25, cols - 1)

                # Available vertical rows for items
                max_visible = max(3, min(len(items), term_rows - 5, 10))

                # Keep active item inside scroll window
                if current < scroll_offset:
                    scroll_offset = current
                elif current >= scroll_offset + max_visible:
                    scroll_offset = current - max_visible + 1
                scroll_offset = max(0, min(scroll_offset, max(0, len(items) - max_visible)))

                lines = []
                # Header
                raw_title = f"{self.badge()} {self.bold(title)}"
                lines.append(raw_title if len(strip_ansi(raw_title)) <= max_w else raw_title[:max_w])

                # Subtitle navigation hint
                raw_help = self.dim("  (Use ↑/↓ or j/k to navigate, Enter to select, q/Ctrl+C to cancel)")
                lines.append(raw_help if len(strip_ansi(raw_help)) <= max_w else self.dim("  (↑/↓: navigate, Enter: select)"))
                lines.append("")

                # Up indicator if scrolled
                if scroll_offset > 0:
                    lines.append(self.dim(f"  ▲ ({scroll_offset} more above...)"))

                # Visible items
                visible_items = items[scroll_offset : scroll_offset + max_visible]
                for idx_offset, (key, label, desc) in enumerate(visible_items):
                    actual_idx = scroll_offset + idx_offset
                    if actual_idx == current:
                        pointer = self.bold_cyan("❯")
                        styled_lbl = self.bold_cyan(label)
                    else:
                        pointer = " "
                        styled_lbl = label

                    prefix = f"  {pointer} "
                    lines.append(self._fit_line(prefix, styled_lbl, label, desc, max_w))

                # Down indicator if more below
                if scroll_offset + max_visible < len(items):
                    remaining = len(items) - (scroll_offset + max_visible)
                    lines.append(self.dim(f"  ▼ ({remaining} more below...)"))

                # Clear previous frame rows and redraw in-place
                if rendered_lines > 0:
                    sys.stdout.write(f"\033[{rendered_lines}A\r")
                for line in lines:
                    sys.stdout.write(f"\033[2K{line}\r\n")
                sys.stdout.flush()
                rendered_lines = len(lines)

                key = self._read_key()
                if key == "up":
                    current = (current - 1) % len(items)
                elif key == "down":
                    current = (current + 1) % len(items)
                elif key == "enter":
                    break
                elif key in ("ctrl_c", "ctrl_d", "q", "esc"):
                    if rendered_lines > 0:
                        sys.stdout.write(f"\033[{rendered_lines}A\r")
                        for _ in range(rendered_lines):
                            sys.stdout.write("\033[2K\r\n")
                        sys.stdout.write(f"\033[{rendered_lines}A\r")
                        sys.stdout.flush()
                    print("\nAborted.")
                    sys.exit(0)

            # Clear interactive frame cleanly and output final choice
            sys.stdout.write(f"\033[{rendered_lines}A\r")
            for _ in range(rendered_lines):
                sys.stdout.write("\033[2K\r\n")
            sys.stdout.write(f"\033[{rendered_lines}A\r")
            print(f"{self.badge()} {self.dim(title)} {self.bold_green(items[current][1])}")
            sys.stdout.flush()
            return items[current][0]
        finally:
            # Restore cursor
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()

    def multiselect(
        self,
        title: str,
        options: Sequence[Any],
        preselected: Sequence[str] | set[str] | None = None,
    ) -> list[str]:
        """
        Multi-select interactive menu with arrow key navigation and spacebar toggling.
        Width & height aware: truncates wide lines and paginates lists to fit any terminal size.
        """
        items = self._normalize_options(options)
        if not items:
            return []

        selected_keys: set[str] = set(preselected) if preselected else set()

        # Fallback for non-interactive / non-TTY
        if not sys.stdin.isatty():
            print(f"\n{self.badge()} {self.bold(title)}")
            for idx, (k, lbl, desc) in enumerate(items, 1):
                mark = "[*]" if k in selected_keys else "[ ]"
                extra = f" - {desc}" if desc else ""
                print(f"  {mark} [{idx}] {lbl}{extra}")
            ans = input("Select numbers (comma/space separated): ").strip()
            chosen = []
            for tok in ans.replace(",", " ").split():
                if tok.isdigit() and 1 <= int(tok) <= len(items):
                    chosen.append(items[int(tok) - 1][0])
            return chosen if chosen else list(selected_keys)

        current = 0
        scroll_offset = 0
        rendered_lines = 0

        # Hide cursor
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        try:
            while True:
                term_size = shutil.get_terminal_size(fallback=(80, 24))
                cols, term_rows = term_size.columns, term_size.lines
                max_w = max(25, cols - 1)

                # Available vertical rows for items
                max_visible = max(3, min(len(items), term_rows - 5, 10))

                # Keep active item inside scroll window
                if current < scroll_offset:
                    scroll_offset = current
                elif current >= scroll_offset + max_visible:
                    scroll_offset = current - max_visible + 1
                scroll_offset = max(0, min(scroll_offset, max(0, len(items) - max_visible)))

                lines = []
                raw_title = f"{self.badge()} {self.bold(title)}"
                lines.append(raw_title if len(strip_ansi(raw_title)) <= max_w else raw_title[:max_w])

                raw_help = self.dim("  (↑/↓: navigate, Space: toggle, a: all, Enter: confirm, q/Ctrl+C: cancel)")
                lines.append(raw_help if len(strip_ansi(raw_help)) <= max_w else self.dim("  (↑/↓: nav, Space: toggle, Enter: ok)"))
                lines.append("")

                # Up indicator if scrolled
                if scroll_offset > 0:
                    lines.append(self.dim(f"  ▲ ({scroll_offset} more above...)"))

                # Visible items
                visible_items = items[scroll_offset : scroll_offset + max_visible]
                for idx_offset, (key, label, desc) in enumerate(visible_items):
                    actual_idx = scroll_offset + idx_offset
                    is_checked = key in selected_keys
                    check = self.bold_green("[✔]") if is_checked else self.dim("[ ]")

                    if actual_idx == current:
                        pointer = self.bold_cyan("❯")
                        styled_lbl = self.bold_cyan(label) if is_checked else self.bold(label)
                    else:
                        pointer = " "
                        styled_lbl = self.green(label) if is_checked else label

                    prefix = f"  {pointer} {check} "
                    lines.append(self._fit_line(prefix, styled_lbl, label, desc, max_w))

                # Down indicator if more below
                if scroll_offset + max_visible < len(items):
                    remaining = len(items) - (scroll_offset + max_visible)
                    lines.append(self.dim(f"  ▼ ({remaining} more below...)"))

                # Clear previous frame rows and redraw in-place
                if rendered_lines > 0:
                    sys.stdout.write(f"\033[{rendered_lines}A\r")
                for line in lines:
                    sys.stdout.write(f"\033[2K{line}\r\n")
                sys.stdout.flush()
                rendered_lines = len(lines)

                key = self._read_key()
                if key == "up":
                    current = (current - 1) % len(items)
                elif key == "down":
                    current = (current + 1) % len(items)
                elif key == "space":
                    cur_key = items[current][0]
                    if cur_key in selected_keys:
                        selected_keys.remove(cur_key)
                    else:
                        selected_keys.add(cur_key)
                elif key == "a":
                    if len(selected_keys) == len(items):
                        selected_keys.clear()
                    else:
                        selected_keys = {k for k, _, _ in items}
                elif key == "enter":
                    break
                elif key in ("ctrl_c", "ctrl_d", "q", "esc"):
                    if rendered_lines > 0:
                        sys.stdout.write(f"\033[{rendered_lines}A\r")
                        for _ in range(rendered_lines):
                            sys.stdout.write("\033[2K\r\n")
                        sys.stdout.write(f"\033[{rendered_lines}A\r")
                        sys.stdout.flush()
                    print("\nAborted.")
                    sys.exit(0)

            # Clear interactive frame cleanly and output final choice
            sys.stdout.write(f"\033[{rendered_lines}A\r")
            for _ in range(rendered_lines):
                sys.stdout.write("\033[2K\r\n")
            sys.stdout.write(f"\033[{rendered_lines}A\r")
            chosen_labels = [lbl for k, lbl, _ in items if k in selected_keys]
            print(f"{self.badge()} {self.dim(title)} {self.bold_green(', '.join(chosen_labels) if chosen_labels else 'none')}")
            sys.stdout.flush()
            return [k for k, _, _ in items if k in selected_keys]
        finally:
            # Restore cursor
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()


ui = UI()
