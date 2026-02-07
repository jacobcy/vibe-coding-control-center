#!/usr/bin/env zsh
# init-project.sh
# 用途: 初始化新项目，复制 Cursor 规则，生成 CLAUDE.md 模板

if [ -z "${ZSH_VERSION:-}" ]; then
    if command -v zsh >/dev/null 2>&1; then
        exec zsh -l "$0" "$@"
    fi
    echo "zsh not found. Please run ./scripts/install.sh to install zsh." >&2
    exit 1
fi

set -e

# ================= LOAD UTILITIES =================
SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"

# Colors for backward compatibility with existing output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_step "AI 项目初始化脚本 (Cursor & Claude)"

# Get target directory from command line arguments
TARGET_DIR="${1:-.}"

# Validate the target directory input to prevent injection attacks
if ! validate_input "$TARGET_DIR" "false"; then
    log_critical "Invalid target directory input: $TARGET_DIR"
    exit 1
fi

# Sanitize the directory name to prevent path traversal
TARGET_DIR=$(sanitize_filename "$TARGET_DIR")

# Further validate path to prevent directory traversal
if ! validate_path "$TARGET_DIR" "Target directory validation failed"; then
    log_critical "Invalid target directory: $TARGET_DIR"
    exit 1
fi

# Check if target directory exists, create if necessary
if [ ! -d "$TARGET_DIR" ]; then
    log_warn "Target directory $TARGET_DIR does not exist, creating..."
    if ! mkdir -p "$TARGET_DIR" 2>/dev/null; then
        log_critical "Failed to create target directory: $TARGET_DIR"
        exit 1
    fi
fi

# Convert target directory to absolute path
TARGET_DIR_ABS=""
if ! TARGET_DIR_ABS=$(cd "$TARGET_DIR" 2>/dev/null && pwd); then
    log_critical "Cannot access target directory: $TARGET_DIR"
    exit 1
fi

# Validate the absolute path
if ! validate_path "$TARGET_DIR_ABS" "Absolute target directory validation failed"; then
    log_critical "Invalid absolute target directory: $TARGET_DIR_ABS"
    exit 1
fi

cd "$TARGET_DIR_ABS"
log_success "Initializing project: $(pwd)"

# 2. Generate project-level rules template (Stack Specifics)
log_step "Initializing project-level rules (.cursor/rules/tech-stack.mdc)..."

# Validate directory creation
if ! mkdir -p .cursor/rules 2>/dev/null; then
    log_error "Failed to create .cursor/rules directory"
    exit 1
fi

# Create a template for defining specific tech stack specifications
# Unlike ~/.claude/rules (global behavior), this stores project-specific constraints
TECH_STACK_TEMPLATE='# Project Tech Stack Rules

## Language Standards
- [ ] TypeScript Strength: Strict (no any)
- [ ] Python Formatting: Black/Isort

## Framework Patterns
- [ ] Component Structure: Functional / Class-based
- [ ] API Design: REST / GraphQL

## Testing
- [ ] Framework: Jest / Pytest
'

# Write the tech stack template with security validation
if ! secure_write_file ".cursor/rules/tech-stack.mdc" "$TECH_STACK_TEMPLATE" "644"; then
    log_error "Failed to create tech-stack.mdc template"
    exit 1
fi

log_info "✓ Created tech-stack.mdc template - Define project-specific tech specs here"

# 3. Generate CLAUDE.md template
log_step "Generating CLAUDE.md template..."

if [ -f "CLAUDE.md" ]; then
    log_info "✓ CLAUDE.md already exists, skipping"
else
    # Create a generic project template
    PROJECT_NAME=$(basename "$TARGET_DIR_ABS")
    CLAUDE_MD_TEMPLATE="# Project Context: $PROJECT_NAME

## Build & Test Commands
- Build: \`npm run build\`
- Test: \`npm test\`
- Dev: \`npm run dev\`

## Tech Stack
- Language: (e.g., TypeScript/JavaScript, Python, Go)
- Framework: (e.g., Next.js, React, FastAPI, Spring Boot)
- Styling: (e.g., Tailwind CSS, SCSS, Styled Components)
- Patterns: (e.g., Functional components, Clean Architecture)

## Project Structure
- \`src/\`: Main source code
- \`components/\`: Reusable components
- \`tests/\`: Test files
- \`docs/\`: Documentation

## Coding Standards
- Follow established patterns in the codebase
- Use consistent naming conventions
- Document complex logic
- Write tests for new functionality

## Special Considerations
- [Any project-specific requirements or constraints]

## Troubleshooting
- Common issues and solutions for this project
"

    if ! secure_write_file "CLAUDE.md" "$CLAUDE_MD_TEMPLATE" "644"; then
        log_error "Failed to create CLAUDE.md template"
        exit 1
    fi
    log_info "✓ Created CLAUDE.md template"
fi

# 4. AI-Friendly Scaffolding Recommendations
log_step "AI Friendly Scaffolding Recommendations..."
echo "----------------------------------------"
log_info "1. Next.js + Shadcn UI (Most Recommended)"
echo "   - Reason: Component library code is extremely standardized, AI generates new UI with almost zero errors."
echo "   - Command: npx create-next-app@latest"

log_info "2. T3 Stack (TypeScript Strong Typing)"
echo "   - Reason: Extremely strong type safety allows AI to follow logic with 'traceable' patterns."
echo "   - Command: npx create-t3-app@latest"

log_info "3. FastAPI (Python Backend First)"
echo "   - Reason: Auto-generated documentation and strong type hints are AI's favorite."
echo "----------------------------------------"

echo -e "\n${BLUE}Initialization complete! You can now start your AI pair programming with 'c' or 'o'.${NC}"
