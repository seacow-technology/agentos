#!/bin/bash
set -e

echo "=== Multi-Repo Minimal Example ==="
echo ""

# Setup test directories
DEMO_DIR="/tmp/agentos-demo-$(date +%s)"
mkdir -p "$DEMO_DIR"

echo "1. Creating local test repos..."
mkdir -p "$DEMO_DIR/repoA" "$DEMO_DIR/repoB"

# Initialize repoA
cd "$DEMO_DIR/repoA"
git init
echo "# Repo A" > README.md
echo "console.log('Hello from Repo A');" > index.js
git add .
git commit -m "Initial commit for Repo A"

# Initialize repoB
cd "$DEMO_DIR/repoB"
git init
echo "# Repo B" > README.md
echo "def hello(): print('Hello from Repo B')" > main.py
git add .
git commit -m "Initial commit for Repo B"

# Go to demo directory
cd "$DEMO_DIR"

# Create project config
echo "2. Creating project configuration..."
cat > project.yaml << 'YAML_EOF'
name: minimal-demo
description: Minimal multi-repo example

repos:
  - name: repoA
    path: ./repoA
    role: code
    writable: true
    branch: main

  - name: repoB
    path: ./repoB
    role: code
    writable: true
    branch: main
YAML_EOF

# Import project
echo "3. Importing project..."
agentos project import --from project.yaml --workspace-root "$DEMO_DIR" --yes

# Verify import
echo ""
echo "4. Verifying import..."
agentos project repos list minimal-demo

# Show workspace
echo ""
echo "5. Workspace created at:"
echo "   $DEMO_DIR"
ls -la "$DEMO_DIR"

echo ""
echo "✓ Demo complete!"
echo ""
echo "To explore:"
echo "  cd $DEMO_DIR"
echo "  agentos project repos list minimal-demo"
echo "  agentos project validate minimal-demo"
echo ""
echo "To cleanup:"
echo "  rm -rf $DEMO_DIR"
