#!/bin/bash
# Example usage of cross-repository tracing CLI commands
#
# This script demonstrates various ways to trace project and task activities
# across multiple repositories without using the WebUI.

set -e

PROJECT_ID="my-app"
TASK_ID="task-123"

echo "=================================================="
echo "Cross-Repository Tracing CLI Examples"
echo "=================================================="
echo ""

# Example 1: Basic project trace
echo "1. Basic Project Trace (Table Format)"
echo "--------------------------------------------------"
agentos project trace "$PROJECT_ID"
echo ""

# Example 2: Project trace with JSON output
echo "2. Project Trace (JSON Format)"
echo "--------------------------------------------------"
agentos project trace "$PROJECT_ID" --format json | jq '.'
echo ""

# Example 3: Project trace with tree view
echo "3. Project Trace (Tree Format)"
echo "--------------------------------------------------"
agentos project trace "$PROJECT_ID" --format tree
echo ""

# Example 4: Limit number of tasks shown
echo "4. Project Trace with Task Limit"
echo "--------------------------------------------------"
agentos project trace "$PROJECT_ID" --limit 3
echo ""

# Example 5: Basic task trace
echo "5. Basic Task Trace (Table Format)"
echo "--------------------------------------------------"
agentos task repo-trace "$TASK_ID"
echo ""

# Example 6: Detailed task trace
echo "6. Detailed Task Trace"
echo "--------------------------------------------------"
agentos task repo-trace "$TASK_ID" --detailed
echo ""

# Example 7: Task trace with JSON output
echo "7. Task Trace (JSON Format)"
echo "--------------------------------------------------"
agentos task repo-trace "$TASK_ID" --format json | jq '.'
echo ""

# Example 8: Task trace with tree view (dependency tree)
echo "8. Task Trace (Tree Format - Dependency Tree)"
echo "--------------------------------------------------"
agentos task repo-trace "$TASK_ID" --format tree
echo ""

# Example 9: Alternative access via dependencies command
echo "9. Task Trace via Dependencies Command"
echo "--------------------------------------------------"
agentos task dependencies trace "$TASK_ID"
echo ""

# Example 10: Extract specific data with jq
echo "10. Extract Specific Data (Backend Repository Changes)"
echo "--------------------------------------------------"
agentos task repo-trace "$TASK_ID" --format json | \
  jq '.repositories[] | select(.name=="backend") | .changes'
echo ""

# Example 11: Count total files changed
echo "11. Count Total Files Changed Across All Repos"
echo "--------------------------------------------------"
FILE_COUNT=$(agentos task repo-trace "$TASK_ID" --format json | \
  jq '[.repositories[].changes.file_count] | add')
echo "Total files changed: $FILE_COUNT"
echo ""

# Example 12: List all tasks that depend on this task
echo "12. List Dependent Tasks"
echo "--------------------------------------------------"
agentos task repo-trace "$TASK_ID" --format json | \
  jq -r '.dependencies.depended_by[].task_id'
echo ""

# Example 13: Check if task has cross-repo dependencies
echo "13. Check for Cross-Repository Dependencies"
echo "--------------------------------------------------"
REPO_COUNT=$(agentos task repo-trace "$TASK_ID" --format json | \
  jq '.repositories | length')
if [ "$REPO_COUNT" -gt 1 ]; then
  echo "✓ Task involves multiple repositories ($REPO_COUNT repos)"
else
  echo "✗ Task only involves single repository"
fi
echo ""

# Example 14: Export task trace to file
echo "14. Export Task Trace to File"
echo "--------------------------------------------------"
OUTPUT_FILE="task-${TASK_ID}-trace.json"
agentos task repo-trace "$TASK_ID" --format json > "$OUTPUT_FILE"
echo "✓ Task trace exported to: $OUTPUT_FILE"
echo ""

# Example 15: Generate summary report
echo "15. Generate Summary Report"
echo "--------------------------------------------------"
echo "Project: $PROJECT_ID"
echo "Task: $TASK_ID"
echo ""

# Get task status
STATUS=$(agentos task repo-trace "$TASK_ID" --format json | jq -r '.task.status')
echo "Status: $STATUS"

# Get repository count
REPO_COUNT=$(agentos task repo-trace "$TASK_ID" --format json | jq '.repositories | length')
echo "Repositories involved: $REPO_COUNT"

# Get artifact count
ARTIFACT_COUNT=$(agentos task repo-trace "$TASK_ID" --format json | jq '.artifacts | length')
echo "Artifacts produced: $ARTIFACT_COUNT"

# Get dependency counts
DEPENDS_ON=$(agentos task repo-trace "$TASK_ID" --format json | jq '.dependencies.depends_on | length')
DEPENDED_BY=$(agentos task repo-trace "$TASK_ID" --format json | jq '.dependencies.depended_by | length')
echo "Dependencies: $DEPENDS_ON (depends on), $DEPENDED_BY (depended by)"
echo ""

echo "=================================================="
echo "Examples Complete!"
echo "=================================================="
echo ""
echo "For more information, see:"
echo "  docs/cli/CROSS_REPO_TRACING.md"
echo ""
