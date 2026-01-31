"""
FastAPI Application - AgentOS WebUI

Main application entry point for the Web Control Surface

Refactored in v0.3.2 (P1 Sprint):
- Added SessionStore initialization (SQLite persistent storage)
- Added config-based fallback to MemoryStore (degraded mode)
- WebUI data now persists across restarts
- Added Sentry error tracking and performance monitoring

Dependencies:
- sentry-sdk: Optional, for error monitoring in production
  If missing, the app will run in local dev mode without monitoring.
  Install: pip install sentry-sdk
"""

import logging
import os
import secrets
from pathlib import Path
from typing import Optional

# Sentry integration (optional for local development)
try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    sentry_sdk = None
    SENTRY_AVAILABLE = False

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

# Import API routers
from agentos.webui.api import health, sessions, tasks, events, skills, memory, config, logs, providers, selfcheck, context, runtime, providers_control, support, sessions_runtime, providers_lifecycle, providers_instances, providers_models, knowledge, history, share, preview, snippets, governance, guardians, lead, projects, task_dependencies, governance_dashboard, guardian, content, answers, auth, execution, dryrun, intent, auth_profiles, task_templates, task_events, evidence, mode_monitoring, extensions, extensions_execute, extension_templates, models, budget, brain, brain_governance, chat_commands, communication, mcp, info_need_metrics, metrics, decision_comparison, review_queue, channels, channels_marketplace, capability, voice, voice_twilio, apps
from agentos.webui.api import secrets as secrets_api  # Avoid conflict with stdlib secrets
# v0.31 API routers
from agentos.webui.api import projects_v31, repos_v31, tasks_v31_extension
# WebSocket and SSE routers
from agentos.webui.websocket import chat, events as ws_events
from agentos.webui.sse import task_events as sse_task_events

# Import SessionStore
from agentos.webui.store import SQLiteSessionStore, MemorySessionStore

# Import custom rate limit key function (L-1: Test bypass)
from agentos.webui.middleware.rate_limit import get_rate_limit_key

logger = logging.getLogger(__name__)

# Initialize Sentry for error tracking, performance monitoring, and release health
# Disabled by default in development to avoid CSP conflicts and external dependencies
# Set SENTRY_ENABLED=true in production to enable error monitoring
SENTRY_ENABLED = os.getenv("SENTRY_ENABLED", "false").lower() == "true"
# Sentry Configuration: 默认关闭，显式设置才启用
# 不提供默认 DSN，避免误上报本地敏感信息
SENTRY_DSN = os.getenv("SENTRY_DSN")  # 无默认值
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "development")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0"))
SENTRY_PROFILES_SAMPLE_RATE = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "1.0"))
SENTRY_RELEASE = os.getenv("SENTRY_RELEASE", "agentos-webui@0.3.2")

# Initialize Sentry (optional, disabled by default)
if SENTRY_AVAILABLE and SENTRY_ENABLED:
    if not SENTRY_DSN:
        logger.warning(
            "⚠️  SENTRY_ENABLED=true but SENTRY_DSN is not set. "
            "Error monitoring will NOT work. "
            "Set SENTRY_DSN environment variable or disable Sentry."
        )
    else:
        try:
            sentry_sdk.init(
                dsn=SENTRY_DSN,
                # Enable FastAPI and Starlette integrations
                integrations=[
                    FastApiIntegration(transaction_style="endpoint"),
                    StarletteIntegration(transaction_style="endpoint"),
                ],
                # Performance monitoring: 100% in dev, adjust in production
                traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
                # Profiling: 100% in dev, adjust in production
                profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
                # Include request data (headers, cookies, user IP, etc.)
                send_default_pii=True,
                # Environment (development, staging, production)
                environment=SENTRY_ENVIRONMENT,
                # Release version (used for Release Health tracking)
                release=SENTRY_RELEASE,
                # Breadcrumb settings
                max_breadcrumbs=50,
                # Additional options
                attach_stacktrace=True,

                # === Release Health: Auto Session Tracking ===
                # For server-mode applications (FastAPI), sessions are tracked per-request
                # Each HTTP request = 1 session for Release Health metrics
                # Sentry automatically detects the application type and uses request-mode
                auto_session_tracking=True,

                # Filter out healthcheck noise
                before_send=lambda event, hint: (
                    None if event.get("request", {}).get("url", "").endswith("/health") else event
                ),

                # Ignore health check transactions in performance monitoring
                traces_sampler=lambda sampling_context: (
                    0.0 if sampling_context.get("wsgi_environ", {}).get("PATH_INFO", "").endswith("/health")
                    else SENTRY_TRACES_SAMPLE_RATE
                ),
            )
            logger.info(f"✅ Sentry enabled: {SENTRY_RELEASE} (DSN: {SENTRY_DSN[:20]}...)")
        except Exception as e:
            logger.warning(f"⚠️  Failed to initialize Sentry: {e}")
else:
    # 明确记录 Sentry 状态
    if not SENTRY_AVAILABLE:
        logger.info("ℹ️  Sentry disabled: sentry-sdk not installed")
    elif not SENTRY_ENABLED:
        logger.info("ℹ️  Sentry disabled: SENTRY_ENABLED=false (default)")
    else:
        logger.info("ℹ️  Sentry disabled: SENTRY_DSN not configured")

# Get the webui directory path
WEBUI_DIR = Path(__file__).parent
STATIC_DIR = WEBUI_DIR / "static"
TEMPLATES_DIR = WEBUI_DIR / "templates"

# Create FastAPI app
app = FastAPI(
    title="AgentOS WebUI",
    description="Control Surface for AgentOS - Observability & Control",
    version="0.3.2",  # Updated for P1 Sprint
)

# Configure rate limiter with test bypass support (L-1)
# Uses custom key_func that returns unique keys for bypassed requests
limiter = Limiter(key_func=get_rate_limit_key)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# NOTE: Exception handlers have been moved to error_envelope.py (M-02)
# =====================================================================
# Global exception handling is now centralized in agentos/webui/api/error_envelope.py
# All errors use the unified ErrorEnvelope format:
#
# {
#   "ok": false,
#   "error_code": "ERROR_TYPE",        # Machine-readable error code
#   "message": "Human-readable message",
#   "details": {...},                  # Additional context
#   "timestamp": "2026-01-31T..."      # ISO 8601 UTC timestamp
# }
#
# The following handlers are registered via register_error_handlers(app):
# - HTTPException handler (404, 403, 401, etc.)
# - RequestValidationError handler (422)
# - Global Exception handler (500) with Sentry integration
#
# See register_error_handlers() call below (after middleware setup)
# =====================================================================

# Register Deprecation middleware first (Step 4: Legacy API deprecation)
@app.middleware("http")
async def legacy_api_deprecation(request: Request, call_next):
    """Add deprecation headers to legacy /api routes

    Step 4: Route Alias Implementation
    - /api/v0.31/* is the standard implementation
    - /api/* is a compatibility alias
    - Add deprecation headers to guide users to upgrade
    """
    response = await call_next(request)

    path = request.url.path

    # Only for /api but not /api/v0.31 (projects/tasks/repos routes)
    if path.startswith("/api/") and not path.startswith("/api/v0.31/"):
        if any(path.startswith(f"/api/{p}") for p in ["projects", "tasks", "repos"]):
            response.headers["Deprecation"] = "true"
            response.headers["Warning"] = '299 - "Deprecated: Use /api/v0.31/* instead"'
            # Suggest alternative URL
            alt_path = path.replace("/api/", "/api/v0.31/", 1)
            response.headers["Link"] = f'<{alt_path}>; rel="alternate"'

    return response

# Register JSON validation middleware first (M-1: Invalid JSON handling)
from agentos.webui.middleware.json_validation import add_json_validation_middleware
add_json_validation_middleware(app)

# Register Payload Size Limit middleware (L-3: Reject oversized payloads)
from agentos.webui.middleware.payload_size_limit import add_payload_size_limit_middleware
add_payload_size_limit_middleware(app)

# Register Request ID middleware (M-02: Request tracking)
from agentos.webui.middleware.request_id import add_request_id_middleware
add_request_id_middleware(app)

# Register Metrics tracking middleware (M-27-30: Observability)
from agentos.webui.middleware.metrics import add_metrics_middleware
add_metrics_middleware(app)

# Register audit middleware first (will execute last, closest to routes)
from agentos.webui.middleware.audit import add_audit_middleware
add_audit_middleware(app)

# Register security middleware (Task #34: XSS protection)
# Build CSP policy dynamically based on Sentry configuration
from agentos.webui.middleware.security import add_security_headers

# Base CSP policy (strict, local resources only)
csp_policy = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' ws: wss:"
)

# Add Sentry domain if enabled (production only)
if SENTRY_ENABLED:
    csp_policy += " https://*.ingest.us.sentry.io"

csp_policy += (
    "; "
    "media-src 'self'; "
    "object-src 'none'; "
    "frame-src 'self'; "
    "worker-src 'self' blob:; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "upgrade-insecure-requests;"
)

add_security_headers(app, csp_policy=csp_policy)

# Register CSRF protection middleware (Task #36: CSRF protection)
from agentos.webui.middleware.csrf import add_csrf_protection
add_csrf_protection(app)

# Register Confirm Intent middleware (Task #8: Extra protection for high-risk endpoints)
# This is Layer 3 of defense (after Origin check and CSRF token)
from agentos.webui.middleware.confirm_intent import add_confirm_intent_middleware
add_confirm_intent_middleware(app, enabled=True)

# Register session validation middleware (M-25: Session Security)
# Must be added BEFORE SessionMiddleware due to LIFO order
from agentos.webui.middleware.session_validation import add_session_validation
add_session_validation(app)

# Register session middleware last (will execute first in the middleware chain)
# IMPORTANT: SessionMiddleware must be added AFTER CSRF middleware due to LIFO order
# This ensures session is available when CSRF middleware executes

# Session Security: SESSION_SECRET_KEY 必须显式设置
# 不提供 fallback，任何环境都必须配置
session_secret = os.getenv("SESSION_SECRET_KEY")
if not session_secret:
    raise RuntimeError(
        "❌ SESSION_SECRET_KEY environment variable is required!\n"
        "\n"
        "Security: Session secret must be explicitly set, no fallback allowed.\n"
        "\n"
        "Generate a secure key:\n"
        "  python3 -c 'import secrets; print(secrets.token_urlsafe(32))'\n"
        "\n"
        "Set it:\n"
        "  export SESSION_SECRET_KEY='<your-generated-key>'\n"
        "\n"
        "Or add to .env file:\n"
        "  echo 'SESSION_SECRET_KEY=<your-generated-key>' >> .env\n"
        "\n"
        "For development, you can use a fixed key (DO NOT use in production):\n"
        "  export SESSION_SECRET_KEY='dev-only-insecure-key-do-not-use-in-prod'\n"
    )
SESSION_SECRET_KEY = session_secret

# M-25: Enhanced session configuration for production security
# Get configuration from environment
IS_PRODUCTION = os.getenv("AGENTOS_ENV", "development").lower() == "production"
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "86400"))  # 24 hours default
SESSION_SECURE_ONLY = os.getenv("SESSION_SECURE_ONLY", str(IS_PRODUCTION)).lower() == "true"

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="agentos_session",
    max_age=SESSION_MAX_AGE,  # 24 hours (configurable)
    same_site="strict",  # CSRF protection: strict prevents all cross-site usage
    https_only=SESSION_SECURE_ONLY,  # True in production, False in dev
)
logger.info(
    f"Session middleware enabled (max_age={SESSION_MAX_AGE}s, "
    f"secure={SESSION_SECURE_ONLY}, samesite=strict)"
)

# Register v0.31 error handlers
from agentos.webui.api.error_handlers_v31 import register_v31_error_handlers
register_v31_error_handlers(app)

# Register unified error handlers (M-02: API Contract Consistency)
from agentos.webui.api.error_envelope import register_error_handlers
register_error_handlers(app)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Register API routes
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(sessions_runtime.router, tags=["sessions"])

# CSRF Token API (provides tokens for frontend)
from agentos.webui.api import csrf_token
app.include_router(csrf_token.router, prefix="/api", tags=["csrf"])
# app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])  # LEGACY - Removed in v0.31 migration
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(secrets_api.router, tags=["secrets"])
app.include_router(providers.router, prefix="/api/providers", tags=["providers"])
app.include_router(providers_control.router, tags=["providers"])
app.include_router(providers_lifecycle.router, tags=["providers"])
app.include_router(providers_instances.router, tags=["providers"])
app.include_router(providers_models.router, prefix="/api/providers", tags=["providers"])
app.include_router(selfcheck.router, prefix="/api/selfcheck", tags=["selfcheck"])
app.include_router(context.router, prefix="/api/context", tags=["context"])
app.include_router(runtime.router, prefix="/api/runtime", tags=["runtime"])
app.include_router(support.router, prefix="/api/support", tags=["support"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(history.router, prefix="/api/history", tags=["history"])
app.include_router(share.router, prefix="/api", tags=["share"])
app.include_router(preview.router, prefix="/api", tags=["preview"])
app.include_router(snippets.router, prefix="/api/snippets", tags=["snippets"])
app.include_router(governance.router, tags=["governance"])
app.include_router(governance_dashboard.router, tags=["governance_dashboard"])
app.include_router(guardians.router, tags=["guardians"])
app.include_router(guardian.router, tags=["guardian"])
app.include_router(lead.router, tags=["lead"])
# app.include_router(projects.router, tags=["projects"])  # LEGACY - Removed in v0.31 migration
app.include_router(task_dependencies.router, tags=["tasks"])
app.include_router(task_templates.router, prefix="/api/task-templates", tags=["task-templates"])
app.include_router(task_events.router, prefix="/api", tags=["task-events"])
app.include_router(evidence.router, prefix="/api", tags=["evidence"])
app.include_router(content.router, tags=["content"])
app.include_router(execution.router, tags=["execution"])
app.include_router(dryrun.router, tags=["dryrun"])
app.include_router(intent.router, tags=["intent"])
app.include_router(answers.router, tags=["answers"])
app.include_router(auth.router, tags=["auth"])
app.include_router(auth_profiles.router, tags=["auth_profiles"])

# ============================================================================
# v0.31 API Routes (Standard Implementation)
# ============================================================================
# This is the canonical implementation with all Phase 3 fixes:
# - M-03: Idempotency support
# - M-24: Cascade delete policy
# - M-02: Unified ErrorEnvelope
# - C-1: Task FK fix (session_id in TaskResponse)
# ============================================================================

# Projects and Repos (standard CRUD)
app.include_router(projects_v31.router, prefix="/api/v0.31", tags=["projects_v31"])
app.include_router(repos_v31.router, prefix="/api/v0.31", tags=["repos_v31"])

# Tasks: Basic CRUD endpoints (GET/POST/DELETE /tasks)
app.include_router(tasks.router, prefix="/api/v0.31/tasks", tags=["tasks_v31_crud"])

# Tasks: v0.31 Extensions (spec freeze, binding, artifacts)
app.include_router(tasks_v31_extension.router, prefix="/api/v0.31", tags=["tasks_v31_ext"])

# ============================================================================
# Legacy Compatibility Routes (/api → v0.31)
# ============================================================================
# Compatibility aliases: reuse v0.31 implementation, zero code duplication
# Deprecation warnings added via middleware
# ============================================================================

# Projects and Repos compatibility
app.include_router(projects_v31.router, prefix="/api", tags=["projects_compat"])
app.include_router(repos_v31.router, prefix="/api", tags=["repos_compat"])

# Tasks: Basic CRUD compatibility
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks_compat_crud"])

# Tasks: v0.31 Extensions compatibility
app.include_router(tasks_v31_extension.router, prefix="/api", tags=["tasks_compat_ext"])

# Mode Monitoring API (Task #15: Phase 3.4)
app.include_router(mode_monitoring.router, prefix="/api/mode", tags=["mode"])

# Extensions Execution API (PR-E1: Runner Infrastructure)
# IMPORTANT: Register before extensions.router to avoid route conflicts
# /api/extensions/execute must be matched before /api/extensions/{extension_id}
app.include_router(extensions_execute.router, tags=["extensions_execute"])

# Extension Templates API (Task #13: Extension Template Wizard)
# IMPORTANT: Register before extensions.router to avoid route conflicts
# /api/extensions/templates/* must be matched before /api/extensions/{extension_id}
app.include_router(extension_templates.router, tags=["extension_templates"])

# Extensions Management API (PR-C: WebUI Extensions Management)
app.include_router(extensions.router, tags=["extensions"])

# Chat Commands API (Slash Command Discovery)
app.include_router(chat_commands.router, prefix="/api", tags=["chat_commands"])

# Models Management API (Model Download and Management)
app.include_router(models.router, tags=["models"])

# Budget Configuration API (Token Budget Configuration)
app.include_router(budget.router, prefix="/api/budget", tags=["budget"])

# Register BrainOS routes
app.include_router(brain.router, prefix="/api/brain", tags=["brain"])
app.include_router(brain_governance.router, tags=["brain-governance"])

# Communication API (CommunicationOS - External Communication Management)
app.include_router(communication.router, tags=["communication"])

# CommunicationOS Channels API (Task #5: WhatsApp Adapter)
app.include_router(channels.router, prefix="/api/channels", tags=["channels"])

# Channels Marketplace API (Task #7: Channels WebUI)
app.include_router(channels_marketplace.router, tags=["channels_marketplace"])

# MCP Management API (PR-4: MCP Observability and Control)
app.include_router(mcp.router, tags=["mcp"])

# MCP Marketplace API (PR-B: Marketplace APIs)
from agentos.webui.api import mcp_marketplace
app.include_router(mcp_marketplace.router, prefix="/api/mcp/marketplace", tags=["mcp-marketplace"])

# InfoNeed Metrics API (Task #21: Quality Monitoring Dashboard)
app.include_router(info_need_metrics.router, prefix="/api/info-need-metrics", tags=["info-need-metrics"])

# Decision Comparison API (Task #6: v3 Shadow Classifier Comparison)
app.include_router(decision_comparison.router, prefix="/api/v3/decision-comparison", tags=["decision-comparison"])

# Review Queue API (Task #9: Human review for BrainOS improvement proposals)
app.include_router(review_queue.router, prefix="/api/v3/review-queue", tags=["review-queue"])

# Capability Governance API (Task #29: v3 UI for Capability Governance)
app.include_router(capability.router, prefix="/api/capability", tags=["capability"])

# Voice API (VoiceOS - Voice conversation endpoints)
app.include_router(voice.router, tags=["voice"])
app.include_router(voice_twilio.router, tags=["voice", "twilio"])

# AppOS API (App management endpoints)
app.include_router(apps.router, prefix="/api", tags=["apps"])

# Register WebSocket routes
app.include_router(chat.router, prefix="/ws", tags=["websocket"])
app.include_router(ws_events.router, prefix="/ws", tags=["websocket"])

# L-21: Governance WebSocket for real-time quota updates
from agentos.webui.websocket import governance as ws_governance
app.include_router(ws_governance.router, prefix="/ws", tags=["websocket"])

# Register SSE routes
app.include_router(sse_task_events.router, tags=["sse"])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main control surface page"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "AgentOS Control Surface",
            "sentry_enabled": SENTRY_ENABLED,
            "sentry_dsn": SENTRY_DSN if SENTRY_ENABLED else "",
            "sentry_environment": SENTRY_ENVIRONMENT,
            "sentry_release": SENTRY_RELEASE,
        }
    )


@app.get("/health-check", response_class=HTMLResponse)
async def health_check_page(request: Request):
    """Health check page for debugging"""
    return templates.TemplateResponse(
        "health.html",
        {"request": request}
    )


@app.get("/share/{share_id}", response_class=HTMLResponse)
async def share_preview_page(request: Request, share_id: str):
    """Shared preview page"""
    return templates.TemplateResponse(
        "share.html",
        {
            "request": request,
            "share_id": share_id
        }
    )


@app.on_event("startup")
async def startup_event():
    """
    Application startup

    PR-2 Changes:
    - Removed SessionStore initialization (deprecated)
    - All session management now unified to ChatService
    - Sessions stored in chat_sessions table (not webui_sessions)
    """
    logger.info("AgentOS WebUI starting...")
    logger.info(f"Static files: {STATIC_DIR}")
    logger.info(f"Templates: {TEMPLATES_DIR}")

    # PR-2: SessionStore initialization removed
    # All session operations now use ChatService directly
    # Data stored in chat_sessions table for unified access
    logger.info("Sessions API unified to ChatService (PR-2)")

    # Note: Sessions are created on-demand with ULID generation
    # No default 'main' session is created

    # Initialize component databases (ensure migrations are applied)
    logger.info("Initializing component databases...")
    try:
        from agentos.core.storage.paths import ensure_db_exists, ALLOWED_COMPONENTS
        from agentos.store.migrator import auto_migrate

        # Initialize all component databases
        for component in ALLOWED_COMPONENTS:
            try:
                db_path = ensure_db_exists(component)
                applied = auto_migrate(db_path)
                if applied > 0:
                    logger.info(f"  ✓ {component}: applied {applied} migrations")
                else:
                    logger.debug(f"  ✓ {component}: up to date")
            except Exception as e:
                logger.warning(f"  ⚠ {component}: initialization failed - {e}")
                # Continue with other components even if one fails

        logger.info("Component databases initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize component databases: {e}", exc_info=True)
        logger.warning("Some databases may not be initialized (degraded mode)")

    # Cleanup stale KB index jobs on startup
    try:
        from agentos.webui.api.knowledge import cleanup_stale_jobs, CleanupJobsRequest
        result = await cleanup_stale_jobs(CleanupJobsRequest(older_than_hours=1))
        if result.cleaned_count > 0:
            logger.info(f"Cleaned {result.cleaned_count} stale KB index jobs on startup")
    except Exception as e:
        logger.warning(f"Failed to cleanup stale jobs on startup: {e}")

    # Retry failed KB index jobs on startup
    try:
        from agentos.webui.api.knowledge import retry_failed_jobs, RetryFailedJobsRequest
        result = await retry_failed_jobs(RetryFailedJobsRequest(max_retries=1, hours_lookback=24))
        if result.retried_count > 0:
            logger.info(f"Retrying {result.retried_count} failed KB index jobs on startup (skipped {result.skipped_count})")
        elif result.skipped_count > 0:
            logger.info(f"Found {result.skipped_count} failed jobs, but all were already retried or too old")
    except Exception as e:
        logger.warning(f"Failed to retry failed jobs on startup: {e}")

    # Initialize system logs capture
    try:
        from agentos.core.logging.store import LogStore
        from agentos.core.logging.handler import LogCaptureHandler
        from agentos.webui.api import logs as logs_api

        # Configuration from environment
        persist_logs = os.getenv("AGENTOS_LOGS_PERSIST", "false").lower() == "true"
        max_logs = int(os.getenv("AGENTOS_LOGS_MAX_SIZE", "5000"))
        log_level_str = os.getenv("AGENTOS_LOGS_LEVEL", "ERROR").upper()
        log_level = getattr(logging, log_level_str, logging.ERROR)

        # Get DB path (consistent with registry_db)
        # Use environment variable or unified storage API
        db_path = os.getenv("AGENTOS_DB_PATH") if persist_logs else None
        if persist_logs and not db_path:
            # Use unified storage API
            from agentos.core.storage.paths import component_db_path
            db_path = str(component_db_path("agentos"))

        # Create LogStore
        log_store = LogStore(max_size=max_logs, persist=persist_logs, db_path=db_path)

        # Inject store into Logs API
        logs_api.set_log_store(log_store)

        # Register Handler to root logger
        handler = LogCaptureHandler(log_store, level=log_level)
        logging.getLogger().addHandler(handler)

        logger.info(
            f"System logs capture initialized "
            f"(level={log_level_str}, max_size={max_logs}, persist={persist_logs})"
        )

        # Test log to verify capture is working
        test_logger = logging.getLogger("agentos.system_logs")
        test_logger.error("System logs capture is active and ready")

    except Exception as e:
        logger.error(f"Failed to initialize system logs: {e}", exc_info=True)
        logger.warning("System logs will not be captured (degraded mode)")

    # Initialize CommunicationOS (Task #5: WhatsApp Adapter)
    try:
        from agentos.webui.api.channels import initialize_communicationos
        initialize_communicationos()
        logger.info("CommunicationOS initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize CommunicationOS: {e}", exc_info=True)
        logger.warning("CommunicationOS will not be available (degraded mode)")

    # Initialize AppOS (Application Layer)
    try:
        from agentos.webui.api.apps import initialize_appos
        initialize_appos()
        logger.info("AppOS initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize AppOS: {e}", exc_info=True)
        logger.warning("AppOS will not be available (degraded mode)")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown"""
    logger.info("AgentOS WebUI shutting down...")
