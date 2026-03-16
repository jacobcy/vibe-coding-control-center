import os
import re
from pathlib import Path

# Paths
ROOT = Path(".")
STANDARDS_DIR = ROOT / "docs/standards"
V2_DIR = STANDARDS_DIR / "v2"
V3_DIR = STANDARDS_DIR / "v3"

# Categorization (更新：添加 doc-text-test-governance.md)
COMMON = [
    "action-verbs.md",
    "authorship-standard.md",
    "cognition-spec-dominion.md",
    "doc-organization.md",
    "doc-quality-standards.md",
    "doc-text-test-governance.md",  # 新增
    "git-workflow-standard.md",
    "glossary.md",
    "serena-usage.md",
    "worktree-lifecycle-standard.md",
    "agent-workflow-standard.md"
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
                os.system(f"git restore docs/standards/{f}")
            print(f"Removing duplicate {f} from v2...")
            v2_path.unlink()

def cleanup_legacy():
    """Ensure legacy files are moved to v2 and deleted from root."""
    # Create v2 directory if it doesn't exist
    V2_DIR.mkdir(exist_ok=True)
    
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
    print("=== 预览操作 ===")
    print(f"将创建: {V2_DIR}")
    print(f"将移动 {len(LEGACY)} 个文件到 v2")
    print(f"保留 {len(COMMON)} 个文件在根目录")
    print()
    
    confirm = input("Execute selective restoration and reference update? (y/n): ")
    if confirm.lower() == 'y':
        restore_common()
        cleanup_legacy()
        update_references()
        print("\n✓ Done. Changes are unstaged. Review with 'git status'")
        print("  To commit: git add . && git commit -m 'chore: reorganize standards into v2/v3 directories'")
    else:
        print("Aborted.")
