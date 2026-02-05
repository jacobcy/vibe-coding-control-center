#!/bin/bash
# scripts/backup-project.sh
# Creates a backup of the current project state

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_ROOT}_backup_$(date +%Y%m%d_%H%M%S)"

echo "Creating backup at $BACKUP_DIR..."
# Exclude the backup itself if it's being created inside (though we aim for sibling)
# But strictly, cp -r will copy the folder.
# We should probably copy to a sibling directory to avoid recursion issues if run from root.

# If SCRIPT_DIR is .../scripts/scripts, PROJECT_ROOT is .../scripts
# But currently standard structure is .../skills/scripts
# So if I put this file in .../skills/scripts/backup-project.sh (temporarily at root) OR
# if I strictly follow plan and put it in .../skills/scripts/scripts/backup-project.sh

# Let's assume we run this from the project root for now, or handle path derivation carefully.
# Current Root: /Users/jacobcy/Documents/skills/scripts

# If I write this file to /Users/jacobcy/Documents/skills/scripts/scripts/backup-project.sh
# Then SCRIPT_DIR = .../skills/scripts/scripts
# PROJECT_ROOT = .../skills/scripts

cp -r "$PROJECT_ROOT" "$BACKUP_DIR"

echo "Backup created successfully at $BACKUP_DIR"
