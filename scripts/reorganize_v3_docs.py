import os
import re
from pathlib import Path

# Paths
ROOT = Path(".")
STANDARDS_DIR = ROOT / "docs/standards"
V2_DIR = STANDARDS_DIR / "v2"
V3_DIR = STANDARDS_DIR / "v3"

# Categorization
COMMON = [
    "action-verbs.md",
    "authorship-standard.md",
    "cognition-spec-dominion.md",
    "doc-organization.md",
    "doc-quality-standards.md",
    "git-workflow-standard.md",
    "glossary.md",
    "serena-usage.md",
    "worktree-lifecycle-standard.md",
    "agent-workflow-standard.md" # user might want this in root too, but let's check
]

LEGACY = [
    "registry-json-standard.md",
    "roadmap-json-standard.md",
    "handoff-governance-standard.md",
    "command-standard.md",
    "data-model-standard.md",
    "shell-capability-design.md",
    "shell-skill-boundary-audit.md",
    "skill-standard.md",
    "skill-trigger-standard.md",
    "vibe-engine-design.md"
]

V3_EXCLUSIVE = [
    "github-remote-call-standard.md",
    "handoff-store-standard.md"
]

def restore_common():
    """Restore common standards to root and remove from v2."""
    for f in COMMON:
        v2_path = V2_DIR / f
        root_path = STANDARDS_DIR / f
        if v2_path.exists():
            if not root_path.exists():
                print(f"Restoring {f} to root...")
                # We use os.system to 'git restore' if it was deleted, or just move back
                os.system(f"git restore docs/standards/{f}")
            print(f"Removing duplicate {f} from v2...")
            v2_path.unlink()

def cleanup_legacy():
    """Ensure legacy files are moved to v2 and deleted from root."""
    for f in LEGACY:
        root_path = STANDARDS_DIR / f
        v2_path = V2_DIR / f
        if root_path.exists():
            if not v2_path.exists():
                print(f"Moving legacy {f} to v2...")
                root_path.rename(v2_path)
            else:
                print(f"Legacy {f} already in v2, deleting from root...")
                root_path.unlink()

def update_references():
    """Update markdown path references repository-wide."""
    mapping = {}
    for f in LEGACY:
        mapping[f"docs/standards/{f}"] = f"docs/standards/v2/{f}"
    for f in V3_EXCLUSIVE:
        mapping[f"docs/standards/{f}"] = f"docs/standards/v3/{f}"
    
    for md_file in ROOT.glob("**/*.md"):
        if ".git" in str(md_file): continue
        if "node_modules" in str(md_file): continue
        
        content = md_file.read_text()
        new_content = content
        for old, new in mapping.items():
            new_content = new_content.replace(old, new)
        
        if new_content != content:
            print(f"Updating references in {md_file}")
            md_file.write_text(new_content)

if __name__ == "__main__":
    confirm = input("Execute selective restoration and reference update? (y/n): ")
    if confirm.lower() == 'y':
        restore_common()
        cleanup_legacy()
        update_references()
        print("Done.")
