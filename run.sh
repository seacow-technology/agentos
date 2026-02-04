#!/usr/bin/env bash
# AgentOS Public Release - Quick Start Script
#
# Usage:
#   ./run.sh           # Run system check (doctor)
#   ./run.sh doctor    # Run system check
#   ./run.sh init      # Initialize database
#   ./run.sh webui     # Start WebUI (default port 8080)
#   ./run.sh cli       # Start interactive CLI
#
# Environment variables:
#   AGENTOS_WEBUI_PORT - WebUI port (default: 8080)
#   AGENTOS_WEBUI_HOST - WebUI host (default: 127.0.0.1)

set -euo pipefail

COMMAND="${1:-doctor}"

echo "🚀 AgentOS Quick Start"
echo ""

# Check Python 3.13+
if ! command -v python3 &> /dev/null; then
  echo "❌ Python 3 not found. Please install Python 3.13+"
  exit 1
fi

# Create virtual environment if not exists
if [[ ! -d ".venv" ]]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Show venv Python version (consistent with what will run)
PYTHON_VERSION=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
echo "✓ Python ${PYTHON_VERSION} (venv)"

# Suppress warnings for cleaner first-run experience
export PYTHONWARNINGS="${PYTHONWARNINGS:-ignore::UserWarning}"

# Upgrade pip and install dependencies
echo "📦 Installing dependencies..."
pip install -U pip -q
pip install -e . -q

echo ""
echo "✅ Setup complete!"
echo ""
echo "ℹ️  Voice features are optional:"
echo "   pip install -e '.[voice]'  (Python < 3.14)"
echo ""

# Run command
case "${COMMAND}" in
  doctor)
    echo "🔍 Running system check..."
    python -m agentos.cli.main doctor
    ;;
  init)
    echo "🔧 Initializing AgentOS database..."
    python -m agentos.cli.main init
    ;;
  help)
    echo "📚 AgentOS Help"
    echo ""
    python -m agentos.cli.main --help
    ;;
  webui)
    echo "🌐 Starting WebUI..."

    # Check port availability (default 8080)
    WEBUI_PORT="${AGENTOS_WEBUI_PORT:-8080}"
    WEBUI_HOST="${AGENTOS_WEBUI_HOST:-127.0.0.1}"

    # Check if port is already in use (requires lsof)
    if command -v lsof &> /dev/null; then
      if lsof -Pi :${WEBUI_PORT} -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo ""
        echo "⚠️  Port ${WEBUI_PORT} is already in use."
        echo ""
        echo "Options:"
        echo "  1. Stop the process using port ${WEBUI_PORT}"
        echo "  2. Use a different port:"
        echo "     AGENTOS_WEBUI_PORT=8081 ./run.sh webui"
        echo ""
        exit 1
      fi
    else
      echo "⚠️  Warning: lsof not found, skipping port check"
      echo "   If WebUI fails to start, try a different port:"
      echo "   AGENTOS_WEBUI_PORT=8081 ./run.sh webui"
      echo ""
    fi

    echo "Starting at http://${WEBUI_HOST}:${WEBUI_PORT}"
    python -m agentos.cli.main --web
    ;;
  cli)
    echo "💻 Starting interactive CLI..."
    python -m agentos.cli.main
    ;;
  *)
    echo "❌ Unknown command: ${COMMAND}"
    echo ""
    echo "Available commands:"
    echo "  ./run.sh doctor    # System check (default)"
    echo "  ./run.sh init      # Initialize database"
    echo "  ./run.sh webui     # Start WebUI"
    echo "  ./run.sh cli       # Interactive CLI"
    echo "  ./run.sh help      # Show help"
    echo ""
    echo "Environment variables:"
    echo "  AGENTOS_WEBUI_PORT=8081 ./run.sh webui  # Custom port"
    exit 1
    ;;
esac
