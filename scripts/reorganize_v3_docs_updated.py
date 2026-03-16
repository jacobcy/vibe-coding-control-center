import os
import re
from pathlib import Path

# Paths
ROOT = Path(".")
STANDARDS_DIR = ROOT / "docs/standards"
V2_DIR = STANDARDS_DIR / "v2"
V3_DIR = STANDARDS_DIR / "v3"

# Categorization (v2 架构标准已全部移至 v2)
COMMON = [
    "action-verbs.md",
    "authorship-standard.md",
    "cognition-spec-dominion.md",
    "doc-organization.md",
    "doc-quality-standards.md",
    "doc-text-test-governance.md",
    "glossary.md",
    "serena-usage.md",
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
    "vibe-engine-design.md",
    "git-workflow-standard.md",          # v2 workflow 标准
    "worktree-lifecycle-standard.md"     # v2 worktree 标准
]

V3_EXCLUSIVE = [
    "github-remote-call-standard.md",
    "handoff-store-standard.md"
]

def move_legacy_files():
    """Move legacy v2 files to v2 directory using git mv."""
    V2_DIR.mkdir(exist_ok=True)

    moved_count = 0
    for f in LEGACY:
        root_path = STANDARDS_DIR / f
        v2_path = V2_DIR / f

        if root_path.exists() and not v2_path.exists():
            print(f"Moving {f} to v2...")
            os.system(f"git mv docs/standards/{f} docs/standards/v2/{f}")
            moved_count += 1
        elif v2_path.exists() and root_path.exists():
            print(f"Warning: {f} exists in both locations, removing from root...")
            root_path.unlink()
        elif v2_path.exists():
            print(f"✓ {f} already in v2")
        else:
            print(f"⚠ {f} not found in either location")

    return moved_count

def update_references():
    """Update markdown path references repository-wide."""
    mapping = {}
    for f in LEGACY:
        mapping[f"docs/standards/{f}"] = f"docs/standards/v2/{f}"
    for f in V3_EXCLUSIVE:
        mapping[f"docs/standards/{f}"] = f"docs/standards/v3/{f}"

    updated_count = 0
    for md_file in ROOT.glob("**/*.md"):
        if ".git" in str(md_file):
            continue
        if "node_modules" in str(md_file):
            continue

        # Skip if file doesn't exist (broken symlinks)
        if not md_file.exists():
            continue

        try:
            content = md_file.read_text()
            new_content = content
            for old, new in mapping.items():
                new_content = new_content.replace(old, new)

            if new_content != content:
                print(f"  Updating: {md_file}")
                md_file.write_text(new_content)
                updated_count += 1
        except Exception as e:
            print(f"  ⚠ Error processing {md_file}: {e}")

    print(f"\n✓ 更新了 {updated_count} 个文件的引用")

if __name__ == "__main__":
    print("=== Standards Reorganization Script ===")
    print(f"将移动 {len(LEGACY)} 个 v2 遗留文件到 v2/")
    print(f"保留 {len(COMMON)} 个通用文件在根目录")
    print(f"v3 专用文件 {len(V3_EXCLUSIVE)} 个在 v3/")
    print()

    print("遗留文件列表：")
    for f in LEGACY:
        print(f"  - {f}")
    print()

    confirm = input("执行移动和引用更新？(y/n): ")
    if confirm.lower() == 'y':
        print("\n=== Step 1: 移动文件 ===")
        moved = move_legacy_files()
        print(f"✓ 移动了 {moved} 个文件")

        print("\n=== Step 2: 更新引用 ===")
        update_references()

        print("\n✓ 完成！")
        print("  运行 'git status' 查看变更")
        print("  提交: git add . && git commit -m 'chore: move v2 workflow standards to v2/'")
    else:
        print("已取消")
