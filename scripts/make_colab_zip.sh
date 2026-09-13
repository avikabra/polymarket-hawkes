#!/usr/bin/env bash
# Build thesis-polymarket-slim.zip for upload to Google Drive, consumed by
# notebooks/colab_pipeline.ipynb (cell 3 unzips it, cell 5 `pip install -e . --no-deps`
# against the unzipped src/). See reports/colab_offload_plan.md.
#
# Includes: src/, scripts/*.py, pyproject.toml, config/*.yaml (minus credentials),
# and the local-pipeline data artifacts scripts 06-14 need on Colab.
# Excludes: secrets (.env, config/credentials.yaml, config/*.json), dead/oversized
# corpora (quarantine, audit), and the pre-pivot matches.db (script 08 recreates it).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ZIP_NAME="thesis-polymarket-slim.zip"
ZIP_PATH="$REPO_ROOT/$ZIP_NAME"

rm -f "$ZIP_PATH"

shopt -s nullglob

INCLUDE=()
INCLUDED_SUMMARY=()

add() {
    # add <path> — only if it exists, and record it for the summary
    local path="$1"
    if [[ -e "$path" ]]; then
        INCLUDE+=("$path")
        INCLUDED_SUMMARY+=("$path")
    else
        echo "WARNING: expected path missing, skipping: $path"
    fi
}

# ── Code (needed for `pip install -e . --no-deps` on Colab) ───────────────────
add "src"
add "pyproject.toml"
for f in scripts/*.py; do
    add "$f"
done

# ── Config (all yaml except credentials) ───────────────────────────────────────
for f in config/*.yaml; do
    [[ "$(basename "$f")" == "credentials.yaml" ]] && continue
    add "$f"
done

# ── Polymarket data (scripts 01-03, local) ─────────────────────────────────────
add "data/polymarket/universe.parquet"
add "data/polymarket/_UNIVERSE_SUCCESS"
add "data/polymarket/bars_1min"
add "data/polymarket/trades"

# ── News corpus (scripts 04-06, local) ──────────────────────────────────────────
if [[ -d "data/news/gdelt_gkg" ]]; then
    add "data/news/gdelt_gkg"
    [[ -f "data/news/gdelt_gkg/_SCOPE.json" ]] || echo "WARNING: data/news/gdelt_gkg/_SCOPE.json missing — script 04 may not have finished. Run it before uploading, or scripts 07/09/12 will hard-fail on Colab."
else
    echo "WARNING: data/news/gdelt_gkg/ not found — run scripts/04_pull_gdelt_corpus.py first."
fi

if [[ -d "data/news/feeds" ]]; then
    add "data/news/feeds"
    [[ -f "data/news/feeds/_SCOPE.json" ]] || echo "WARNING: data/news/feeds/_SCOPE.json missing — script 05 may not have finished. Run it before uploading, or scripts 07/09/12 will hard-fail on Colab."
else
    echo "WARNING: data/news/feeds/ not found — run scripts/05_pull_category_feeds.py first."
fi

# Optional — bodies already fetched locally (script 06 ships the rest via --verified-only on Colab)
if [[ -d "data/news/bodies" ]]; then
    add "data/news/bodies"
fi

# ── Build the zip ───────────────────────────────────────────────────────────────
# Explicit excludes as a safety net, independent of what was selected above:
# secrets must never reach Drive even if the include list above is changed later.
zip -rq "$ZIP_PATH" "${INCLUDE[@]}" \
    -x ".env" \
    -x "config/credentials.yaml" \
    -x "config/*.json" \
    -x "data/news/_quarantine_sports_20260912/*" \
    -x "data/news/audit/*" \
    -x "data/matches/matches.db" \
    -x "*/__pycache__/*" \
    -x "*.pyc" \
    -x "*.DS_Store"

echo ""
echo "=== $ZIP_NAME built ==="
echo "Size: $(du -h "$ZIP_PATH" | cut -f1)"
echo "Included top-level paths:"
printf '  %s\n' "${INCLUDED_SUMMARY[@]}"
