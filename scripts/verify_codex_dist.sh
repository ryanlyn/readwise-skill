#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 "$repo_root/scripts/build_codex_dist.py" --clean

tmp_dir="$(mktemp -d /tmp/readwise-codex-verify.XXXXXX)"
trap 'rm -rf "$tmp_dir"' EXIT

for zip_path in "$repo_root"/dist/codex/*.zip; do
  unzip -q "$zip_path" -d "$tmp_dir"
done

for skill_dir in "$tmp_dir"/readwise "$tmp_dir"/readwise-reader; do
  if [[ ! -d "$skill_dir" ]]; then
    echo "Missing unpacked skill directory: $skill_dir" >&2
    exit 1
  fi

  if [[ ! -f "$skill_dir/SKILL.md" ]]; then
    echo "Missing SKILL.md in $skill_dir" >&2
    exit 1
  fi

  if [[ ! -d "$skill_dir/readwise_common" ]]; then
    echo "Missing readwise_common in $skill_dir" >&2
    exit 1
  fi

  uv run --project "$skill_dir" python -m compileall "$skill_dir/scripts" "$skill_dir/readwise_common" >/dev/null

done

uv run --project "$tmp_dir/readwise" python "$tmp_dir/readwise/scripts/readwise_client.py" --help >/dev/null
uv run --project "$tmp_dir/readwise-reader" python "$tmp_dir/readwise-reader/scripts/reader_client.py" --help >/dev/null

echo "Codex artifacts verified: $repo_root/dist/codex"
