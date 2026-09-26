# Glaze ✨

> **Universal Filename Sanitizer, Case Transformer & Batch Rename Engine**

Glaze is an ultra-fast, opinionated batch renaming utility designed to normalize messy filenames, standardize project conventions, and perform robust case transformations across large directories.

---

## ✨ Features

- 🔠 **8 Case Transformation Modes**:
  - `Title_Snake_Case` (Default)
  - `standard_snake_case`
  - `UPPER_SNAKE_CASE`
  - `standard-kebab-case`
  - `PascalCase`
  - `camelCase`
  - `lowercase` / `UPPERCASE`
- 🧠 **Smart Boundary Detection**: Automatically splits `camelCase`, `PascalCase`, dots, hyphens, and underscores into distinct words before transforming.
- 🌐 **Safe ASCII & Accent Normalization (`-s / --safe`)**: Decomposes Unicode diacritics (`Café` $\to$ `Cafe`, `München` $\to$ `Munchen`) rather than destructively erasing international characters.
- 🔄 **1-Command Undo Engine (`glaze undo`)**: Stores a transaction journal in cache, allowing instant rollback of any batch rename operation.
- 🌲 **Recursive Traversal (`-r / --recursive`)**: Recursively processes subdirectories bottom-up so child files are renamed cleanly before parent directories.
- 📁 **Directory Renaming (`--dirs`)**: Option to sanitize and rename directory names alongside regular files.
- 🛡️ **Collision Protection**: Pre-checks target paths and prevents accidental overwrites if a file with the destination name already exists.
- 🧪 **Dry-Run Simulation (`-n / --dry-run`)**: Preview all planned changes in a colored diff view without touching the filesystem.
- 🪶 **Zero Host Dependencies**: Pure standard library core (<20ms execution time).

---

## 🚀 Quick Start

Run Glaze directly via Nix without installing:

```bash
# Sanitize all files in the current directory to Title_Snake_Case (Default)
nix run github:SpanishSyntax/Glaze

# Convert all filenames to standard_snake_case
nix run github:SpanishSyntax/Glaze -- --snake

# Convert to standard-kebab-case with lowercase extensions
nix run github:SpanishSyntax/Glaze -- --kebab --lower-ext

# Filter by extension (e.g. only audio or documentation files)
nix run github:SpanishSyntax/Glaze -- -e mp3 --title-snake

# Safe ASCII mode with recursive directory traversal
nix run github:SpanishSyntax/Glaze -- -r -s

# Dry-run preview
nix run github:SpanishSyntax/Glaze -- --snake --dry-run

# Revert the last executed batch rename
nix run github:SpanishSyntax/Glaze -- undo
```

---

## 💻 CLI Commands & Options

```text
Usage: glaze [paths...] [options]
       glaze undo

Options:
  -d, --dir PATH         Target directory (Default: current directory)
  -e, --ext EXT          Filter by file extension (e.g., pdf, mp3, txt)
  -s, --safe             Safe ASCII: strip non-alphanumeric chars & normalize accents
  -l, --lower-ext        Convert file extensions to lowercase
  -r, --recursive        Recursively process subdirectories
  --dirs                 Also rename directory names
  -n, --dry-run          Simulate changes without renaming any files
  -i, --interactive      Prompt for confirmation before applying renames
  -y, --yes              Bypass confirmation prompt
  -h, --help             Show this help menu
  -v, --version          Show version information

Case Transformations:
  --title-snake          Title_Snake_Case (Default)
  --snake                standard_snake_case
  --upper-snake          UPPER_SNAKE_CASE
  --kebab                standard-kebab-case
  --pascal               PascalCase
  --camel                camelCase
  --lower                lowercase
  --upper                UPPERCASE
```

---

## 🛠️ Home Manager Configuration

Add Glaze to your `flake.nix`:

```nix
{
  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    glaze = {
      url = "github:SpanishSyntax/Glaze";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, glaze, ... }: {
    homeConfigurations.user = home-manager.lib.homeManagerConfiguration {
      modules = [
        glaze.homeManagerModules.default
        {
          programs.glaze.enable = true;
        }
      ];
    };
  };
}
```

Once enabled, `glaze` is available in your `$PATH`.

---

## 📜 License

MIT © SpanishSyntax
