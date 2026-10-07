import argparse
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from glaze.ui import ui


@dataclass
class RenamePlan:
    original: Path
    new_path: Path
    relative_old: str
    relative_new: str
    is_dir: bool = False


def normalize_words(name: str) -> list[str]:
    """
    Splits camelCase, PascalCase, snake_case, kebab-case, dots, and spaced strings
    into a clean list of words.
    """
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    s = re.sub(r"[_.\-—–/]+", " ", s)
    s = re.sub(r"[,;:\\()\[\]{}'\"`~!@#$%^&*+=|<>?]+", " ", s)
    return [w for w in s.strip().split() if w]


def strip_accents(text: str) -> str:
    """Decomposes Unicode characters to remove diacritics (e.g., 'Café' -> 'Cafe')."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def transform_words(words: list[str], case_mode: str) -> str:
    """Transforms a list of words into the requested case mode."""
    if not words:
        return ""

    if case_mode == "title_snake":
        return "_".join(w.capitalize() for w in words)
    elif case_mode == "snake":
        return "_".join(w.lower() for w in words)
    elif case_mode == "upper_snake":
        return "_".join(w.upper() for w in words)
    elif case_mode == "kebab":
        return "-".join(w.lower() for w in words)
    elif case_mode == "pascal":
        return "".join(w.capitalize() for w in words)
    elif case_mode == "camel":
        return words[0].lower() + "".join(w.capitalize() for w in words[1:])
    elif case_mode == "lower":
        return "".join(w.lower() for w in words)
    elif case_mode == "upper":
        return "".join(w.upper() for w in words)
    return "_".join(words)


def sanitize_filename(
    stem: str,
    ext: str,
    case_mode: str,
    safe_ascii: bool,
    lower_ext: bool,
) -> str:
    """Applies case transformation and sanitization rules to a filename."""
    if safe_ascii:
        stem = strip_accents(stem)

    words = normalize_words(stem)
    if not words:
        return ""

    new_base = transform_words(words, case_mode)

    if safe_ascii:
        new_base = re.sub(r"[^a-zA-Z0-9_\-]", "", new_base)

    # Collapse repeated delimiters and trim edge delimiters
    new_base = re.sub(r"_+", "_", new_base)
    new_base = re.sub(r"-+", "-", new_base)
    new_base = new_base.strip("_-")

    if not new_base:
        return ""

    if ext:
        final_ext = ext.lower() if lower_ext else ext
        return f"{new_base}.{final_ext}"
    return new_base


def get_undo_log_path() -> Path:
    """Returns the path to the undo log in ~/.cache/glaze/last_run.json."""
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "glaze"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "last_run.json"


def save_undo_log(operations: list[tuple[str, str]]):
    """Saves executed rename operations for potential undo."""
    log_file = get_undo_log_path()
    data = [{"old": old, "new": new} for old, new in operations]
    log_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run_undo(dry_run: bool = False, list_only: bool = False) -> bool:
    """Reverses the last recorded batch rename operation or inspects it."""
    log_file = get_undo_log_path()
    if not log_file.exists():
        ui.error("No previous Glaze rename history found to undo.")
        return False

    try:
        data = json.loads(log_file.read_text(encoding="utf-8"))
    except Exception as e:
        ui.error(f"Failed to read undo log: {e}")
        return False

    if not data:
        ui.warn("Undo log is empty.")
        return False

    if dry_run or list_only:
        ui.header(f"{ui.app_name.upper()} UNDO LOG ({len(data)} operations)", width=76)
        for item in reversed(data):
            old_p = Path(item["old"])
            new_p = Path(item["new"])
            if not new_p.exists():
                tag = ui.yellow("[MISSING]")
            elif old_p.exists():
                tag = ui.red("[COLLISION]")
            else:
                tag = ui.green("[REVERSIBLE]")
            print(f"  {tag} {ui.dim(new_p.name)} {ui.cyan('→')} {ui.bold(old_p.name)}  {ui.dim(f'({new_p})')}")
        ui.info("Dry-run preview only. No files were modified.", symbol="💡")
        return True

    if sys.stdin.isatty():
        confirm = ui.select(
            f"Revert {len(data)} rename operation(s)?",
            [
                ("yes", f"Yes, revert {len(data)} operation(s)"),
                ("no", "No, cancel"),
            ],
        )
        if confirm != "yes":
            ui.warn("Undo aborted by user.")
            return False

    ui.action(f"Reverting {len(data)} rename operation(s)...", symbol="🔄")
    reverted = 0
    for item in reversed(data):
        old_path = Path(item["old"])
        new_path = Path(item["new"])

        if not new_path.exists():
            print(f"  {ui.yellow('SKIP')} Current file '{new_path}' not found, skipping.")
            continue

        if old_path.exists():
            print(f"  {ui.red('COLLISION')} Original path '{old_path}' already exists, skipping.")
            continue

        try:
            new_path.rename(old_path)
            print(f"  {ui.green('REVERTED')} '{new_path.name}' → '{old_path.name}'")
            reverted += 1
        except Exception as e:
            print(f"  {ui.red('ERROR')} Failed to revert '{new_path}': {e}", file=sys.stderr)

    log_file.unlink(missing_ok=True)
    ui.success(f"Successfully reverted {reverted} file(s).")
    return True


def scan_directory(
    root: Path,
    extension: str,
    case_mode: str,
    safe_ascii: bool,
    lower_ext: bool,
    recursive: bool,
    include_dirs: bool,
    include_hidden: bool = False,
) -> list[RenamePlan]:
    """Scans directory and builds a conflict-checked list of planned renames."""
    plans: list[RenamePlan] = []
    clean_ext = extension.lstrip(".") if extension and extension != "*" else None

    if recursive:
        entries: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            # Hard exclude .git repository directories
            dirnames[:] = [d for d in dirnames if d != ".git"]
            if not include_hidden:
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            dp = Path(dirpath)
            for fn in filenames:
                if fn == ".git" or fn.startswith(".git"):
                    continue
                if not include_hidden and fn.startswith("."):
                    continue
                entries.append(dp / fn)
            if include_dirs:
                for dn in dirnames:
                    entries.append(dp / dn)
        # Deepest paths first for directories so children rename before parents
        entries.sort(key=lambda p: len(p.parts), reverse=True)
    else:
        entries = sorted(list(root.iterdir()))

    for p in entries:
        # Hard exclude .git under all conditions
        if p.name == ".git" or ".git" in p.parts:
            continue

        if not include_hidden and p.name.startswith("."):
            continue

        is_directory = p.is_dir()

        if is_directory and not include_dirs:
            continue

        name = p.name

        if is_directory:
            stem = name
            ext = ""
        else:
            if "." in name and not name.startswith("."):
                stem, ext = name.rsplit(".", 1)
            else:
                stem, ext = name, ""

            if clean_ext and ext.lower() != clean_ext.lower():
                continue

        new_filename = sanitize_filename(
            stem=stem,
            ext=ext,
            case_mode=case_mode,
            safe_ascii=safe_ascii,
            lower_ext=lower_ext,
        )

        if not new_filename or new_filename == name:
            continue

        target_path = p.parent / new_filename
        rel_old = str(p.relative_to(root)) if p != root else str(p)
        rel_new = str(target_path.relative_to(root)) if target_path != root else str(target_path)

        plans.append(
            RenamePlan(
                original=p,
                new_path=target_path,
                relative_old=rel_old,
                relative_new=rel_new,
                is_dir=is_directory,
            )
        )

    return plans


def handle_color_args():
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--no-color":
            ui.set_color_mode("never")
        elif arg.startswith("--color="):
            ui.set_color_mode(arg.split("=", 1)[1])
        elif arg == "--color" and i + 1 < len(sys.argv[1:]):
            ui.set_color_mode(sys.argv[1:][i + 1])


def print_help():
    """Prints beautiful colored usage instructions matching Folio & Flaker."""
    app = ui.app_name
    print(f"""{ui.badge()} {ui.bold("Universal Filename Sanitizer & Batch Case Engine")}

{ui.blue("Usage:")}
  {app} [options] [paths...]
  {app} undo [options]               Revert or inspect previous batch rename

{ui.blue("Options:")}
  -d, --dir DIR          Target directory (default: current working directory)
  -e, --ext EXT          Filter by file extension (e.g. pdf, mp3, txt, png)
  -a, --all              Include hidden dotfiles (hard-excludes .git)
  -s, --safe             Safe ASCII: strip non-alphanumeric chars & normalize accents
  -l, --lower-ext        Convert file extensions to lowercase
  -r, --recursive        Recursively process nested subdirectories
  --dirs                 Also rename directory names
  --on-conflict MODE     Collision strategy: skip, abort, suffix (default: skip)
  -n, --dry-run          Simulate changes without renaming any files
  -i, --interactive      Prompt for confirmation before applying renames
  -y, --yes              Bypass confirmation prompt
  --color MODE           Color output mode: auto, always, never (default: auto)
  --no-color             Disable colored output
  -h, --help             Show this help message and exit
  -V, -v, --version      Show version and exit

{ui.blue("Undo Options:")}
  -n, --dry-run          Preview operations that would be reverted without touching files
  -l, --list             List all recorded operations in undo history

{ui.blue("Case Transformations:")}
  --title-snake          Title_Snake_Case (default)
  --snake                standard_snake_case
  --upper-snake          UPPER_SNAKE_CASE
  --kebab                standard-kebab-case
  --pascal               PascalCase
  --camel                camelCase
  --lower                lowercase
  --upper                UPPERCASE

{ui.blue("Examples:")}
  {app}                              # Sanitize current directory to Title_Snake_Case
  {app} --snake                      # Convert all files to standard_snake_case
  {app} -a --kebab                   # Convert all files including hidden dotfiles
  {app} --on-conflict suffix         # Disambiguate colliding files with _1, _2 suffix
  {app} -e mp3 --title-snake         # Only format *.mp3 audio files
  {app} -r -s                        # Recursively sanitize all files with Safe ASCII
  {app} -n                           # Dry-run preview of planned renames
  {app} undo -n                      # Preview operations before reverting
  {app} undo                         # Revert the last executed batch rename
""")


def main():
    handle_color_args()

    if any(a in ("-h", "--help", "help") for a in sys.argv[1:]):
        print_help()
        sys.exit(0)

    if any(a in ("-V", "-v", "--version", "version") for a in sys.argv[1:]):
        print(f"{ui.badge()} {ui.bold('v0.1.0')}")
        sys.exit(0)

    # Handle 'glaze undo' and 'glaze log'
    if len(sys.argv) > 1 and sys.argv[1] in ("undo", "log"):
        is_list = sys.argv[1] == "log" or any(a in ("--list", "-l") for a in sys.argv[2:])
        is_dry = any(a in ("-n", "--dry-run") for a in sys.argv[2:])
        success = run_undo(dry_run=is_dry, list_only=is_list)
        sys.exit(0 if success else 1)

    parser = argparse.ArgumentParser(
        prog="glaze",
        add_help=False,
    )

    parser.add_argument("paths", nargs="*", help="Optional specific files or directories to process.")
    parser.add_argument("-d", "--dir", default=".", help="Target directory (Default: current directory).")
    parser.add_argument("-e", "--ext", default="*", help="Filter by file extension (e.g., pdf, mp3, txt).")
    parser.add_argument("-a", "--all", "--include-hidden", "--hidden", dest="include_hidden", action="store_true", help="Include hidden files (always excludes .git).")
    parser.add_argument("-s", "--safe", action="store_true", help="Safe ASCII: strip non-alphanumeric chars & normalize accents.")
    parser.add_argument("-l", "--lower-ext", action="store_true", help="Convert file extensions to lowercase.")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recursively process subdirectories.")
    parser.add_argument("--dirs", action="store_true", help="Also rename directory names.")
    parser.add_argument("--on-conflict", choices=["skip", "abort", "suffix"], default="skip", help="Conflict resolution: skip, abort, suffix (Default: skip).")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Simulate changes without renaming any files.")
    parser.add_argument("-i", "--interactive", action="store_true", help="Prompt for confirmation before applying renames.")
    parser.add_argument("-y", "--yes", action="store_true", help="Bypass confirmation prompt.")
    parser.add_argument("--color", choices=["auto", "always", "never"], default="auto", help="Color output mode.")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output.")
    parser.add_argument("-V", "-v", "--version", action="store_true", help="Show version and exit.")

    # Case conversions
    case_group = parser.add_mutually_exclusive_group()
    case_group.add_argument("--title-snake", dest="case_mode", action="store_const", const="title_snake", help="Title_Snake_Case (Default)")
    case_group.add_argument("--snake", dest="case_mode", action="store_const", const="snake", help="standard_snake_case")
    case_group.add_argument("--upper-snake", dest="case_mode", action="store_const", const="upper_snake", help="UPPER_SNAKE_CASE")
    case_group.add_argument("--kebab", dest="case_mode", action="store_const", const="kebab", help="standard-kebab-case")
    case_group.add_argument("--pascal", dest="case_mode", action="store_const", const="pascal", help="PascalCase")
    case_group.add_argument("--camel", dest="case_mode", action="store_const", const="camel", help="camelCase")
    case_group.add_argument("--lower", dest="case_mode", action="store_const", const="lower", help="lowercase")
    case_group.add_argument("--upper", dest="case_mode", action="store_const", const="upper", help="UPPERCASE")

    args = parser.parse_args()

    CASE_OPTIONS = [
        ("title_snake", "Title_Snake_Case (e.g. My_Document_File.pdf)"),
        ("snake", "snake_case (e.g. my_document_file.pdf)"),
        ("kebab", "kebab-case (e.g. my-document-file.pdf)"),
        ("pascal", "PascalCase (e.g. MyDocumentFile.pdf)"),
        ("camel", "camelCase (e.g. myDocumentFile.pdf)"),
        ("lower", "lowercase (e.g. mydocumentfile.pdf)"),
        ("upper", "UPPERCASE (e.g. MYDOCUMENTFILE.pdf)"),
        ("upper_snake", "UPPER_SNAKE_CASE (e.g. MY_DOCUMENT_FILE.pdf)"),
    ]

    is_interactive_session = args.interactive or (len(sys.argv) == 1 and sys.stdin.isatty())

    if not args.case_mode and is_interactive_session:
        case_mode = ui.select("Select target case format:", CASE_OPTIONS)
    else:
        case_mode = args.case_mode or "title_snake"

    target_dir = Path(args.dir).resolve()
    if not target_dir.exists():
        ui.error(f"Directory '{target_dir}' does not exist.")
        sys.exit(1)

    ui.header(f"{ui.app_name.upper()} BATCH RENAME ENGINE", width=76)
    scope_str = "recursive" if args.recursive else "current directory"
    safe_str = "Safe ASCII" if args.safe else "standard"
    hidden_str = "all (including hidden)" if args.include_hidden else "standard (hidden skipped)"
    ui.info(f"Target: {ui.cyan(str(target_dir))} | Mode: {ui.green(case_mode)} | Scope: {scope_str} | Hidden: {hidden_str}", symbol="📂")

    if args.dry_run:
        ui.warn("DRY RUN mode active: simulating renames without modifying files")

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
        ui.success("All filenames already conform to requested styling. Nothing to rename.")
        sys.exit(0)

    # Detect collisions and conflicts
    collisions: list[RenamePlan] = []
    executable_plans: list[RenamePlan] = []
    seen_destinations: set[Path] = set()

    for p in plans:
        is_collision = (p.new_path.exists() and p.new_path != p.original) or (p.new_path in seen_destinations)
        if is_collision:
            if args.on_conflict == "abort":
                ui.error(f"Conflict detected: target '{p.relative_new}' already exists for '{p.relative_old}'. Aborting.")
                sys.exit(1)
            elif args.on_conflict == "suffix":
                # Generate unique suffixed name
                if p.is_dir:
                    base_stem, ext = p.new_path.name, ""
                else:
                    if "." in p.new_path.name and not p.new_path.name.startswith("."):
                        base_stem, ext = p.new_path.name.rsplit(".", 1)
                    else:
                        base_stem, ext = p.new_path.name, ""
                counter = 1
                resolved_path = None
                while True:
                    suffixed_name = f"{base_stem}_{counter}.{ext}" if ext else f"{base_stem}_{counter}"
                    candidate_path = p.original.parent / suffixed_name
                    if not candidate_path.exists() and candidate_path not in seen_destinations:
                        resolved_path = candidate_path
                        break
                    counter += 1

                p.new_path = resolved_path
                p.relative_new = str(resolved_path.relative_to(target_dir)) if resolved_path != target_dir else str(resolved_path)
                executable_plans.append(p)
                seen_destinations.add(p.new_path)
            else:  # skip
                collisions.append(p)
        else:
            executable_plans.append(p)
            seen_destinations.add(p.new_path)

    print()
    for p in plans:
        if p in collisions:
            print(f"  {ui.yellow('[COLLISION SKIPPED]')} {ui.dim(repr(p.relative_old))} {ui.yellow('⇸')} target {ui.dim(repr(p.relative_new))} exists")
        else:
            tag = "DIR" if p.is_dir else "FILE"
            print(f"  {ui.dim(f'[{tag}]')} {ui.dim(repr(p.relative_old))} {ui.cyan('→')} {ui.bold_green(p.relative_new)}")

    print()
    ui.info(f"Found {ui.bold(str(len(plans)))} item(s) to rename. ({len(collisions)} collisions skipped)", symbol="📊")

    if args.dry_run:
        ui.info("Dry-run complete. Re-run without -n to apply renames permanently.", symbol="💡")
        sys.exit(0)

    if not executable_plans:
        ui.error("No renames can be performed safely without collisions.")
        sys.exit(1)

    # Interactive confirmation prompt if requested or in bare TTY mode
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
            sys.exit(0)

    # Execute renames
    executed_ops: list[tuple[str, str]] = []
    renamed_count = 0

    ui.action("Applying renames...", symbol="⚡")
    for p in executable_plans:
        try:
            p.original.rename(p.new_path)
            executed_ops.append((str(p.original), str(p.new_path)))
            renamed_count += 1
        except Exception as e:
            print(f"  {ui.red('FAILED')} '{p.relative_old}' → '{p.relative_new}': {e}", file=sys.stderr)

    save_undo_log(executed_ops)
    ui.success(f"Successfully renamed {renamed_count} item(s).")
    ui.info('Run "glaze undo" anytime to instantly revert this operation.', symbol="💡")


if __name__ == "__main__":
    main()
