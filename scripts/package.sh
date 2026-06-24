#!/usr/bin/env bash
# Rebuild dist/<name>.skill (a zip) for every skill under skills/.
# A .skill is just a zip of the skill folder, e.g. it contains pd-externals/SKILL.md ...
# No dependencies beyond `zip`. Usage: bash scripts/package.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p dist
shopt -s nullglob
built=0
for dir in skills/*/; do
  name="$(basename "$dir")"
  if [ ! -f "$dir/SKILL.md" ]; then
    echo "skip $name (no SKILL.md)"
    continue
  fi
  out="dist/$name.skill"
  rm -f "$out"
  ( cd skills && zip -rqX "../$out" "$name" -x '*/.DS_Store' '*/__pycache__/*' '*.pyc' )
  echo "built $out"
  built=$((built + 1))
done
echo "done: $built skill package(s) in dist/"
