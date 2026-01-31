#!/bin/bash
#
# InfoNeed Metrics Dashboard Demo Script
#
# This script demonstrates the InfoNeed Metrics WebUI Dashboard functionality.
# It shows how to:
# 1. Access the API endpoints
# 2. View metrics summary
# 3. Get historical data
# 4. Export metrics
#
# Prerequisites:
# - AgentOS WebUI running (python -m agentos.webui.app)
# - curl and jq installed
#

set -e

BASE_URL="http://localhost:8000"
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "InfoNeed Metrics Dashboard Demo"
echo "================================================"
echo ""

# Check if WebUI is running
echo -e "${BLUE}[1/5] Checking if WebUI is running...${NC}"
if curl -s "${BASE_URL}/api/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ WebUI is running${NC}"
else
    echo -e "${YELLOW}✗ WebUI is not running. Please start it with:${NC}"
    echo "    python -m agentos.webui.app"
    exit 1
fi
echo ""

# Get 24h summary
echo -e "${BLUE}[2/5] Fetching 24h metrics summary...${NC}"
SUMMARY=$(curl -s "${BASE_URL}/api/info-need-metrics/summary?time_range=24h")

if echo "$SUMMARY" | jq -e '.ok == true' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Successfully fetched summary${NC}"
    echo ""
    echo "Time Range: $(echo "$SUMMARY" | jq -r '.data.time_range')"
    echo "Period: $(echo "$SUMMARY" | jq -r '.data.period.start') to $(echo "$SUMMARY" | jq -r '.data.period.end')"
    echo ""
    echo "Metrics:"
    echo "  • Comm Trigger Rate:     $(echo "$SUMMARY" | jq -r '.data.metrics.comm_trigger_rate | . * 100 | round | tostring + "%"')"
    echo "  • False Positive Rate:   $(echo "$SUMMARY" | jq -r '.data.metrics.false_positive_rate | . * 100 | round | tostring + "%"')"
    echo "  • False Negative Rate:   $(echo "$SUMMARY" | jq -r '.data.metrics.false_negative_rate | . * 100 | round | tostring + "%"')"
    echo "  • Ambient Hit Rate:      $(echo "$SUMMARY" | jq -r '.data.metrics.ambient_hit_rate | . * 100 | round | tostring + "%"')"
    echo "  • Decision Stability:    $(echo "$SUMMARY" | jq -r '.data.metrics.decision_stability | . * 100 | round | tostring + "%"')"
    echo ""
    echo "Counts:"
    echo "  • Total Classifications: $(echo "$SUMMARY" | jq -r '.data.counts.total_classifications')"
    echo "  • Comm Triggered:        $(echo "$SUMMARY" | jq -r '.data.counts.comm_triggered')"
    echo "  • Ambient Queries:       $(echo "$SUMMARY" | jq -r '.data.counts.ambient_queries')"
    echo "  • False Positives:       $(echo "$SUMMARY" | jq -r '.data.counts.false_positives')"
    echo "  • False Negatives:       $(echo "$SUMMARY" | jq -r '.data.counts.false_negatives')"
else
    echo -e "${YELLOW}✗ No data available or error occurred${NC}"
    echo "Error: $(echo "$SUMMARY" | jq -r '.error // "Unknown error"')"
fi
echo ""

# Get 7d history with hour granularity
echo -e "${BLUE}[3/5] Fetching 7-day historical data (hour granularity)...${NC}"
HISTORY=$(curl -s "${BASE_URL}/api/info-need-metrics/history?time_range=7d&granularity=hour")

if echo "$HISTORY" | jq -e '.ok == true' > /dev/null 2>&1; then
    DATA_POINTS=$(echo "$HISTORY" | jq '.data.data_points | length')
    echo -e "${GREEN}✓ Successfully fetched history${NC}"
    echo "Time Range: $(echo "$HISTORY" | jq -r '.data.time_range')"
    echo "Granularity: $(echo "$HISTORY" | jq -r '.data.granularity')"
    echo "Data Points: $DATA_POINTS"

    if [ "$DATA_POINTS" -gt 0 ]; then
        echo ""
        echo "Sample Data Point (first):"
        echo "$HISTORY" | jq '.data.data_points[0]' | head -10
    fi
else
    echo -e "${YELLOW}✗ No history data available${NC}"
fi
echo ""

# Test different time ranges
echo -e "${BLUE}[4/5] Testing different time ranges...${NC}"
for RANGE in "24h" "7d" "30d"; do
    echo -n "  Testing ${RANGE}... "
    RESULT=$(curl -s "${BASE_URL}/api/info-need-metrics/summary?time_range=${RANGE}")
    if echo "$RESULT" | jq -e '.ok == true' > /dev/null 2>&1; then
        TOTAL=$(echo "$RESULT" | jq -r '.data.counts.total_classifications')
        echo -e "${GREEN}✓ ($TOTAL classifications)${NC}"
    else
        echo -e "${YELLOW}✗ (no data)${NC}"
    fi
done
echo ""

# Export metrics
echo -e "${BLUE}[5/5] Exporting metrics data...${NC}"
EXPORT_FILE="info_need_metrics_export_$(date +%Y%m%d_%H%M%S).json"
curl -s "${BASE_URL}/api/info-need-metrics/export?time_range=24h&format=json" > "$EXPORT_FILE"

if [ -f "$EXPORT_FILE" ]; then
    FILE_SIZE=$(wc -c < "$EXPORT_FILE" | tr -d ' ')
    if [ "$FILE_SIZE" -gt 100 ]; then
        echo -e "${GREEN}✓ Successfully exported metrics${NC}"
        echo "File: $EXPORT_FILE"
        echo "Size: ${FILE_SIZE} bytes"

        # Show structure
        echo ""
        echo "Export structure:"
        cat "$EXPORT_FILE" | jq 'if .ok == true then .data | keys else .error end'
    else
        echo -e "${YELLOW}✗ Export file is too small (likely an error)${NC}"
        cat "$EXPORT_FILE" | jq '.'
        rm -f "$EXPORT_FILE"
    fi
else
    echo -e "${YELLOW}✗ Failed to create export file${NC}"
fi
echo ""

# Summary
echo "================================================"
echo "Demo Complete!"
echo "================================================"
echo ""
echo "To view the dashboard in your browser:"
echo "  1. Navigate to: ${BASE_URL}"
echo "  2. Click: Quality → InfoNeed Metrics"
echo ""
echo "API Endpoints:"
echo "  • Summary:  GET ${BASE_URL}/api/info-need-metrics/summary"
echo "  • History:  GET ${BASE_URL}/api/info-need-metrics/history"
echo "  • Export:   GET ${BASE_URL}/api/info-need-metrics/export"
echo ""
echo "For full documentation, see:"
echo "  docs/INFO_NEED_METRICS_DASHBOARD.md"
echo ""
