#!/usr/bin/env zsh
# scripts/bump.sh - Simple version bumper and changelog updater

set -e

# Support passing version or type (patch, minor, major)
type="${1:-patch}"
vfile="VERSION"
clfile="CHANGELOG.md"

[[ -f "$vfile" ]] || echo "2.0.0" > "$vfile"
current_v=$(cat "$vfile" | tr -d '[:space:]')

# Split version
IFS='.' read -r major minor patch <<< "$current_v"

case "$type" in
    patch) patch=$((patch + 1)) ;;
    minor) minor=$((minor + 1)); patch=0 ;;
    major) major=$((major + 1)); minor=0; patch=0 ;;
    *) 
      if [[ "$type" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
        new_v="$type"
      else
        echo "Error: Invalid version type '$type'. Use patch, minor, major or a semver string (e.g. 2.1.0-rc1)."
        exit 1
      fi
      ;;
esac

[[ -z "$new_v" ]] && new_v="${major}.${minor}.${patch}"

echo "$new_v" > "$vfile"

# Update CHANGELOG.md if it exists
if [[ -f "$clfile" ]]; then
    today=$(date +"%Y-%m-%d")
    desc="${2:-"Automated version bump and updates."}"
    # Check if this version header already exists
    if grep -q "## \[$new_v\]" "$clfile"; then
        echo "Note: Version $new_v already exists in CHANGELOG.md"
    else
        # Insert new version entry at the top, after the main title
        tmp_cl=$(mktemp)
        {
            head -n 2 "$clfile"
            echo "## [$new_v] - $today"
            echo ""
            echo "### ✨ Changed"
            # Split newlines in desc if provided as multi-line string
            echo "$desc" | sed 's/^/- /'
            echo ""
            tail -n +3 "$clfile"
        } > "$tmp_cl"
        mv "$tmp_cl" "$clfile"
    fi
fi

echo "🚀 Bumped version: $current_v -> $new_v"
