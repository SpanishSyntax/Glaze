"""Terminal UI and ANSI styling for Glaze."""

import os
import sys


class UI:
    def __init__(self, app_name: str = "glaze", icon: str = "✨", badge_color: str = "1;36"):
        self.app_name = app_name
        self.icon = icon
        self.badge_color = badge_color

    @property
    def use_color(self) -> bool:
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
        print(self.status(symbol, msg, "1;36"))

    def warn(self, msg: str):
        print(self.status("⚠️", msg, "1;33"))

    def error(self, msg: str):
        print(self.status("✘", msg, "1;31"), file=sys.stderr)

    def action(self, msg: str, symbol: str = "⚡"):
        print(self.status(symbol, msg, "1;36"))

    def header(self, title: str, width: int = 76):
        border = self.bold_cyan("=" * width)
        print(f"\n{border}\n {self.bold(title)}\n{border}")

    def subheader(self, title: str, width: int = 76):
        rule_part = self.dim("-" * max(0, width - len(title) - 5))
        print(f"\n{self.bold_cyan(f'--- {title}')} {rule_part}")


ui = UI()
