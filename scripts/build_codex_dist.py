#!/usr/bin/env python3
"""Build standalone Codex skill zip artifacts for Readwise skills."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

DEPENDENCIES = ["requests>=2.31.0", "typer>=0.12.0", "pydantic>=2.5.0"]
IGNORE_PATTERNS = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


@dataclass(frozen=True)
class SkillSpec:
    name: str
    source_dir: Path
    cli_script: str


@dataclass(frozen=True)
class BuildConfig:
    repo_root: Path
    plugin_root: Path
    dist_root: Path
    version: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Codex zip distributions for Readwise skills."
    )
    parser.add_argument(
        "--version",
        help="Override artifact version (defaults to plugins/readwise/.claude-plugin/plugin.json)",
    )
    parser.add_argument(
        "--clean", action="store_true", help="Remove dist/codex before building"
    )
    return parser.parse_args()


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def read_version(plugin_root: Path, override: str | None) -> str:
    if override:
        return override
    plugin_manifest = plugin_root / ".claude-plugin" / "plugin.json"
    data = json.loads(plugin_manifest.read_text(encoding="utf-8"))
    version = data.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"Invalid version in {plugin_manifest}")
    return version.strip()


def transform_skill_markdown(raw: str, *, skill_name: str, cli_script: str) -> str:
    codex_root_expr = f"${{CODEX_HOME:-$HOME/.codex}}/skills/{skill_name}"
    transformed = raw
    transformed = transformed.replace(
        f"${{CLAUDE_PLUGIN_ROOT}}/skills/{skill_name}/scripts/{cli_script}",
        f"{codex_root_expr}/scripts/{cli_script}",
    )
    transformed = transformed.replace(
        f"${{CLAUDE_PLUGIN_ROOT}}/skills/{skill_name}", codex_root_expr
    )
    transformed = transformed.replace(
        "--project ${CLAUDE_PLUGIN_ROOT}", f"--project {codex_root_expr}"
    )
    transformed = transformed.replace(
        "${CLAUDE_PLUGIN_ROOT}/readwise_common", f"{codex_root_expr}/readwise_common"
    )
    transformed = transformed.replace("${CLAUDE_PLUGIN_ROOT}", codex_root_expr)
    return transformed


def render_pyproject(skill_name: str, version: str) -> str:
    deps = "\n".join(f'    "{dependency}",' for dependency in DEPENDENCIES)
    return (
        "[project]\n"
        f'name = "readwise-codex-{skill_name}"\n'
        f'version = "{version}"\n'
        'description = "Standalone Codex Readwise skill runtime"\n'
        'requires-python = ">=3.11"\n'
        "dependencies = [\n"
        f"{deps}\n"
        "]\n\n"
        "[tool.uv]\n"
        "package = false\n"
    )


def write_skill_tree(config: BuildConfig, spec: SkillSpec, staging_root: Path) -> Path:
    skill_root = staging_root / spec.name
    skill_root.mkdir(parents=True, exist_ok=True)

    source_skill_md = spec.source_dir / "SKILL.md"
    transformed = transform_skill_markdown(
        source_skill_md.read_text(encoding="utf-8"),
        skill_name=spec.name,
        cli_script=spec.cli_script,
    )
    (skill_root / "SKILL.md").write_text(transformed, encoding="utf-8")

    shutil.copytree(
        spec.source_dir / "scripts", skill_root / "scripts", ignore=IGNORE_PATTERNS
    )
    shutil.copytree(
        config.plugin_root / "readwise_common",
        skill_root / "readwise_common",
        ignore=IGNORE_PATTERNS,
    )
    shutil.copy2(config.repo_root / "LICENSE", skill_root / "LICENSE")
    (skill_root / "pyproject.toml").write_text(
        render_pyproject(spec.name, config.version), encoding="utf-8"
    )

    return skill_root


def zip_skill_tree(skill_root: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as zip_file:
        for path in sorted(skill_root.rglob("*")):
            if path.is_file():
                zip_file.write(path, arcname=path.relative_to(skill_root.parent))


def build(config: BuildConfig, *, clean: bool) -> list[Path]:
    if clean and config.dist_root.exists():
        shutil.rmtree(config.dist_root)
    config.dist_root.mkdir(parents=True, exist_ok=True)

    skills = [
        SkillSpec(
            name="readwise",
            source_dir=config.plugin_root / "skills" / "readwise",
            cli_script="readwise_client.py",
        ),
        SkillSpec(
            name="readwise-reader",
            source_dir=config.plugin_root / "skills" / "readwise-reader",
            cli_script="reader_client.py",
        ),
    ]

    outputs: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="readwise-codex-dist-") as temp_dir:
        staging_root = Path(temp_dir)
        for spec in skills:
            skill_root = write_skill_tree(config, spec, staging_root)
            output_path = config.dist_root / f"{spec.name}-{config.version}.zip"
            zip_skill_tree(skill_root, output_path)
            outputs.append(output_path)

    return outputs


def main() -> int:
    args = parse_args()
    repo_root = repo_root_from_script()
    plugin_root = repo_root / "plugins" / "readwise"
    version = read_version(plugin_root, args.version)
    config = BuildConfig(
        repo_root=repo_root,
        plugin_root=plugin_root,
        dist_root=repo_root / "dist" / "codex",
        version=version,
    )

    outputs = build(config, clean=args.clean)
    for path in outputs:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
