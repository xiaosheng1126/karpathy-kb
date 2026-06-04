#!/usr/bin/env python3
"""Install Karpathy KB adapters into an Obsidian vault.

The installer is conservative by default: it creates missing files and refuses
to overwrite existing user files unless --force is provided.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]

COMMON_DIRS = [
    "adapters",
    "prompts",
    "source-reader",
    "templates",
]

COMMON_FILES = [
    ".gitignore",
    "README.md",
    "commands.md",
    "index.md",
    "log.md",
    "package-lock.json",
    "package.json",
    "profile.md",
    "raw/README.md",
    "runbook.md",
    "scripts/browser_reader.mjs",
    "scripts/install.py",
    "scripts/kb.py",
    "scripts/source_reader.py",
    "wiki/README.md",
]

CODEX_FILES = [
    ("AGENTS.md", "AGENTS.md"),
    ("adapters/codex/.codex-plugin/plugin.json", ".codex-plugin/plugin.json"),
    ("adapters/codex/skills/karpathy-kb/SKILL.md", "skills/karpathy-kb/SKILL.md"),
]

CLAUDE_FILES = [
    ("adapters/claude/CLAUDE.md", "CLAUDE.md"),
    ("adapters/claude/commands/read.md", ".claude/commands/read.md"),
    ("adapters/claude/commands/deposit.md", ".claude/commands/deposit.md"),
    ("adapters/claude/commands/publish.md", ".claude/commands/publish.md"),
    ("adapters/claude/commands/update-kb.md", ".claude/commands/update-kb.md"),
]


def looks_like_vault(path: pathlib.Path) -> bool:
    return (path / ".obsidian").exists()


def find_parent_vault(path: pathlib.Path) -> pathlib.Path | None:
    current = path.resolve()
    for candidate in [current, *current.parents]:
        if looks_like_vault(candidate):
            return candidate
    return None


def obsidian_config_path() -> pathlib.Path:
    return pathlib.Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"


def detect_obsidian_vault(vault_name: str = "") -> pathlib.Path:
    current_vault = find_parent_vault(pathlib.Path.cwd())
    if current_vault:
        return current_vault

    config_path = obsidian_config_path()
    if not config_path.exists():
        raise SystemExit(
            "could not auto-detect Obsidian vault: no parent .obsidian directory and "
            f"Obsidian config not found at {config_path}"
        )

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"could not parse Obsidian config: {config_path}: {exc}") from exc

    vaults = data.get("vaults", {})
    candidates: list[tuple[str, pathlib.Path, bool]] = []
    if isinstance(vaults, dict):
        for item in vaults.values():
            if not isinstance(item, dict):
                continue
            raw_path = item.get("path")
            if not raw_path:
                continue
            path = pathlib.Path(str(raw_path)).expanduser()
            if path.exists():
                name = str(item.get("name") or path.name)
                candidates.append((name, path.resolve(), bool(item.get("open"))))

    if vault_name:
        matched = [path for name, path, _open in candidates if name == vault_name or path.name == vault_name]
        if len(matched) == 1:
            return matched[0]
        if matched:
            raise SystemExit(f"multiple Obsidian vaults match --vault-name {vault_name!r}")
        raise SystemExit(f"no Obsidian vault matches --vault-name {vault_name!r}")

    open_vaults = [path for _name, path, is_open in candidates if is_open]
    unique_open = sorted(set(open_vaults))
    if len(unique_open) == 1:
        return unique_open[0]

    unique = sorted({path for _name, path, _open in candidates})
    if len(unique) == 1:
        return unique[0]

    if not unique:
        raise SystemExit("could not auto-detect Obsidian vault: no valid vault paths in Obsidian config")

    lines = "\n".join(f"- {path}" for path in unique)
    raise SystemExit(
        "multiple Obsidian vaults found; rerun with --vault <path> or --vault-name <name>:\n"
        f"{lines}"
    )


class Installer:
    def __init__(self, vault: pathlib.Path, force: bool, dry_run: bool) -> None:
        self.vault = vault.resolve()
        self.force = force
        self.dry_run = dry_run
        self.created: list[pathlib.Path] = []
        self.updated: list[pathlib.Path] = []
        self.skipped: list[pathlib.Path] = []

    def ensure_dir(self, path: pathlib.Path) -> None:
        if self.dry_run:
            return
        path.mkdir(parents=True, exist_ok=True)

    def copy_file(self, src_rel: str, dst_rel: str) -> None:
        src = (ROOT / src_rel).resolve()
        dst = (self.vault / dst_rel).resolve()
        if src == dst:
            self.skipped.append(dst)
            return
        if not src.exists():
            raise SystemExit(f"missing source file: {src}")
        if dst.exists() and not self.force:
            self.skipped.append(dst)
            return
        existed_before = dst.exists()
        if not self.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        if existed_before:
            self.updated.append(dst)
        else:
            self.created.append(dst)

    def copy_tree(self, src_rel: str, dst_rel: str) -> None:
        src = (ROOT / src_rel).resolve()
        dst = (self.vault / dst_rel).resolve()
        if src == dst:
            self.skipped.append(dst)
            return
        if not src.exists():
            raise SystemExit(f"missing source directory: {src}")
        for item in sorted(src.rglob("*")):
            if item.is_dir() or "__pycache__" in item.parts:
                continue
            rel = item.relative_to(src)
            self.copy_file(str(pathlib.Path(src_rel) / rel), str(pathlib.Path(dst_rel) / rel))

    def install_common(self) -> None:
        self.ensure_dir(self.vault)
        self.ensure_dir(self.vault / "raw")
        self.ensure_dir(self.vault / "wiki")
        self.ensure_dir(self.vault / ".source-reader" / "profiles" / "default")
        for directory in COMMON_DIRS:
            self.copy_tree(directory, directory)
        for src, dst in ((path, path) for path in COMMON_FILES):
            self.copy_file(src, dst)

    def install_codex(self) -> None:
        for src, dst in CODEX_FILES:
            self.copy_file(src, dst)

    def install_claude(self) -> None:
        for src, dst in CLAUDE_FILES:
            self.copy_file(src, dst)

    def install_playwright(self) -> None:
        if self.dry_run:
            return
        package_json = self.vault / "package.json"
        if not package_json.exists():
            raise SystemExit(f"package.json does not exist in vault: {package_json}")
        print("\ninstalling Playwright runtime...")
        subprocess.run(["npm", "install"], cwd=self.vault, check=True)
        subprocess.run(["npx", "playwright", "install", "chromium"], cwd=self.vault, check=True)

    def print_summary(self) -> None:
        print(f"vault: {self.vault}")
        print(f"created: {len(self.created)}")
        print(f"updated: {len(self.updated)}")
        print(f"skipped: {len(self.skipped)}")
        if self.skipped:
            print("\nskipped existing files:")
            for path in self.skipped[:20]:
                print(f"- {path.relative_to(self.vault)}")
            if len(self.skipped) > 20:
                print(f"- ... {len(self.skipped) - 20} more")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Karpathy KB into an Obsidian vault")
    parser.add_argument(
        "--target",
        choices=["codex", "claude", "both"],
        default="both",
        help="agent adapter to install",
    )
    parser.add_argument(
        "--vault",
        default="auto",
        help="target Obsidian vault path; defaults to auto-detection",
    )
    parser.add_argument(
        "--vault-name",
        default="",
        help="Obsidian vault name to use when auto-detection finds multiple vaults",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing adapter/template files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be skipped without writing files",
    )
    parser.add_argument(
        "--install-playwright",
        action="store_true",
        help="run npm install and install Playwright Chromium for browser/login reading",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.vault == "auto":
        vault = detect_obsidian_vault(args.vault_name)
    else:
        vault = pathlib.Path(args.vault).expanduser()
        if not vault.is_absolute():
            vault = (pathlib.Path.cwd() / vault).resolve()

    installer = Installer(vault=vault, force=args.force, dry_run=args.dry_run)
    installer.install_common()
    if args.target in {"codex", "both"}:
        installer.install_codex()
    if args.target in {"claude", "both"}:
        installer.install_claude()
    if args.install_playwright:
        installer.install_playwright()
    installer.print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
