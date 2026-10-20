"""CLI argument router, interactive selector, and execution harness for Glaze."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

from glaze import __version__
from glaze.config import load_user_config
from glaze.engine import RenamePlan, execute_renames, resolve_conflicts, scan_directory
from glaze.history import UNDO_LOG_PATH, get_undo_log_path, run_undo, save_undo_log
from glaze.transform import (
    CASE_OPTIONS,
    normalize_words,
    sanitize_filename,
    strip_accents,
    transform_words,
)
from glaze.ui import add_color_args, handle_color_args, ui

__all__ = [
    "main",
    "scan_directory",
    "resolve_conflicts",
    "execute_renames",
    "normalize_words",
    "strip_accents",
    "transform_words",
    "sanitize_filename",
    "CASE_OPTIONS",
    "load_user_config",
    "get_undo_log_path",
    "save_undo_log",
    "run_undo",
    "RenamePlan",
    "UNDO_LOG_PATH",
]


def print_help() -> None:
    """Prints colored usage instructions matching Flaker, Folio, Borealis, and Firn."""
    print(f"""{ui.badge()} {ui.bold("Universal Filename Sanitizer, Case Transformer & Batch Renamer")}

{ui.blue("Usage:")}
  glaze [options]                    Interactive mode (prompts for target format)
  glaze <format> [options]           Batch rename current directory using specific format
  glaze undo [options]               Revert previous batch rename operations

{ui.blue("Case Formats:")}
  --title-snake          Title_Snake_Case (e.g. My_Document_File.pdf) [Default]
  --snake                snake_case (e.g. my_document_file.pdf)
  --kebab                kebab-case (e.g. my-document-file.pdf)
  --pascal               PascalCase (e.g. MyDocumentFile.pdf)
  --camel                camelCase (e.g. myDocumentFile.pdf)
  --lower                lowercase (e.g. mydocumentfile.pdf)
  --upper                UPPERCASE (e.g. MYDOCUMENTFILE.pdf)
  --upper-snake          UPPER_SNAKE_CASE (e.g. MY_DOCUMENT_FILE.pdf)

{ui.blue("Options:")}
  -d, --dir DIR          Target directory to rename files in (default: current directory)
  -e, --ext EXT          Target specific extension only (e.g. -e pdf or -e mp3)
  -r, --recursive        Recursively scan all subdirectories
  --dirs                 Also rename directories in addition to files
  -s, --safe             Strict ASCII mode: strip accents (é->e) & remove special characters
  -a, --all, --hidden    Include hidden / dot-files (always excludes .git)
  -l, --lower-ext        Normalize extensions to lowercase (e.g. .PDF -> .pdf)
  -n, --dry-run          Preview planned renames without executing them
  -y, --yes              Skip interactive confirmation prompt and execute immediately
  --conflict MODE        Conflict resolution: skip, suffix, or abort (default: skip)
  --color MODE           Color output mode: auto, always, never (default: auto)
  --no-color             Disable colored output
  -h, --help             Show this help message and exit
  -V, -v, --version      Show version information and exit

{ui.blue("Undo Commands:")}
  glaze undo             Revert the most recent rename batch
  glaze undo --dry-run   Preview which files would be reverted without renaming
  glaze undo --list      Inspect previous rename log records

{ui.blue("Examples:")}
  glaze                              # Interactive wizard (prompts for case format)
  glaze --snake                      # Convert current folder to snake_case
  glaze --title-snake -e pdf         # Rename only *.pdf files to Title_Snake_Case
  glaze --kebab -r --safe            # Recursive kebab-case with safe ASCII
  glaze --pascal -n                  # Dry-run preview without renaming files
  glaze undo                         # Revert last executed batch rename
""")


def _build_parser(user_cfg: dict[str, Any]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="glaze", add_help=False)
    parser.add_argument("paths", nargs="*", help="Optional specific files or directories to process.")
    parser.add_argument("-d", "--dir", default=".", help="Target directory (Default: current directory).")
    parser.add_argument("-e", "--ext", default=str(user_cfg.get("ext", "*")), help="Filter by file extension.")
    parser.add_argument("-a", "--all", "--include-hidden", "--hidden", dest="include_hidden", action="store_true", default=bool(user_cfg.get("include_hidden", False)))
    parser.add_argument("-s", "--safe", action="store_true", default=bool(user_cfg.get("safe", False)))
    parser.add_argument("-l", "--lower-ext", dest="lower_ext", action="store_true", default=bool(user_cfg.get("lower_ext", True)))
    parser.add_argument("--no-lower-ext", dest="lower_ext", action="store_false")
    parser.add_argument("-r", "--recursive", action="store_true", default=bool(user_cfg.get("recursive", False)))
    parser.add_argument("--dirs", action="store_true", default=bool(user_cfg.get("include_dirs", False)))
    parser.add_argument("-n", "--dry-run", action="store_true")
    parser.add_argument("-y", "--yes", action="store_true")
    parser.add_argument("-i", "--interactive", action="store_true")
    parser.add_argument("--conflict", dest="on_conflict", choices=["skip", "suffix", "abort"], default=str(user_cfg.get("on_conflict", "skip")))
    add_color_args(parser)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument("-V", "-v", "--version", action="store_true")

    case_group = parser.add_mutually_exclusive_group()
    for flag, mode in [
        ("--title-snake", "title_snake"),
        ("--snake", "snake"),
        ("--kebab", "kebab"),
        ("--pascal", "pascal"),
        ("--camel", "camel"),
        ("--lower", "lower"),
        ("--upper", "upper"),
        ("--upper-snake", "upper_snake"),
    ]:
        case_group.add_argument(flag, dest="case_mode", action="store_const", const=mode)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    user_cfg = load_user_config()
    if "color" in user_cfg:
        ui.set_color_mode(str(user_cfg["color"]))
    handle_color_args(raw_args)

    if any(a in ("-h", "--help", "help") for a in raw_args):
        print_help()
        return 0

    if any(a in ("-V", "-v", "--version", "version") for a in raw_args):
        print(f"{ui.badge()} {ui.bold(f'v{__version__}')}")
        return 0

    # Handle 'glaze undo' and 'glaze log'
    if raw_args and raw_args[0] in ("undo", "log"):
        is_list = raw_args[0] == "log" or any(a in ("--list", "-l") for a in raw_args[1:])
        is_dry = any(a in ("-n", "--dry-run") for a in raw_args[1:])
        success = run_undo(dry_run=is_dry, list_only=is_list)
        return 0 if success else 1

    parser = _build_parser(user_cfg)
    args = parser.parse_args(raw_args)

    is_interactive_session = args.interactive or (not raw_args and sys.stdin.isatty())
    target_dir = Path(args.dir).resolve()
    if not target_dir.exists():
        ui.error(f"Directory '{target_dir}' does not exist.")
        return 1

    if is_interactive_session:
        panel_lines = [
            f"{ui.bold('Glaze Version:')}    {ui.bold_cyan(f'v{__version__}')} (Batch Renamer & File Slugifier)",
            f"{ui.bold('Target Directory:')} {ui.cyan(str(target_dir))}",
            f"{ui.bold('Default Mode:')}     {str(user_cfg.get('case_mode', 'title_snake'))} (Filter: {args.ext})",
        ]
        ui.panel("GLAZE BATCH RENAME ENGINE", panel_lines)

    if not args.case_mode and is_interactive_session:
        case_mode = ui.select("Select target case format:", CASE_OPTIONS)
    else:
        case_mode = args.case_mode or str(user_cfg.get("case_mode", "title_snake"))

    scope_str = "recursive" if args.recursive else "current directory"
    safe_str = "Safe ASCII (sanitized)" if args.safe else "standard unicode"
    hidden_str = "all (including hidden)" if args.include_hidden else "standard (hidden skipped)"
    dry_str = ui.yellow("DRY RUN (Simulation)") if args.dry_run else ui.green("LIVE EXECUTION")

    scan_lines = [
        f"{ui.bold('Target Directory:')} {ui.cyan(str(target_dir))}",
        f"{ui.bold('Case Transform:')}   {ui.bold_green(case_mode)} (Filter: {args.ext})",
        f"{ui.bold('Scan Scope:')}       {scope_str} | Hidden: {hidden_str} | Charset: {safe_str}",
        f"{ui.bold('Execution Mode:')}   {dry_str}",
    ]
    ui.panel("GLAZE BATCH RENAME ENGINE", scan_lines)

    plans = scan_directory(
        root=target_dir,
        extension=args.ext,
        case_mode=case_mode,
        safe_ascii=args.safe,
        lower_ext=args.lower_ext,
        recursive=args.recursive,
        include_dirs=args.dirs,
        include_hidden=args.include_hidden,
    )

    if not plans:
        ui.success("All files already match the target format. Nothing to rename.")
        return 0

    try:
        executable_plans, collisions = resolve_conflicts(
            plans=plans,
            on_conflict=args.on_conflict,
            target_dir=target_dir,
        )
    except FileExistsError as exc:
        ui.error(str(exc))
        return 1

    print()
    for p in plans:
        if p in collisions:
            print(f"  {ui.yellow('[COLLISION SKIPPED]')} {ui.dim(repr(p.relative_old))} {ui.yellow('⇸')} target {ui.dim(repr(p.relative_new))} exists")
        else:
            tag = "DIR" if p.is_dir else "FILE"
            print(f"  {ui.dim(f'[{tag}]')} {ui.dim(repr(p.relative_old))} {ui.cyan('→')} {ui.bold_green(p.relative_new)}")

    print()
    ui.info(
        f"Found {ui.bold(str(len(plans)))} item(s) to rename. ({len(collisions)} collisions skipped)",
        symbol="📊",
    )

    if args.dry_run:
        ui.info("Dry-run complete. Re-run without -n to apply renames permanently.", symbol="💡")
        return 0

    if not executable_plans:
        ui.error("No renames can be performed safely without collisions.")
        return 1

    if is_interactive_session and not args.yes:
        confirm = ui.select(
            f"Apply {len(executable_plans)} rename operation(s)?",
            [
                ("yes", f"Yes, apply {len(executable_plans)} rename(s)"),
                ("no", "No, cancel"),
            ],
        )
        if confirm != "yes":
            ui.warn("Aborted by user.")
            return 0

    execute_renames(executable_plans)
    return 0


if __name__ == "__main__":
    sys.exit(main())
