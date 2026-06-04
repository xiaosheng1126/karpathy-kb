#!/usr/bin/env python3
"""Install Karpathy KB adapters into an Obsidian vault.

The installer is conservative by default: it creates missing files and refuses
to overwrite existing user files unless --force is provided.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import time


ROOT = pathlib.Path(__file__).resolve().parents[1]


def sh_quote(value: str) -> str:
    return shlex.quote(value)

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
        self.registered_mcp: list[str] = []

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

    def write_mcp_runtime_files(self, port: int = 8765) -> None:
        if self.dry_run:
            return
        mcp_dir = self.vault / ".source-reader" / "mcp"
        mcp_dir.mkdir(parents=True, exist_ok=True)
        wrapper_path = mcp_dir / "source-reader-mcp.sh"
        wrapper = (
            "#!/bin/sh\n"
            f"cd {sh_quote(str(self.vault))} || exit 1\n"
            f"exec {sh_quote(sys.executable)} scripts/source_reader.py mcp\n"
        )
        wrapper_path.write_text(wrapper, encoding="utf-8")
        wrapper_path.chmod(0o755)
        self.updated.append(wrapper_path)
        server_cmd = ["/bin/sh", str(wrapper_path)]
        runtime = {
            "name": "source-reader",
            "command": server_cmd[0],
            "args": server_cmd[1:],
            "cwd": str(self.vault),
            "service": {
                "host": "127.0.0.1",
                "port": port,
                "health": f"http://127.0.0.1:{port}/health",
            },
        }
        runtime_path = mcp_dir / "source-reader.runtime.json"
        runtime_path.write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.updated.append(runtime_path)
        codex_config = (
            "[mcp_servers.source-reader]\n"
            f"command = {json.dumps(server_cmd[0])}\n"
            f"args = {json.dumps(server_cmd[1:], ensure_ascii=False)}\n"
            f"cwd = {json.dumps(str(self.vault), ensure_ascii=False)}\n"
        )
        codex_path = mcp_dir / "source-reader.codex.toml"
        codex_path.write_text(codex_config, encoding="utf-8")
        self.updated.append(codex_path)
        claude_config = {
            "mcpServers": {
                "source-reader": {
                    "command": server_cmd[0],
                    "args": server_cmd[1:],
                    "cwd": str(self.vault),
                }
            }
        }
        claude_path = mcp_dir / "source-reader.claude.json"
        claude_path.write_text(json.dumps(claude_config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.updated.append(claude_path)

    def install_playwright(self) -> None:
        if self.dry_run:
            return
        package_json = self.vault / "package.json"
        if not package_json.exists():
            raise SystemExit(f"package.json does not exist in vault: {package_json}")
        print("\ninstalling Playwright runtime...")
        subprocess.run(["npm", "install"], cwd=self.vault, check=True)
        subprocess.run(["npx", "playwright", "install", "chromium"], cwd=self.vault, check=True)

    def service_pid_path(self) -> pathlib.Path:
        return self.vault / ".source-reader" / "source-reader.pid"

    def service_log_path(self) -> pathlib.Path:
        return self.vault / ".source-reader" / "source-reader.log"

    def mcp_wrapper_path(self) -> pathlib.Path:
        return self.vault / ".source-reader" / "mcp" / "source-reader-mcp.sh"

    def service_is_running(self) -> bool:
        pid_path = self.service_pid_path()
        if not pid_path.exists():
            return False
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            return False

    def start_service(self, port: int = 8765) -> None:
        if self.dry_run:
            return
        if self.service_is_running():
            print("\nsource-reader service already running")
            return
        service_dir = self.vault / ".source-reader"
        service_dir.mkdir(parents=True, exist_ok=True)
        log_file = self.service_log_path().open("a", encoding="utf-8")
        proc = subprocess.Popen(
            [
                sys.executable,
                "scripts/source_reader.py",
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=self.vault,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.service_pid_path().write_text(str(proc.pid), encoding="utf-8")
        time.sleep(0.5)
        print(f"\nsource-reader service started: http://127.0.0.1:{port}")
        print(f"service pid: {proc.pid}")
        print(f"service log: {self.service_log_path().relative_to(self.vault)}")

    def codex_config_path(self) -> pathlib.Path:
        return pathlib.Path.home() / ".codex" / "config.toml"

    def codex_mcp_block(self) -> str:
        return (
            "[mcp_servers.source-reader]\n"
            "command = \"/bin/sh\"\n"
            f"args = {json.dumps([str(self.mcp_wrapper_path())], ensure_ascii=False)}\n"
            f"cwd = {json.dumps(str(self.vault), ensure_ascii=False)}\n"
        )

    def register_codex_mcp(self) -> None:
        if self.dry_run:
            return
        config_path = self.codex_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        section = "[mcp_servers.source-reader]"
        if section in existing and not self.force:
            print("\nCodex MCP already has source-reader; use --force to replace it")
            return
        if existing:
            backup = config_path.with_suffix(config_path.suffix + f".bak-karpathy-kb-{int(time.time())}")
            shutil.copy2(config_path, backup)
            print(f"\nCodex config backup: {backup}")
        lines = existing.splitlines()
        output: list[str] = []
        skipping = False
        for line in lines:
            stripped = line.strip()
            if stripped == section or stripped.startswith("[mcp_servers.source-reader."):
                skipping = True
                continue
            if skipping and stripped.startswith("[") and stripped.endswith("]"):
                skipping = False
            if not skipping:
                output.append(line)
        if output and output[-1].strip():
            output.append("")
        output.append(self.codex_mcp_block().rstrip())
        config_path.write_text("\n".join(output) + "\n", encoding="utf-8")
        self.registered_mcp.append("codex")
        print(f"\nCodex MCP registered: {config_path}")

    def register_claude_mcp(self) -> None:
        if self.dry_run:
            return
        wrapper = str(self.mcp_wrapper_path())
        existing = subprocess.run(
            ["claude", "mcp", "get", "source-reader"],
            cwd=self.vault,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if existing.returncode == 0 and not self.force:
            print("\nClaude MCP already has source-reader; use --force to replace it")
            return
        if existing.returncode == 0 and self.force:
            subprocess.run(["claude", "mcp", "remove", "--scope", "user", "source-reader"], cwd=self.vault, check=False)
        subprocess.run(
            ["claude", "mcp", "add", "--scope", "user", "source-reader", "--", "/bin/sh", wrapper],
            cwd=self.vault,
            check=True,
        )
        self.registered_mcp.append("claude")
        print("\nClaude MCP registered: source-reader")

    def register_mcp(self, target: str) -> None:
        if target in {"codex", "both"}:
            self.register_codex_mcp()
        if target in {"claude", "both"}:
            self.register_claude_mcp()

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
        mcp_runtime = self.vault / ".source-reader" / "mcp" / "source-reader.runtime.json"
        if mcp_runtime.exists():
            print("\nMCP runtime file:")
            print(f"- {mcp_runtime.relative_to(self.vault)}")
            if self.registered_mcp:
                print(f"Global MCP registered: {', '.join(self.registered_mcp)}")
            else:
                print("Global Codex/Claude MCP registration is intentionally not modified by default.")


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
    parser.add_argument(
        "--install-runtime",
        action="store_true",
        help="prepare all local runtime dependencies used by source-reader",
    )
    parser.add_argument(
        "--start-service",
        action="store_true",
        help="start local source-reader service after installation",
    )
    parser.add_argument(
        "--install-mcp",
        action="store_true",
        help="write project-local MCP configs and runtime metadata",
    )
    parser.add_argument(
        "--register-mcp",
        choices=["none", "codex", "claude", "both"],
        default="none",
        help="register source-reader MCP in global Codex/Claude client config",
    )
    parser.add_argument(
        "--service-port",
        type=int,
        default=8765,
        help="localhost port for source-reader service",
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
    if args.install_mcp or args.register_mcp != "none":
        installer.write_mcp_runtime_files(args.service_port)
    if args.register_mcp != "none":
        installer.register_mcp(args.register_mcp)
    if args.install_runtime or args.install_playwright:
        installer.install_playwright()
    if args.start_service:
        installer.start_service(args.service_port)
    installer.print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
