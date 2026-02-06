"""Communication command handlers for /comm namespace.

This module implements the /comm command routing and handlers for Chat Mode
to securely interact with CommunicationOS. The /comm namespace is the ONLY
sanctioned channel for Chat to access external resources.

Architecture:
- Phase Gate: Commands are BLOCKED during planning phase
- Security: All requests go through CommunicationService policy enforcement
- Audit: All commands are logged for traceability

Commands:
- /comm search <query> - Execute web search
- /comm fetch <url> - Fetch URL content
- /comm brief ai [--today] - Generate AI topic brief

Design Principles:
1. Fail-Safe: Block by default in planning phase
2. Explicit: Clear error messages for blocked operations
3. Auditable: All commands logged with context
4. Isolated: No direct connector access, only through service layer
"""

import logging
import asyncio
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from agentos.core.chat.commands import CommandResult, get_registry
from agentos.core.time import utc_now_iso


logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async code from sync context.

    Handles both scenarios:
    - If event loop is already running (e.g., in WebUI), use asyncio.ensure_future
    - If no event loop, create one with asyncio.run

    Args:
        coro: Coroutine to run

    Returns:
        Result from coroutine
    """
    try:
        # Try to get the current running loop
        loop = asyncio.get_running_loop()
        # If we get here, we're in an async context
        # We need to run the coroutine in the current loop
        future = asyncio.ensure_future(coro)
        # Since we can't await here, we need to run until complete
        # But we can't use run_until_complete on a running loop
        # So we use a hack with threading
        import concurrent.futures
        import threading

        result_holder = {}
        exception_holder = {}

        def run_in_thread():
            try:
                # Create a new event loop for this thread
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result = new_loop.run_until_complete(coro)
                    result_holder['result'] = result
                finally:
                    new_loop.close()
            except Exception as e:
                exception_holder['exception'] = e

        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()

        if 'exception' in exception_holder:
            raise exception_holder['exception']

        return result_holder.get('result')

    except RuntimeError:
        # No event loop running, safe to use asyncio.run
        return asyncio.run(coro)


class BlockedError(Exception):
    """Exception raised when command is blocked by phase gate."""
    pass


class CommCommandHandler:
    """Handler for /comm namespace commands.

    Provides secure routing between Chat and CommunicationOS.
    All commands enforce phase gate checks and audit logging.
    """

    @staticmethod
    def _format_search_results(result: dict) -> str:
        """Format search results as Markdown.

        Args:
            result: Search result dictionary from CommunicationAdapter

        Returns:
            Markdown formatted string
        """
        # Error handling - SSRF Protection or Blocked
        if result.get("status") == "blocked":
            reason = result.get("reason", "")
            md = "## ❌ 搜索被阻止\n\n"
            md += f"**原因**: {result.get('message', '请求被阻止')}\n\n"
            if result.get("hint"):
                md += f"**提示**: {result['hint']}\n"
            return md

        # Error handling - Rate Limited
        if result.get("status") == "rate_limited":
            retry_after = result.get("retry_after", 60)
            md = "## ⏱️ 超过速率限制\n\n"
            md += f"请等待 **{retry_after} 秒**后重试。\n"
            return md

        # Error handling - Generic Error
        if result.get("status") == "error":
            md = "## ❌ 搜索失败\n\n"
            md += f"**错误**: {result.get('message', '未知错误')}\n"
            return md

        # Success - Format search results
        metadata = result.get("metadata", {})
        results = result.get("results", [])
        query = metadata.get("query", "")
        total_results = metadata.get("total_results", 0)

        md = f"# 搜索结果：{query}\n\n"
        md += f"找到 **{total_results}** 条结果（显示前 {len(results)} 条）：\n\n"

        # Display each search result
        for i, item in enumerate(results, 1):
            title = item.get("title", "无标题")
            url = item.get("url", "")
            snippet = item.get("snippet", "无摘要")
            trust_tier = item.get("trust_tier", "search_result")

            md += f"## {i}. {title}\n"
            md += f"**URL**: {url}\n\n"
            md += f"**摘要**: {snippet}\n\n"
            md += f"**Trust Tier**: `{trust_tier}` （候选来源，需验证）\n\n"

        md += "---\n\n"

        # Add trust tier warning
        trust_warning = metadata.get("trust_tier_warning", "搜索结果是候选来源，不是验证事实")
        md += f"## ⚠️ 注意\n\n**{trust_warning}**\n\n"
        md += "建议使用 `/comm fetch <url>` 验证内容。\n\n"

        # Attribution and audit information
        md += "---\n\n"
        md += f"📝 **来源归因**: {metadata.get('attribution', 'CommunicationOS')}\n\n"
        md += f"🔍 **审计ID**: {metadata.get('audit_id', 'N/A')}\n\n"

        # Additional metadata
        if metadata.get("engine"):
            md += f"🔧 **搜索引擎**: {metadata['engine']}\n\n"

        if metadata.get("retrieved_at"):
            md += f"⏰ **检索时间**: {metadata['retrieved_at']}\n"

        return md

    @staticmethod
    def _format_fetch_results(result: dict) -> str:
        """Format fetch results as Markdown.

        Args:
            result: Fetch result dictionary from CommunicationAdapter

        Returns:
            Markdown formatted string
        """
        # Error handling - SSRF Protection
        if result.get("status") == "blocked":
            reason = result.get("reason", "")
            if reason == "SSRF_PROTECTION":
                md = "## 🛡️ SSRF 防护\n\n"
                md += f"**{result.get('message', '请求被阻止')}**\n\n"
                md += f"**提示**: {result.get('hint', '请使用公开的 HTTPS URL')}\n"
                return md

            md = "## ❌ 请求被阻止\n\n"
            md += f"{result.get('message', '未知原因')}\n"
            return md

        # Error handling - Rate Limited
        if result.get("status") == "rate_limited":
            retry_after = result.get("retry_after", 60)
            md = "## ⏱️ 超过速率限制\n\n"
            md += f"请等待 **{retry_after} 秒**后重试。\n"
            return md

        # Error handling - Requires Approval
        if result.get("status") == "requires_approval":
            md = "## 🔐 需要管理员批准\n\n"
            md += f"{result.get('message', '该操作需要管理员批准')}\n\n"
            if result.get("hint"):
                md += f"**详情**: {result['hint']}\n"
            return md

        # Error handling - Generic Error
        if result.get("status") == "error":
            md = "## ❌ 抓取失败\n\n"
            md += f"**错误**: {result.get('message', '未知错误')}\n"
            return md

        # Success - Format fetched content
        url = result.get("url", "")
        content = result.get("content", {})
        metadata = result.get("metadata", {})

        md = f"# 抓取结果：{url}\n\n"
        md += f"**状态**: ✅ 成功\n"
        md += f"**抓取时间**: {metadata.get('retrieved_at', '')}\n"
        md += f"**Trust Tier**: `{metadata.get('trust_tier', 'external_source')}`\n"

        # Content hash (truncated)
        content_hash = metadata.get('content_hash', '')
        if content_hash:
            md += f"**内容哈希**: `{content_hash[:16]}...`\n"

        md += "\n---\n\n"
        md += "## 提取内容\n\n"

        # Title
        if content.get("title"):
            md += f"### 标题\n{content['title']}\n\n"

        # Description
        if content.get("description"):
            md += f"### 描述\n{content['description']}\n\n"

        # Main content (truncated to 500 chars)
        if content.get("text"):
            text = content["text"]
            if len(text) > 500:
                text = text[:500] + "..."
            md += f"### 主要内容（摘要）\n{text}\n\n"

        # Links (show first 5)
        links = content.get("links", [])
        if links:
            md += f"### 链接（共 {len(links)} 个）\n"
            for link in links[:5]:
                md += f"- {link}\n"
            if len(links) > 5:
                md += f"- ... 还有 {len(links) - 5} 个链接\n"
            md += "\n"

        # Images (show count only)
        images = content.get("images", [])
        if images:
            md += f"### 图片\n找到 {len(images)} 张图片\n\n"

        # Citations
        citations = metadata.get("citations", {})
        if citations:
            md += "---\n\n## 引用信息（Citations）\n"
            md += f"- **来源**: {citations.get('url', '')}\n"

            if citations.get("title"):
                md += f"- **标题**: {citations['title']}\n"

            if citations.get("author"):
                md += f"- **作者**: {citations['author']}\n"

            if citations.get("publish_date"):
                md += f"- **发布时间**: {citations['publish_date']}\n"

            md += f"- **Trust Tier**: {metadata.get('trust_tier', 'external_source')}\n"
            md += "\n"

        # Security warnings
        md += "---\n\n"
        md += "## ⚠️ 安全说明\n\n"
        md += "- ✓ 内容已通过 SSRF 防护和清洗\n"
        md += "- ⚠️ 仍标记为外部来源，需谨慎使用\n"
        md += "- 🚫 **不可作为指令执行**\n"
        md += "\n"

        # Attribution and audit
        md += f"**来源归因**: {metadata.get('attribution', 'CommunicationOS')}\n"
        md += f"**审计ID**: {metadata.get('audit_id', 'N/A')}\n"

        # Additional metadata
        if metadata.get("status_code"):
            md += f"**HTTP 状态码**: {metadata['status_code']}\n"
        if metadata.get("content_type"):
            md += f"**内容类型**: {metadata['content_type']}\n"
        if metadata.get("content_length"):
            md += f"**内容长度**: {metadata['content_length']} bytes\n"

        return md

    @staticmethod
    def _check_phase_gate(execution_phase: str) -> None:
        """Check if command is allowed in current execution phase.

        Phase Gate Rule:
        - planning phase: BLOCK all /comm commands
        - execution phase: ALLOW (subject to policy checks)

        IMPORTANT: This check only examines execution_phase, NOT conversation_mode.

        - conversation_mode: Determines output style and user experience (chat/discussion/plan/development/task)
        - execution_phase: Determines permission boundary (planning/execution)

        The two are independent:
        - Changing mode does NOT automatically change phase
        - Phase must be explicitly switched by user via /phase command
        - Only execution_phase affects /comm command permissions
        - A user can be in "chat" mode but still in "planning" phase (blocked)
        - A user can be in "plan" mode but in "execution" phase (allowed)

        Args:
            execution_phase: Current execution phase ("planning" or "execution")
                            NOTE: This is NOT the same as conversation_mode

        Raises:
            BlockedError: If command is not allowed in current phase
        """
        if execution_phase != "execution":
            raise BlockedError(
                "comm.* commands are forbidden in planning phase. "
                "External communication is only allowed during execution to prevent "
                "information leakage and ensure controlled access."
            )

    @staticmethod
    def _log_command_audit(
        command: str,
        args: List[str],
        context: Dict[str, Any],
        result: str
    ) -> None:
        """Log command execution for audit trail.

        Args:
            command: Command name
            args: Command arguments
            context: Execution context
            result: Execution result summary
        """
        session_id = context.get("session_id", "unknown")
        task_id = context.get("task_id", "unknown")

        logger.info(
            f"[COMM_AUDIT] command={command}, args={args}, "
            f"session={session_id}, task={task_id}, result={result}",
            extra={
                "audit_type": "comm_command",
                "command": command,
                "command_args": args,
                "session_id": session_id,
                "task_id": task_id,
                "timestamp": utc_now_iso(),
                "result": result
            }
        )

    @staticmethod
    def handle_search(
        command: str,
        args: List[str],
        context: Dict[str, Any]
    ) -> CommandResult:
        """Handle /comm search <query> [--max-results N] command.

        Executes web search through CommunicationService.

        Args:
            command: Command name ("search")
            args: Command arguments [query_text, ..., --max-results, N]
            context: Execution context with session_id, task_id, execution_phase

        Returns:
            CommandResult with search results or error
        """
        try:
            # Phase Gate: Block in planning phase
            execution_phase = context.get("execution_phase", "planning")
            CommCommandHandler._check_phase_gate(execution_phase)

            # Parse arguments
            if not args:
                return CommandResult.error_result(
                    "Usage: /comm search <query> [--max-results N]\n"
                    "Example: /comm search latest AI developments\n"
                    "Example: /comm search Python tutorial --max-results 5"
                )

            # Parse --max-results flag
            max_results = 10  # Default
            query_parts = []

            i = 0
            while i < len(args):
                if args[i] == "--max-results":
                    if i + 1 < len(args):
                        try:
                            max_results = int(args[i + 1])
                            i += 2
                            continue
                        except ValueError:
                            return CommandResult.error_result(
                                f"Invalid --max-results value: {args[i + 1]}\n"
                                "Must be a positive integer"
                            )
                    else:
                        return CommandResult.error_result(
                            "--max-results requires a numeric argument"
                        )
                query_parts.append(args[i])
                i += 1

            if not query_parts:
                return CommandResult.error_result(
                    "No search query provided.\n"
                    "Usage: /comm search <query> [--max-results N]"
                )

            query = " ".join(query_parts)

            # Call CommunicationAdapter to execute search
            from agentos.core.chat.communication_adapter import CommunicationAdapter

            adapter = CommunicationAdapter()

            # Execute async search
            result = _run_async(
                adapter.search(
                    query=query,
                    session_id=context.get("session_id", "unknown"),
                    task_id=context.get("task_id", "unknown"),
                    max_results=max_results
                )
            )

            # Format results as Markdown
            result_message = CommCommandHandler._format_search_results(result)

            # Audit log
            status = result.get("status", "success")
            CommCommandHandler._log_command_audit(
                command="search",
                args=args,
                context=context,
                result=status
            )

            # Return appropriate result based on status
            if status == "error" or status == "blocked" or status == "rate_limited":
                return CommandResult.error_result(result_message)
            else:
                return CommandResult.success_result(result_message)

        except BlockedError as e:
            # Phase gate blocked the command
            error_msg = f"🚫 Command blocked: {str(e)}"
            CommCommandHandler._log_command_audit(
                command="search",
                args=args,
                context=context,
                result="blocked_by_phase_gate"
            )
            return CommandResult.error_result(error_msg)

        except Exception as e:
            logger.error(f"Search command failed: {e}", exc_info=True)
            CommCommandHandler._log_command_audit(
                command="search",
                args=args,
                context=context,
                result=f"error: {str(e)}"
            )
            return CommandResult.error_result(f"Search failed: {str(e)}")

    @staticmethod
    def handle_fetch(
        command: str,
        args: List[str],
        context: Dict[str, Any]
    ) -> CommandResult:
        """Handle /comm fetch <url> [--extract] command.

        Fetches URL content through CommunicationService.

        Args:
            command: Command name ("fetch")
            args: Command arguments [url, optional flags]
            context: Execution context with session_id, task_id, execution_phase

        Returns:
            CommandResult with fetched content or error
        """
        try:
            # Phase Gate: Block in planning phase
            execution_phase = context.get("execution_phase", "planning")
            CommCommandHandler._check_phase_gate(execution_phase)

            # Parse arguments
            if not args:
                return CommandResult.error_result(
                    "Usage: /comm fetch <url> [--extract]\n"
                    "Example: /comm fetch https://example.com/article"
                )

            # Extract URL and flags
            url = args[0]
            extract_content = True  # Default to true

            # Parse flags
            if len(args) > 1:
                flags = args[1:]
                if "--extract" in flags:
                    extract_content = True
                if "--no-extract" in flags:
                    extract_content = False

            # Basic URL validation
            if not url.startswith(("http://", "https://")):
                return CommandResult.error_result(
                    f"Invalid URL: {url}\n"
                    "URL must start with http:// or https://"
                )

            # Call CommunicationAdapter to fetch URL
            from agentos.core.chat.communication_adapter import CommunicationAdapter

            adapter = CommunicationAdapter()

            # Execute async fetch
            result = _run_async(
                adapter.fetch(
                    url=url,
                    session_id=context.get("session_id", "unknown"),
                    task_id=context.get("task_id", "unknown"),
                    extract_content=extract_content
                )
            )

            # Format results as Markdown
            result_message = CommCommandHandler._format_fetch_results(result)

            # Audit log
            status = result.get("status", "unknown")
            CommCommandHandler._log_command_audit(
                command="fetch",
                args=args,
                context=context,
                result=status
            )

            if status == "success":
                return CommandResult.success_result(result_message)
            else:
                return CommandResult.error_result(result_message)

        except BlockedError as e:
            # Phase gate blocked the command
            error_msg = f"🚫 Command blocked: {str(e)}"
            CommCommandHandler._log_command_audit(
                command="fetch",
                args=args,
                context=context,
                result="blocked_by_phase_gate"
            )
            return CommandResult.error_result(error_msg)

        except Exception as e:
            logger.error(f"Fetch command failed: {e}", exc_info=True)
            CommCommandHandler._log_command_audit(
                command="fetch",
                args=args,
                context=context,
                result=f"error: {str(e)}"
            )
            return CommandResult.error_result(f"Fetch failed: {str(e)}")

    @staticmethod
    async def _multi_query_search(adapter, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute multiple search queries in parallel.

        Args:
            adapter: CommunicationAdapter instance
            context: Execution context

        Returns:
            Combined list of search results from all queries
        """
        queries = [
            "AI news today",
            "artificial intelligence regulation",
            "AI chips policy",
            "AI research breakthrough"
        ]

        all_results = []
        for query in queries:
            try:
                result = await adapter.search(
                    query=query,
                    session_id=context["session_id"],
                    task_id=context.get("task_id", "unknown"),
                    max_results=5
                )

                if result.get("status") != "error" and "results" in result:
                    all_results.extend(result["results"])
            except Exception as e:
                logger.warning(f"Search query '{query}' failed: {e}")
                # Continue with other queries

        return all_results

    @staticmethod
    def _filter_candidates(results: List[Dict[str, Any]], max_candidates: int = 14) -> List[Dict[str, Any]]:
        """Filter and deduplicate search results.

        Args:
            results: List of search results
            max_candidates: Maximum number of candidates to return

        Returns:
            Filtered and deduplicated list of candidates
        """
        from urllib.parse import urlparse

        # URL deduplication
        seen_urls = set()
        domain_counts = {}
        filtered = []

        for item in results:
            url = item.get("url", "")
            if not url:
                continue

            # Validate URL format
            if not url.startswith(("http://", "https://")):
                logger.debug(f"Skipping invalid URL (missing scheme): {url}")
                continue

            try:
                # Normalize URL (remove query params and fragments)
                parsed = urlparse(url)

                # Ensure we have a valid domain
                if not parsed.netloc:
                    logger.debug(f"Skipping invalid URL (no domain): {url}")
                    continue

                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

                # Skip duplicate URLs
                if normalized in seen_urls:
                    continue

                # Domain limiting (max 2 per domain)
                domain = parsed.netloc
                if domain_counts.get(domain, 0) >= 2:
                    continue

                seen_urls.add(normalized)
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
                filtered.append(item)

                if len(filtered) >= max_candidates:
                    break
            except Exception as e:
                logger.warning(f"Failed to parse URL {url}: {e}")
                continue

        return filtered

    @staticmethod
    async def _fetch_and_verify(
        adapter,
        candidates: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Fetch and verify candidate URLs with concurrency control.

        Args:
            adapter: CommunicationAdapter instance
            candidates: List of candidate URLs to verify
            context: Execution context

        Returns:
            List of verified results with extracted content
        """
        import asyncio
        from urllib.parse import urlparse

        verified = []
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent fetches

        async def fetch_one(candidate):
            async with semaphore:
                try:
                    result = await adapter.fetch(
                        url=candidate["url"],
                        session_id=context["session_id"],
                        task_id=context.get("task_id", "unknown"),
                        extract_content=True
                    )

                    if result.get("status") == "success":
                        content = result.get("content", {})
                        metadata = result.get("metadata", {})

                        return {
                            "url": candidate["url"],
                            "title": content.get("title") or candidate.get("title", "无标题"),
                            "summary": content.get("description") or candidate.get("snippet", ""),
                            "text": content.get("text", ""),
                            "retrieved_at": metadata.get("retrieved_at", ""),
                            "trust_tier": metadata.get("trust_tier", "external_source"),
                            "domain": urlparse(candidate["url"]).netloc
                        }
                except Exception as e:
                    logger.debug(f"Fetch failed for {candidate.get('url')}: {e}")
                    # Skip failed fetches
                return None

        # Parallel fetch with semaphore control
        tasks = [fetch_one(c) for c in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None and exceptions
        verified = [
            r for r in results
            if r is not None and not isinstance(r, Exception)
        ]

        return verified

    @staticmethod
    def _format_brief(verified: List[Dict[str, Any]], metadata: Dict[str, Any]) -> str:
        """Format brief as Markdown using frozen template.

        Args:
            verified: List of verified items
            metadata: Brief metadata (date, stats, etc.)

        Returns:
            Markdown formatted brief
        """
        if len(verified) == 0:
            return (
                "❌ 生成简报失败：无法验证任何来源\n\n"
                "请稍后重试或使用 /comm search 手动搜索。"
            )

        md = f"# 今日 AI 相关新闻简报（{metadata['date']}）\n\n"
        md += f"**生成时间**：{metadata['timestamp']}\n"
        md += f"**来源**：CommunicationOS（search + fetch）\n"
        md += f"**范围**：AI / Policy / Industry / Security\n\n"
        md += "---\n\n"

        for i, item in enumerate(verified, 1):
            summary = item.get("summary", "")
            if len(summary) > 200:
                summary = summary[:200] + "..."

            # Simple importance heuristic
            importance = CommCommandHandler._generate_importance(item)

            md += f"## {i}) {item['title']}\n"
            md += f"- **要点**：{summary}\n"
            md += f"- **为什么重要**：{importance}\n"
            md += f"- **来源**：[{item['domain']}]({item['url']})\n"
            md += f"- **抓取时间**：{item['retrieved_at']}\n"
            md += f"- **Trust Tier**：`{item['trust_tier']}`\n\n"
            md += "---\n\n"

        md += "## 统计信息\n"
        md += f"- 搜索查询：{metadata['search_queries']} 个\n"
        md += f"- 候选结果：{metadata['candidates']} 条\n"
        md += f"- 验证来源：{metadata['verified']} 条\n"
        md += f"- 生成耗时：{metadata.get('duration', 'N/A')}\n\n"

        md += "---\n\n"
        md += "⚠️ **重要说明**：\n"
        md += "- 搜索结果是候选来源生成器，不是真理来源\n"
        md += "- 所有内容已通过 fetch 验证并标记 Trust Tier\n"
        md += "- Evidence 和审计记录已保存到 CommunicationOS\n"

        return md

    @staticmethod
    def _generate_importance(item: Dict[str, Any]) -> str:
        """Generate simple importance statement based on content.

        Args:
            item: Verified item with title, summary, text

        Returns:
            Importance statement
        """
        # Simple rule-based importance generation
        text = (item.get("text", "") + " " + item.get("summary", "")).lower()

        if "regulation" in text or "policy" in text or "law" in text:
            return "监管政策对 AI 行业发展具有重要影响"
        elif "breakthrough" in text or "innovation" in text or "research" in text:
            return "技术突破可能改变 AI 应用格局"
        elif "security" in text or "privacy" in text or "risk" in text:
            return "安全和隐私问题是 AI 部署的关键考量"
        elif "chip" in text or "hardware" in text or "gpu" in text:
            return "硬件基础设施决定 AI 算力供给"
        elif "investment" in text or "funding" in text or "market" in text:
            return "资本动向反映行业发展趋势"
        else:
            return "该事件对 AI 领域具有参考价值"

    @staticmethod
    def handle_brief(
        command: str,
        args: List[str],
        context: Dict[str, Any]
    ) -> CommandResult:
        """Handle /comm brief <topic> [--today] [--max-items N] command.

        Generates AI topic brief through CommunicationService pipeline with:
        - Multi-query search (4 queries)
        - Candidate filtering and deduplication
        - Fetch verification with concurrency control
        - Markdown generation using frozen template

        Args:
            command: Command name ("brief")
            args: Command arguments [topic, flags...]
            context: Execution context with session_id, task_id, execution_phase

        Returns:
            CommandResult with generated brief or error
        """
        import time

        try:
            # Phase Gate: Block in planning phase
            execution_phase = context.get("execution_phase", "planning")
            CommCommandHandler._check_phase_gate(execution_phase)

            # Parse arguments
            if not args:
                return CommandResult.error_result(
                    "Usage: /comm brief <topic> [--today] [--max-items N]\n"
                    "Example: /comm brief ai --today\n"
                    "Example: /comm brief ai --max-items 5"
                )

            # Separate topic and flags
            topic = None
            today_only = False
            max_items = 7  # Default

            i = 0
            while i < len(args):
                arg = args[i]
                if arg == "--today":
                    today_only = True
                    i += 1
                elif arg == "--max-items":
                    if i + 1 < len(args):
                        try:
                            max_items = int(args[i + 1])
                            i += 2
                        except ValueError:
                            return CommandResult.error_result(
                                f"Invalid --max-items value: {args[i + 1]}"
                            )
                    else:
                        return CommandResult.error_result(
                            "--max-items requires a numeric argument"
                        )
                elif not arg.startswith("--"):
                    if topic is None:
                        topic = arg
                    i += 1
                else:
                    i += 1

            if not topic:
                return CommandResult.error_result(
                    "No topic specified.\n"
                    "Usage: /comm brief <topic> [--today] [--max-items N]"
                )

            # Validate topic
            if topic.lower() != "ai":
                return CommandResult.error_result(
                    f"❌ 暂不支持主题 '{topic}'，目前仅支持 'ai'"
                )

            # Start timer
            start_time = time.time()

            # Import adapter
            from agentos.core.chat.communication_adapter import CommunicationAdapter
            adapter = CommunicationAdapter()

            # Execute pipeline
            result_message = _run_async(
                CommCommandHandler._execute_brief_pipeline(
                    adapter, topic, max_items, today_only, context, start_time
                )
            )

            # Audit log
            CommCommandHandler._log_command_audit(
                command="brief",
                args=args,
                context=context,
                result="pipeline_success"
            )

            return CommandResult.success_result(result_message)

        except BlockedError as e:
            # Phase gate blocked the command
            error_msg = f"🚫 Command blocked: {str(e)}"
            CommCommandHandler._log_command_audit(
                command="brief",
                args=args,
                context=context,
                result="blocked_by_phase_gate"
            )
            return CommandResult.error_result(error_msg)

        except Exception as e:
            logger.error(f"Brief command failed: {e}", exc_info=True)
            CommCommandHandler._log_command_audit(
                command="brief",
                args=args,
                context=context,
                result=f"error: {str(e)}"
            )
            return CommandResult.error_result(f"Brief failed: {str(e)}")

    @staticmethod
    async def _execute_brief_pipeline(
        adapter,
        topic: str,
        max_items: int,
        today_only: bool,
        context: Dict[str, Any],
        start_time: float
    ) -> str:
        """Execute the complete brief generation pipeline.

        Args:
            adapter: CommunicationAdapter instance
            topic: Topic name
            max_items: Maximum items to include in brief
            today_only: Whether to filter by today's date
            context: Execution context
            start_time: Pipeline start time

        Returns:
            Markdown formatted brief
        """
        from agentos.core.communication.brief_generator import BriefGenerator

        # Step 1: Multi-query search
        logger.info(f"[Brief Pipeline] Step 1: Multi-query search for topic '{topic}'")
        search_results = await CommCommandHandler._multi_query_search(adapter, context)
        logger.info(f"[Brief Pipeline] Found {len(search_results)} search results")

        # Step 2: Candidate filtering
        logger.info(f"[Brief Pipeline] Step 2: Filtering candidates")
        candidates = CommCommandHandler._filter_candidates(
            search_results,
            max_candidates=max_items * 2
        )
        logger.info(f"[Brief Pipeline] Filtered to {len(candidates)} candidates")

        # Step 3: Fetch verification
        logger.info(f"[Brief Pipeline] Step 3: Fetch verification (max {max_items} items)")
        verified = await CommCommandHandler._fetch_and_verify(
            adapter,
            candidates[:max_items],
            context
        )
        logger.info(f"[Brief Pipeline] Verified {len(verified)} items")

        # Step 4: Phase Gate - Validate inputs with BriefGenerator
        logger.info(f"[Brief Pipeline] Step 4: Phase Gate - Validating inputs")
        generator = BriefGenerator(min_documents=3)
        is_valid, error_msg = generator.validate_inputs(verified)

        if not is_valid:
            # Phase gate failed - return error
            logger.error(f"[Brief Pipeline] Phase gate failed: {error_msg}")
            return (
                f"# Brief Generation Failed\n\n"
                f"## Phase Gate Error\n\n"
                f"{error_msg}\n\n"
                f"---\n\n"
                f"**Pipeline Stats**:\n"
                f"- Search queries: 4\n"
                f"- Candidates found: {len(candidates)}\n"
                f"- Documents verified: {len(verified)}\n"
                f"- Required minimum: 3 verified documents\n\n"
                f"**Recommendation**: Try expanding search criteria or verify more sources."
            )

        # Step 5: Generate brief with BriefGenerator
        logger.info(f"[Brief Pipeline] Step 5: Generating structured brief")
        brief_md = generator.generate_brief(verified, topic)

        # Add pipeline statistics footer
        elapsed = time.time() - start_time
        brief_md += f"\n\n---\n\n"
        brief_md += f"## Pipeline Statistics\n"
        brief_md += f"- Search queries executed: 4\n"
        brief_md += f"- Candidate results: {len(candidates)}\n"
        brief_md += f"- Documents verified: {len(verified)}\n"
        brief_md += f"- Generation time: {elapsed:.2f}s\n"

        logger.info(f"[Brief Pipeline] Brief generation completed in {elapsed:.2f}s")
        return brief_md


def handle_comm_command(
    command: str,
    args: List[str],
    context: Dict[str, Any]
) -> CommandResult:
    """Main router for /comm namespace commands.

    Routes /comm subcommands to appropriate handlers.

    Args:
        command: Main command name ("comm")
        args: Command arguments [subcommand, ...]
        context: Execution context

    Returns:
        CommandResult from subcommand handler
    """
    if not args:
        return CommandResult.error_result(
            "Usage: /comm <subcommand> [args...]\n\n"
            "Available subcommands:\n"
            "  search <query>      - Execute web search\n"
            "  fetch <url>         - Fetch URL content\n"
            "  brief <topic> [--today] - Generate topic brief\n\n"
            "Examples:\n"
            "  /comm search latest AI developments\n"
            "  /comm fetch https://example.com/article\n"
            "  /comm brief ai --today"
        )

    # Extract subcommand and remaining args
    subcommand = args[0].lower()
    subcommand_args = args[1:] if len(args) > 1 else []

    # Route to appropriate handler
    handlers = {
        "search": CommCommandHandler.handle_search,
        "fetch": CommCommandHandler.handle_fetch,
        "brief": CommCommandHandler.handle_brief,
    }

    handler = handlers.get(subcommand)
    if not handler:
        return CommandResult.error_result(
            f"Unknown subcommand: {subcommand}\n"
            f"Available: search, fetch, brief"
        )

    # Execute subcommand handler
    return handler(subcommand, subcommand_args, context)


def register_comm_command():
    """Register the /comm command and its subcommands."""
    registry = get_registry()
    registry.register(
        command="comm",
        handler=handle_comm_command,
        description="Communication commands (search, fetch, brief) - execution phase only"
    )
    logger.info("Registered /comm command namespace")
