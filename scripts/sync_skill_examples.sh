#!/usr/bin/env bash
# Copy the figure_*/*.py demo scripts into scientific-figure-making/examples/
# so that `npx skills add` installs them with the skill. The `skills` CLI only
# copies the skill folder and skips symlinks that point outside it, so the
# scripts have to be real files inside the skill.
#
# Usage:
#   scripts/sync_skill_examples.sh          # refresh the copies
#   scripts/sync_skill_examples.sh --check  # exit 1 if the copies are stale
set -euo pipefail

cd "$(dirname "$0")/.."
dest=scientific-figure-making/examples

build() {
    local out=$1
    rm -rf "$out"
    mkdir -p "$out"
    for dir in figure_*/; do
        dir=${dir%/}
        mkdir -p "$out/$dir"
        cp "$dir"/*.py "$out/$dir/"
    done
}

if [[ "${1:-}" == "--check" ]]; then
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    build "$tmp/examples"
    if ! diff -r "$tmp/examples" "$dest" > /dev/null 2>&1; then
        echo "$dest is out of date. Run scripts/sync_skill_examples.sh" >&2
        exit 1
    fi
    echo "$dest is up to date."
else
    build "$dest"
    echo "Synced $(find "$dest" -name '*.py' | wc -l) scripts into $dest"
fi
