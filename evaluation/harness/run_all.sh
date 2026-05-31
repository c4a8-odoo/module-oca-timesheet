#!/usr/bin/env bash
# Score every candidate migration listed in evaluation/modules.txt and
# aggregate the results.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACES="${WORKSPACES:-/tmp/migrations}"

mkdir -p "$ROOT/runs" "$ROOT/reports"

while IFS= read -r module; do
    [ -z "$module" ] && continue
    src="$WORKSPACES/$module/source_18.0/$module"
    cand="$WORKSPACES/$module/candidate_19.0/$module"
    ref="$WORKSPACES/$module/reference_19.0/$module"
    out="$ROOT/runs/$module"

    if [ ! -d "$cand" ]; then
        echo "skip $module: candidate workspace missing ($cand)" >&2
        continue
    fi
    if [ ! -d "$ref" ]; then
        echo "skip $module: reference workspace missing ($ref)" >&2
        continue
    fi

    python3 "$ROOT/harness/score.py" "$module" \
        --source "$src" --candidate "$cand" --reference "$ref" --out "$out"
done < "$ROOT/modules.txt"

python3 "$ROOT/harness/aggregate.py"
