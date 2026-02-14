#!/usr/bin/env zsh
# bump_version.sh
# Automates version bumping and changelog updating

set -e

SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
VIBE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VERSION_FILE="$VIBE_ROOT/VERSION"
CHANGELOG_FILE="$VIBE_ROOT/CHANGELOG.md"

source "$VIBE_ROOT/lib/utils.sh"

# Current Version
CURRENT_VERSION=$(cat "$VERSION_FILE")

show_help() {
    echo "Usage: ./bump_version.sh [major|minor|patch|x.y.z]"
    echo "  major: 1.0.0 -> 2.0.0"
    echo "  minor: 1.0.0 -> 1.1.0"
    echo "  patch: 1.0.0 -> 1.0.1"
    echo "  x.y.z: Set specific version"
}

if [[ $# -eq 0 ]]; then
    show_help
    exit 1
fi

MODE="$1"

# Calculate new version
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

case "$MODE" in
    major)
        NEW_VERSION="$((MAJOR + 1)).0.0"
        ;;
    minor)
        NEW_VERSION="$MAJOR.$((MINOR + 1)).0"
        ;;
    patch)
        NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
        ;;
    *)
        # Validate custom version format
        if [[ "$MODE" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            NEW_VERSION="$MODE"
        else
            log_error "Invalid version format or mode: $MODE"
            show_help
            exit 1
        fi
        ;;
esac

log_info "Bumping version: $CURRENT_VERSION -> $NEW_VERSION"

# Confirm
if [[ "${CI:-}" != "true" ]]; then
    confirm_action "Update files to version $NEW_VERSION?" "y" || exit 0
fi

# Update VERSION file
echo "$NEW_VERSION" > "$VERSION_FILE"
log_success "Updated VERSION file"

# Update CHANGELOG.md
# We want to insert the new version header after the first line or specific marker.
# Using standard Keep A Changelog format with appropriate sections.

DATE=$(date +%Y-%m-%d)
NEW_HEADER="## [$NEW_VERSION] - $DATE"

# Check if CHANGELOG exists
if [[ -f "$CHANGELOG_FILE" ]]; then
    # Create a temporary file
    TEMP_FILE=$(mktemp)

    # Read the first few lines to find where to insert
    # We look for the first "## [" line and insert before it

    awk -v header="$NEW_HEADER" '
    BEGIN { inserted = 0 }
    /^## \[/ && !inserted {
        print header
        print ""
        print "### ✨ New Features"
        print "- "
        print ""
        print "### 🚀 Performance Improvements"
        print "- "
        print ""
        print "### 🐛 Bug Fixes"
        print "- "
        print ""
        print "### 🔒 Security Enhancements"
        print "- "
        print ""
        inserted = 1
    }
    { print }
    END {
        if (!inserted) {
            print ""
            print header
            print ""
            print "### ✨ New Features"
            print "- Initial release."
        }
    }
    ' "$CHANGELOG_FILE" > "$TEMP_FILE"

    mv "$TEMP_FILE" "$CHANGELOG_FILE"
    log_success "Updated CHANGELOG.md"
else
    log_warn "CHANGELOG.md not found, creating new one"
    echo "# Changelog" > "$CHANGELOG_FILE"
    echo "" >> "$CHANGELOG_FILE"
    echo "$NEW_HEADER" >> "$CHANGELOG_FILE"
    echo "" >> "$CHANGELOG_FILE"
    echo "### ✨ New Features" >> "$CHANGELOG_FILE"
    echo "- Initial release." >> "$CHANGELOG_FILE"
fi

log_success "Version bump complete!"
log_info "Next steps:"
log_info "1. Review CHANGELOG.md"
log_info "2. git add VERSION CHANGELOG.md"
log_info "3. git commit -m \"chore(release): bump version to $NEW_VERSION\""
log_info "4. git tag v$NEW_VERSION"
log_info "5. git push origin main --tags"
