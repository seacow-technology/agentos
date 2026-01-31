"""
Memory Extractor Demo

This script demonstrates the memory extraction functionality
with various example messages in both Chinese and English.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agentos.core.chat.memory_extractor import MemoryExtractor
from agentos.core.chat.models_base import ChatMessage
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


def demo_extraction():
    """Demonstrate memory extraction with various examples"""

    console.print("\n[bold cyan]Memory Extractor Demo[/bold cyan]\n")

    extractor = MemoryExtractor()

    # Test cases
    test_cases = [
        # Preferred names
        ("以后请叫我胖哥", "Chinese: Preferred name"),
        ("Call me John", "English: Preferred name"),
        ("我叫李明", "Chinese: My name is"),

        # Contact info
        ("我的邮箱是test@example.com", "Chinese: Email"),
        ("My email: john.doe@company.org", "English: Email"),
        ("我的手机号是13812345678", "Chinese: Phone"),

        # Company
        ("我在谷歌公司工作", "Chinese: Company"),
        ("I work at Microsoft Corp.", "English: Company"),

        # Technical preferences
        ("我喜欢使用Python语言", "Chinese: Tech preference"),
        ("I prefer React framework", "English: Tech preference"),
        ("我不喜欢Java", "Chinese: Tech dislike"),

        # Project context
        ("我的项目叫AgentOS", "Chinese: Project name"),
        ("This project is called MyApp", "English: Project name"),

        # Multiple extractions
        ("我叫张三，邮箱是zhangsan@test.com", "Multiple: Name + Email"),
        ("我的email是admin@example.com，请call me Admin", "Mixed: Email + Name"),

        # Negative cases
        ("请问你叫什么名字？", "Negative: Question"),
        ("What's your name?", "Negative: Question"),
    ]

    for content, description in test_cases:
        console.print(f"\n[bold yellow]Test Case:[/bold yellow] {description}")
        console.print(f"[dim]Input:[/dim] {content}")

        # Create message
        message = ChatMessage(
            message_id=f"msg-demo-{hash(content)}",
            session_id="sess-demo-001",
            role="user",
            content=content,
            created_at=datetime.now(timezone.utc),
            metadata={}
        )

        # Extract memories
        memories = extractor.extract_memories(message, "sess-demo-001", project_id="proj-demo")

        if memories:
            # Create table for results
            table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
            table.add_column("Type", style="cyan")
            table.add_column("Key", style="green")
            table.add_column("Value", style="yellow")
            table.add_column("Confidence", justify="right", style="blue")
            table.add_column("Scope", style="magenta")

            for memory in memories:
                table.add_row(
                    memory["type"],
                    memory["content"]["key"],
                    memory["content"]["value"],
                    f"{memory['confidence']:.1f}",
                    memory["scope"]
                )

            console.print(table)
        else:
            console.print("[dim]  No memories extracted[/dim]")

    # Statistics
    console.print(f"\n[bold green]Extractor Statistics:[/bold green]")
    console.print(f"  Total rules: {len(extractor.rules)}")

    rule_types = {}
    for rule in extractor.rules:
        rule_types[rule.memory_type] = rule_types.get(rule.memory_type, 0) + 1

    console.print(f"  Rules by type: {rule_types}")


def demo_negative_case_detection():
    """Demonstrate negative case detection"""

    console.print("\n\n[bold cyan]Negative Case Detection Demo[/bold cyan]\n")

    extractor = MemoryExtractor()

    test_cases = [
        ("以后叫我胖哥", True, "Should extract"),
        ("请问你叫什么名字", False, "Question - should not extract"),
        ("What's your name?", False, "Question - should not extract"),
        ("Can you tell me your email?", False, "Question - should not extract"),
        ("我的邮箱是test@test.com", True, "Should extract"),
    ]

    table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
    table.add_column("Message", style="white", width=40)
    table.add_column("Expected", justify="center", style="cyan")
    table.add_column("Negative?", justify="center", style="yellow")
    table.add_column("Status", justify="center")

    for content, should_extract, note in test_cases:
        message = ChatMessage(
            message_id="msg-test",
            session_id="sess-test",
            role="user",
            content=content,
            created_at=datetime.now(timezone.utc),
            metadata={}
        )

        is_negative = extractor.is_negative_case(message)
        expected_negative = not should_extract
        status = "✓" if is_negative == expected_negative else "✗"
        status_color = "green" if status == "✓" else "red"

        table.add_row(
            content,
            "Extract" if should_extract else "Skip",
            "Yes" if is_negative else "No",
            f"[{status_color}]{status}[/{status_color}]"
        )

    console.print(table)


def demo_memory_structure():
    """Demonstrate memory item structure"""

    console.print("\n\n[bold cyan]Memory Item Structure Demo[/bold cyan]\n")

    extractor = MemoryExtractor()

    message = ChatMessage(
        message_id="msg-demo-001",
        session_id="sess-demo-001",
        role="user",
        content="我叫胖哥，我的邮箱是pangge@example.com",
        created_at=datetime.now(timezone.utc),
        metadata={}
    )

    memories = extractor.extract_memories(message, "sess-demo-001", project_id="proj-001")

    for i, memory in enumerate(memories, 1):
        console.print(Panel.fit(
            f"""[bold]Memory Item #{i}[/bold]

[cyan]ID:[/cyan] {memory['id']}
[cyan]Type:[/cyan] {memory['type']}
[cyan]Scope:[/cyan] {memory['scope']}
[cyan]Confidence:[/cyan] {memory['confidence']}

[yellow]Content:[/yellow]
  Key: {memory['content']['key']}
  Value: {memory['content']['value']}
  Raw: {memory['content']['raw_text'][:50]}...

[green]Tags:[/green] {', '.join(memory['tags'])}

[magenta]Sources:[/magenta]
  Message ID: {memory['sources'][0]['message_id']}
  Session ID: {memory['sources'][0]['session_id']}
""",
            title="[bold blue]Extracted Memory[/bold blue]",
            border_style="blue"
        ))


if __name__ == "__main__":
    try:
        demo_extraction()
        demo_negative_case_detection()
        demo_memory_structure()

        console.print("\n[bold green]✓ Demo completed successfully![/bold green]\n")

    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]\n")
        import traceback
        traceback.print_exc()
