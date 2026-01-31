#!/bin/bash

##############################################################################
# Evolvable System Complete Demonstration
#
# This script demonstrates the three major subsystems of the Evolvable System:
# 1. Quality Monitoring Subsystem (Audit logs, Metrics, WebUI)
# 2. Memory Subsystem (MemoryOS, BrainOS, Pattern Learning)
# 3. Multi-Intent Processing Subsystem (Splitter, ChatEngine integration)
#
# Usage: ./demo_evolvable_system.sh [subsystem]
#   subsystem: all (default), quality, memory, multi-intent
##############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get subsystem parameter (default: all)
SUBSYSTEM=${1:-all}

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

wait_for_input() {
    echo -e "\n${YELLOW}Press Enter to continue...${NC}"
    read
}

##############################################################################
# Demo 1: Quality Monitoring Subsystem
##############################################################################
demo_quality_monitoring() {
    print_header "📊 Demo 1: Quality Monitoring Subsystem"

    echo "This subsystem tracks classification performance through:"
    echo "  • Audit logging (INFO_NEED_CLASSIFICATION, INFO_NEED_OUTCOME events)"
    echo "  • 6 core metrics calculation"
    echo "  • WebUI visualization dashboard"
    echo ""

    wait_for_input

    # 1.1: Check audit log
    print_info "Step 1: Checking audit log for recent classifications..."
    echo ""
    echo "SQL Query:"
    echo "  SELECT COUNT(*), event_type FROM task_audits"
    echo "  WHERE timestamp > datetime('now', '-24 hours')"
    echo "  GROUP BY event_type;"
    echo ""

    sqlite3 store/registry.sqlite "
        SELECT
            event_type,
            COUNT(*) as count
        FROM task_audits
        WHERE timestamp > datetime('now', '-24 hours')
        AND event_type LIKE 'INFO_NEED_%'
        GROUP BY event_type;
    " || print_error "No audit data found (this is normal for fresh install)"

    wait_for_input

    # 1.2: Calculate metrics
    print_info "Step 2: Calculating quality metrics..."
    echo ""
    echo "Command: agentos metrics show --last 7d"
    echo ""

    if command -v agentos &> /dev/null; then
        agentos metrics show --last 7d || print_error "No metrics data available (need classification events)"
    else
        print_info "Using Python directly:"
        python3 -c "
from agentos.metrics.info_need_metrics import generate_metrics_report
report = generate_metrics_report('7d')
print(report)
" || print_error "Metrics calculation requires classification events"
    fi

    wait_for_input

    # 1.3: WebUI Dashboard
    print_info "Step 3: WebUI Dashboard"
    echo ""
    echo "To view the metrics dashboard:"
    echo "  1. Start WebUI: python -m agentos.webui.app"
    echo "  2. Navigate to: http://localhost:5000"
    echo "  3. Click: Dashboard → InfoNeed Metrics"
    echo ""
    echo "Dashboard features:"
    echo "  • 6 metric cards with real-time values"
    echo "  • Breakdown by classification type"
    echo "  • Outcome distribution chart"
    echo "  • Time range filtering (7d, 30d, 90d, all)"
    echo "  • Auto-refresh every 30 seconds"
    echo "  • JSON export capability"
    echo ""

    print_success "Quality Monitoring demo complete!"
    wait_for_input
}

##############################################################################
# Demo 2: Memory Subsystem
##############################################################################
demo_memory_subsystem() {
    print_header "🧠 Demo 2: Memory Subsystem"

    echo "This subsystem enables learning from experience through:"
    echo "  • MemoryOS: Short-term judgment storage (30 days)"
    echo "  • BrainOS: Long-term pattern storage (permanent)"
    echo "  • Automated pattern extraction (daily job)"
    echo ""

    wait_for_input

    # 2.1: MemoryOS Storage
    print_info "Step 1: MemoryOS - Short-term Judgment History"
    echo ""
    echo "MemoryOS stores individual classification judgments for 30 days."
    echo ""
    echo "Check current judgments:"
    sqlite3 store/registry.sqlite "
        SELECT
            COUNT(*) as total,
            outcome,
            classified_type
        FROM info_need_judgments
        WHERE timestamp > datetime('now', '-30 days')
        GROUP BY outcome, classified_type;
    " || print_error "No judgment data found (run some classifications first)"

    wait_for_input

    # 2.2: Query example
    print_info "Step 2: Query recent judgments"
    echo ""
    echo "Example: Get judgments from last 7 days with 'validated' outcome"
    echo ""
    sqlite3 -header -column store/registry.sqlite "
        SELECT
            substr(question_text, 1, 50) as question,
            classified_type,
            confidence_level,
            outcome,
            datetime(timestamp) as time
        FROM info_need_judgments
        WHERE timestamp > datetime('now', '-7 days')
        AND outcome = 'validated'
        LIMIT 10;
    " || print_info "No validated judgments yet"

    wait_for_input

    # 2.3: BrainOS Patterns
    print_info "Step 3: BrainOS - Long-term Pattern Storage"
    echo ""
    echo "BrainOS stores extracted decision patterns permanently."
    echo ""
    echo "Check current patterns:"
    sqlite3 store/registry.sqlite "
        SELECT
            COUNT(*) as total_patterns,
            AVG(success_rate) as avg_success_rate,
            AVG(occurrence_count) as avg_occurrences
        FROM info_need_patterns;
    " || print_info "No patterns yet (run pattern extraction job)"

    wait_for_input

    # 2.4: Pattern Extraction Job
    print_info "Step 4: Pattern Extraction Job"
    echo ""
    echo "Run pattern extraction (dry-run mode):"
    echo ""
    python3 -m agentos.jobs.info_need_pattern_extraction --days 7 --min-occurrences 5 --dry-run || print_error "Extraction requires MemoryOS data"

    wait_for_input

    # 2.5: Pattern Evolution
    print_info "Step 5: Pattern Evolution Tracking"
    echo ""
    echo "Check pattern evolution history:"
    sqlite3 -header -column store/registry.sqlite "
        SELECT
            evolution_type,
            COUNT(*) as count,
            datetime(MAX(timestamp)) as latest
        FROM pattern_evolution
        GROUP BY evolution_type;
    " || print_info "No pattern evolution yet"

    print_success "Memory Subsystem demo complete!"
    wait_for_input
}

##############################################################################
# Demo 3: Multi-Intent Processing Subsystem
##############################################################################
demo_multi_intent() {
    print_header "🧩 Demo 3: Multi-Intent Processing Subsystem"

    echo "This subsystem handles composite questions through:"
    echo "  • Intelligent question splitting (4 strategies)"
    echo "  • Context preservation (pronoun detection)"
    echo "  • Independent classification per sub-question"
    echo "  • Combined response generation"
    echo ""

    wait_for_input

    # 3.1: Splitting Detection
    print_info "Step 1: Multi-Intent Detection"
    echo ""
    echo "Test various question types:"
    echo ""

    python3 << 'EOF'
from agentos.core.chat.multi_intent_splitter import MultiIntentSplitter

splitter = MultiIntentSplitter()

test_cases = [
    "What time is it?",  # Single intent
    "What time is it? What phase are we in?",  # Multiple intents
    "现在几点？还有最新AI政策",  # Chinese connectors
    "1. What is Python? 2. What is Java?",  # Enumeration
]

for question in test_cases:
    should_split = splitter.should_split(question)
    print(f"Question: {question}")
    print(f"Should split: {should_split}")
    if should_split:
        sub_questions = splitter.split(question)
        print(f"Sub-questions ({len(sub_questions)}):")
        for sq in sub_questions:
            print(f"  [{sq.index}] {sq.text}")
            if sq.needs_context:
                print(f"      (needs context: {sq.context_hint})")
    print()
EOF

    wait_for_input

    # 3.2: Splitting Strategies
    print_info "Step 2: Splitting Strategies"
    echo ""
    echo "Four splitting strategies implemented:"
    echo ""
    echo "1. Connector-based:"
    echo "   CN: 以及, 还有, 另外, 同时, 顺便"
    echo "   EN: and also, also, additionally, as well as"
    echo ""
    echo "2. Punctuation-based:"
    echo "   Patterns: .？ .? ； ;"
    echo ""
    echo "3. Enumeration-based:"
    echo "   Numeric: 1. 2. 3. or 1) 2) 3)"
    echo "   Ordinal: First, Second, or 第一, 第二,"
    echo ""
    echo "4. Question mark splitting:"
    echo "   Multiple ? or ？ in sequence"
    echo ""

    wait_for_input

    # 3.3: Context Preservation
    print_info "Step 3: Context Preservation"
    echo ""
    echo "Test context detection:"
    echo ""

    python3 << 'EOF'
from agentos.core.chat.multi_intent_splitter import MultiIntentSplitter

splitter = MultiIntentSplitter()

questions = [
    "Who is the CEO? What are his policies?",  # Pronoun reference
    "And what about the other option?",  # Incomplete sentence
]

for question in questions:
    result = splitter.split(question)
    print(f"Question: {question}")
    for sq in result:
        print(f"  [{sq.index}] {sq.text}")
        if sq.needs_context:
            print(f"      → Needs context: {sq.context_hint}")
    print()
EOF

    wait_for_input

    # 3.4: Performance
    print_info "Step 4: Performance Benchmark"
    echo ""
    echo "Measuring splitting speed..."
    echo ""

    python3 << 'EOF'
import time
from agentos.core.chat.multi_intent_splitter import MultiIntentSplitter

splitter = MultiIntentSplitter()

test_questions = [
    "What time? What weather?",
    "现在几点？还有最新AI政策",
    "1. What is Python? 2. What is Java?",
]

total_time = 0
iterations = 1000

for question in test_questions:
    start = time.time()
    for _ in range(iterations):
        splitter.split(question)
    elapsed = time.time() - start
    total_time += elapsed
    avg_ms = (elapsed / iterations) * 1000
    print(f"Question: {question}")
    print(f"Average time: {avg_ms:.4f} ms")
    print()

avg_overall = (total_time / (len(test_questions) * iterations)) * 1000
print(f"Overall average: {avg_overall:.4f} ms")
print(f"Target: < 5 ms")
print(f"Status: {'✓ PASS' if avg_overall < 5 else '✗ FAIL'}")
EOF

    wait_for_input

    # 3.5: ChatEngine Integration
    print_info "Step 5: ChatEngine Integration"
    echo ""
    echo "Multi-intent flow in ChatEngine:"
    echo ""
    echo "1. User sends composite question"
    echo "2. ChatEngine detects multiple intents"
    echo "3. MultiIntentSplitter splits into sub-questions"
    echo "4. Each sub-question classified independently"
    echo "5. Each sub-question processed based on classification"
    echo "6. Results combined into structured response"
    echo "7. Audit log records MULTI_INTENT_SPLIT event"
    echo ""
    echo "Check recent multi-intent splits:"
    sqlite3 -header -column store/registry.sqlite "
        SELECT
            json_extract(metadata, '$.sub_count') as sub_count,
            substr(json_extract(metadata, '$.original_question'), 1, 50) as question,
            datetime(timestamp) as time
        FROM task_audits
        WHERE event_type = 'MULTI_INTENT_SPLIT'
        ORDER BY timestamp DESC
        LIMIT 10;
    " || print_info "No multi-intent splits yet"

    print_success "Multi-Intent Processing demo complete!"
    wait_for_input
}

##############################################################################
# Demo 4: End-to-End Integration
##############################################################################
demo_end_to_end() {
    print_header "🔗 Demo 4: End-to-End System Integration"

    echo "This demo shows how all three subsystems work together."
    echo ""

    wait_for_input

    print_info "Scenario: User asks composite question with external info need"
    echo ""
    echo "User input: 'What time is it? And what is the latest AI policy?'"
    echo ""

    wait_for_input

    print_info "Step 1: Multi-Intent Detection"
    echo "✓ Detected 2 intents"
    echo "  • Sub-question 1: 'What time is it?'"
    echo "  • Sub-question 2: 'what is the latest AI policy?'"
    echo ""

    wait_for_input

    print_info "Step 2: Classification (for each sub-question)"
    echo ""
    echo "Sub-question 1: 'What time is it?'"
    echo "  • Type: AMBIENT_STATE"
    echo "  • Action: LOCAL_CAPABILITY"
    echo "  • Confidence: HIGH"
    echo "  • Rule signals: ambient_state_keywords=['time']"
    echo ""
    echo "Sub-question 2: 'what is the latest AI policy?'"
    echo "  • Type: EXTERNAL_FACT_UNCERTAIN"
    echo "  • Action: REQUIRE_COMM"
    echo "  • Confidence: HIGH"
    echo "  • Rule signals: time_sensitive_keywords=['latest']"
    echo ""

    wait_for_input

    print_info "Step 3: Audit Logging"
    echo "✓ Logged MULTI_INTENT_SPLIT event"
    echo "✓ Logged INFO_NEED_CLASSIFICATION (x2)"
    echo ""

    wait_for_input

    print_info "Step 4: MemoryOS Writing"
    echo "✓ Wrote judgment for sub-question 1"
    echo "✓ Wrote judgment for sub-question 2"
    echo "  • outcome: pending (awaiting user feedback)"
    echo ""

    wait_for_input

    print_info "Step 5: Processing"
    echo ""
    echo "Sub-question 1 (AMBIENT_STATE):"
    echo "  → Query system state"
    echo "  → Return: 'Current time: 2026-01-31 10:30:00'"
    echo ""
    echo "Sub-question 2 (REQUIRE_COMM):"
    echo "  → Create ExternalInfoDeclaration"
    echo "  → Return: 'External information required. Use: /comm search latest AI policy'"
    echo ""

    wait_for_input

    print_info "Step 6: Response Combination"
    echo ""
    echo "Combined response:"
    echo "────────────────────────────────────────"
    echo "You asked 2 questions. Here are the answers:"
    echo ""
    echo "**1. What time is it?**"
    echo "[Classification: AMBIENT_STATE]"
    echo "Current time: 2026-01-31 10:30:00"
    echo ""
    echo "**2. what is the latest AI policy?**"
    echo "[Classification: EXTERNAL_FACT_UNCERTAIN]"
    echo "External information required."
    echo "Suggestion: Use /comm search latest AI policy"
    echo "────────────────────────────────────────"
    echo ""

    wait_for_input

    print_info "Step 7: User Action & Outcome Update"
    echo ""
    echo "User uses /comm search → Classification validated!"
    echo ""
    echo "MemoryOS update:"
    echo "  • Sub-question 1 outcome: validated"
    echo "  • Sub-question 2 outcome: validated"
    echo "  • user_action: used_communication"
    echo ""

    wait_for_input

    print_info "Step 8: Pattern Learning (Daily Job)"
    echo ""
    echo "Next day at 2 AM:"
    echo "  • Extract features from recent judgments"
    echo "  • Cluster similar patterns"
    echo "  • Update/create patterns in BrainOS"
    echo "  • Track pattern evolution"
    echo ""
    echo "Example pattern learned:"
    echo "  pattern_signature: 'time_sensitive|question_mark|length_medium'"
    echo "  classification_type: EXTERNAL_FACT_UNCERTAIN"
    echo "  occurrence_count: 127"
    echo "  success_rate: 0.94"
    echo "  example_questions:"
    echo "    • 'What is the latest AI policy?'"
    echo "    • 'Latest Python 3.13 features?'"
    echo "    • '最新AI政策是什么？'"
    echo ""

    wait_for_input

    print_info "Step 9: Metrics Calculation"
    echo ""
    echo "Weekly metrics update:"
    echo "  • comm_trigger_rate: 0.30 (30% require external info)"
    echo "  • false_positive_rate: 0.05 (5% unnecessary comm)"
    echo "  • false_negative_rate: 0.03 (3% missed external need)"
    echo "  • ambient_hit_rate: 0.98 (98% ambient queries correct)"
    echo "  • decision_latency (p95): 150ms"
    echo "  • decision_stability: 0.92 (92% consistent)"
    echo ""
    echo "WebUI Dashboard updated automatically."
    echo ""

    print_success "End-to-End Integration demo complete!"
    wait_for_input
}

##############################################################################
# Main Script
##############################################################################

echo -e "${GREEN}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║    EVOLVABLE SYSTEM DEMONSTRATION                                ║
║                                                                  ║
║    "From Judgment System to Evolvable System"                   ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo "This demonstration covers:"
echo "  📊 Quality Monitoring Subsystem"
echo "  🧠 Memory Subsystem"
echo "  🧩 Multi-Intent Processing Subsystem"
echo "  🔗 End-to-End Integration"
echo ""

case $SUBSYSTEM in
    quality)
        demo_quality_monitoring
        ;;
    memory)
        demo_memory_subsystem
        ;;
    multi-intent)
        demo_multi_intent
        ;;
    e2e)
        demo_end_to_end
        ;;
    all)
        demo_quality_monitoring
        demo_memory_subsystem
        demo_multi_intent
        demo_end_to_end
        ;;
    *)
        print_error "Unknown subsystem: $SUBSYSTEM"
        echo "Usage: $0 [quality|memory|multi-intent|e2e|all]"
        exit 1
        ;;
esac

print_header "🎉 Demonstration Complete!"

echo "For more information:"
echo "  • Final Acceptance Report: EVOLVABLE_SYSTEM_FINAL_ACCEPTANCE_REPORT.md"
echo "  • Architecture Guide: docs/EVOLVABLE_SYSTEM_ARCHITECTURE.md"
echo "  • Developer Guide: docs/EVOLVABLE_SYSTEM_DEVELOPER_GUIDE.md"
echo "  • Quick Reference: EVOLVABLE_SYSTEM_QUICK_REFERENCE.md"
echo ""
echo "To explore interactively:"
echo "  • WebUI: python -m agentos.webui.app"
echo "  • Metrics CLI: agentos metrics show --last 7d"
echo "  • Pattern Extraction: python -m agentos.jobs.info_need_pattern_extraction --dry-run"
echo ""

print_success "Thank you for exploring the Evolvable System!"
