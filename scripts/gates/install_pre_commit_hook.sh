#!/bin/bash
# Install pre-commit hook for DB integrity gates
#
# This script installs a git pre-commit hook that runs all DB integrity gates
# before allowing a commit.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"
HOOK_FILE="$HOOKS_DIR/pre-commit"

echo "================================================================================"
echo "Install DB Integrity Pre-Commit Hook"
echo "================================================================================"
echo ""

# Check if .git directory exists
if [ ! -d "$PROJECT_ROOT/.git" ]; then
    echo "Error: Not a git repository. Cannot install pre-commit hook."
    echo "Location: $PROJECT_ROOT"
    exit 1
fi

# Create hooks directory if it doesn't exist
mkdir -p "$HOOKS_DIR"

# Check if pre-commit hook already exists
if [ -f "$HOOK_FILE" ]; then
    echo "Pre-commit hook already exists: $HOOK_FILE"
    echo ""
    echo "Options:"
    echo "  1. Backup and replace"
    echo "  2. Append to existing hook"
    echo "  3. Cancel"
    echo ""
    read -p "Choose option (1/2/3): " choice

    case $choice in
        1)
            # Backup existing hook
            BACKUP_FILE="$HOOK_FILE.backup.$(date +%Y%m%d_%H%M%S)"
            echo "Backing up existing hook to: $BACKUP_FILE"
            mv "$HOOK_FILE" "$BACKUP_FILE"
            ;;
        2)
            # Append to existing hook
            echo "Appending DB gates to existing hook..."
            cat >> "$HOOK_FILE" << 'EOF'

# ==============================================================================
# DB Integrity Gates (auto-added by install_pre_commit_hook.sh)
# ==============================================================================

echo "Running DB integrity gates..."
./scripts/gates/run_all_gates.sh

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ DB integrity gates failed! Commit blocked."
    echo ""
    echo "To fix:"
    echo "  - Review gate output above"
    echo "  - Fix violations in your code"
    echo "  - Run './scripts/gates/run_all_gates.sh' to verify"
    echo ""
    echo "To bypass (NOT RECOMMENDED):"
    echo "  git commit --no-verify"
    echo ""
    exit 1
fi

echo "✅ DB integrity gates passed!"
echo ""

# ==============================================================================
# End of DB Integrity Gates
# ==============================================================================
EOF
            echo "✓ DB gates appended to existing hook"
            exit 0
            ;;
        3)
            echo "Cancelled."
            exit 0
            ;;
        *)
            echo "Invalid option. Cancelled."
            exit 1
            ;;
    esac
fi

# Create new pre-commit hook
cat > "$HOOK_FILE" << 'EOF'
#!/bin/bash
# Pre-commit hook: DB Integrity Gates
#
# This hook runs all DB integrity gates before allowing a commit.
# To bypass (NOT RECOMMENDED), use: git commit --no-verify

set -e

echo "================================================================================"
echo "Pre-Commit Hook: DB Integrity Gates"
echo "================================================================================"
echo ""

# Run all gates
./scripts/gates/run_all_gates.sh

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ DB integrity gates failed! Commit blocked."
    echo ""
    echo "To fix:"
    echo "  - Review gate output above"
    echo "  - Fix violations in your code"
    echo "  - Run './scripts/gates/run_all_gates.sh' to verify"
    echo ""
    echo "To bypass (NOT RECOMMENDED):"
    echo "  git commit --no-verify"
    echo ""
    exit 1
fi

echo ""
echo "✅ DB integrity gates passed!"
echo "================================================================================"
echo ""

exit 0
EOF

# Make hook executable
chmod +x "$HOOK_FILE"

echo "✓ Pre-commit hook installed successfully!"
echo ""
echo "Location: $HOOK_FILE"
echo ""
echo "The hook will now run automatically before each commit."
echo ""
echo "To test the hook:"
echo "  ./scripts/gates/run_all_gates.sh"
echo ""
echo "To bypass the hook (NOT RECOMMENDED):"
echo "  git commit --no-verify"
echo ""
echo "To uninstall:"
echo "  rm $HOOK_FILE"
echo ""
