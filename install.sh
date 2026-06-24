#!/usr/bin/env bash
# Install a skill from this repo into an agent's skills directory.
# Usage: ./install.sh <agent> [skill] [--link] [--dest DIR]
#   agent : claude | codex | copilot | gemini | agents
#   skill : a folder name under skills/ (default: install all skills)
#   --link: symlink instead of copy, so edits in this repo propagate
#   --dest DIR: install into DIR instead of the agent's default dir (handy for testing)
# Examples:
#   ./install.sh claude pd-externals
#   ./install.sh agents            # all skills into ~/.agents/skills (Codex/Copilot/Gemini)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() { sed -n '2,10p' "$0"; exit "${1:-0}"; }

[ $# -ge 1 ] || usage 1
agent="$1"; shift
skill=""; link=0; dest=""
while [ $# -gt 0 ]; do
  case "$1" in
    --link) link=1 ;;
    --dest) dest="${2:?--dest needs a directory}"; shift ;;
    -h|--help) usage 0 ;;
    -*) echo "unknown option: $1" >&2; usage 1 ;;
    *) skill="$1" ;;
  esac
  shift
done

case "$agent" in
  claude)  default="$HOME/.claude/skills" ;;
  codex)   default="$HOME/.codex/skills" ;;
  copilot) default="$HOME/.copilot/skills" ;;
  gemini)  default="$HOME/.gemini/skills" ;;
  agents)  default="$HOME/.agents/skills" ;;
  *) echo "unknown agent: '$agent' (expected: claude|codex|copilot|gemini|agents)" >&2; exit 1 ;;
esac
target="${dest:-$default}"
mkdir -p "$target"

install_one() {
  local name="$1" src="$ROOT/skills/$1"
  if [ ! -f "$src/SKILL.md" ]; then echo "skip '$name' (not a skill — no SKILL.md)"; return; fi
  rm -rf "$target/$name"
  if [ "$link" -eq 1 ]; then
    ln -s "$src" "$target/$name"; echo "linked   $name -> $target/$name"
  else
    cp -R "$src" "$target/$name"; echo "installed $name -> $target/$name"
  fi
}

if [ -n "$skill" ]; then
  install_one "$skill"
else
  for d in "$ROOT"/skills/*/; do install_one "$(basename "$d")"; done
fi
