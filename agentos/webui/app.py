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

# Import API routers
from agentos.webui.api import health, sessions, tasks, events, skills, memory, config, logs, providers, selfcheck, context, runtime, providers_control, support, secrets, sessions_runtime, providers_lifecycle, providers_instances, providers_models, knowledge, history, share, preview, snippets, governance, guardians, lead, projects, task_dependencies, governance_dashboard, guardian, content, answers, auth, execution, dryrun, intent, auth_profiles, task_templates, task_events, evidence, mode_monitoring, extensions, extensions_execute, extension_templates, models, budget, brain
# v0.31 API routers
from agentos.webui.api import projects_v31, repos_v31, tasks_v31_extension
# WebSocket and SSE routers
from agentos.webui.websocket import chat, events as ws_events
from agentos.webui.sse import task_events as sse_task_events

# Import SessionStore
from agentos.webui.store import SQLiteSessionStore, MemorySessionStore

logger = logging.getLogger(__name__)

# Initialize Sentry for error tracking, performance monitoring, and release health
# Can be disabled by setting SENTRY_ENABLED=false
SENTRY_ENABLED = os.getenv("SENTRY_ENABLED", "true").lower() == "true"
SENTRY_DSN = os.getenv("SENTRY_DSN", "https://0f4d8d4b457861cad05ed94aa1b53c40@o4510344567586816.ingest.us.sentry.io/4510783131942912")
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "development")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0"))
SENTRY_PROFILES_SAMPLE_RATE = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "1.0"))
SENTRY_RELEASE = os.getenv("SENTRY_RELEASE", "agentos-webui@0.3.2")

# Initialize Sentry with proper error handling
if SENTRY_AVAILABLE and SENTRY_ENABLED and SENTRY_DSN:
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
        logger.info(
            f"check Sentry monitoring enabled: {SENTRY_RELEASE} "
            f"(env: {SENTRY_ENVIRONMENT}, traces: {SENTRY_TRACES_SAMPLE_RATE*100}%, "
            f"profiles: {SENTRY_PROFILES_SAMPLE_RATE*100}%, sessions: enabled)"
        )
    except Exception as e:
        logger.warning(f"warning Failed to initialize Sentry: {e} – running in local dev mode")
        SENTRY_AVAILABLE = False
elif not SENTRY_AVAILABLE:
    logger.warning(
        "warning Sentry disabled (dependency missing: sentry-sdk) – running in local dev mode\n"
        "  Install with: pip install sentry-sdk"
    )
else:
    logger.info("warning Sentry monitoring disabled (SENTRY_ENABLED=false or DSN not configured)")

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

# Configure rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Custom exception handler for HTTPException with our API contract format
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException and format according to our API contract

    If the exception detail is a dict with our standard format (ok, error, etc.),
    return it directly. Otherwise, wrap the detail in our format.
    """
    detail = exc.detail

    # If detail is already in our format, return it
    if isinstance(detail, dict) and "ok" in detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=detail
        )

    # Otherwise, wrap it in our format
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "data": None,
            "error": str(detail) if detail else "An error occurred",
            "hint": None,
            "reason_code": "INTERNAL_ERROR"
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler for unhandled exceptions.

    Logs the exception with full context and returns a standardized
    error response. Also reports to Sentry if enabled.
    """
    logger.error(
        f"Unhandled exception in {request.method} {request.url.path}",
        exc_info=exc
    )

    # Report to Sentry if available and enabled
    if SENTRY_AVAILABLE and SENTRY_ENABLED:
        try:
            sentry_sdk.capture_exception(exc)
        except Exception as e:
            logger.warning(f"Failed to report exception to Sentry: {e}")

    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "data": None,
            "error": "Internal server error",
            "hint": "An unexpected error occurred. Please check the logs.",
            "reason_code": "INTERNAL_ERROR"
        }
    )


# Register audit middleware (must be before route registration)
from agentos.webui.middleware.audit import add_audit_middleware
add_audit_middleware(app)

# Register v0.31 error handlers
from agentos.webui.api.error_handlers_v31 import register_v31_error_handlers
register_v31_error_handlers(app)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Register API routes
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(sessions_runtime.router, tags=["sessions"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(skills.router, prefix="/api/skills", tags=["skills"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(secrets.router, tags=["secrets"])
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
app.include_router(projects.router, tags=["projects"])
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

# Register v0.31 API routes (Project-Aware Task OS)
app.include_router(projects_v31.router, tags=["projects_v31"])
app.include_router(repos_v31.router, tags=["repos_v31"])
app.include_router(tasks_v31_extension.router, tags=["tasks_v31"])

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

# Models Management API (Model Download and Management)
app.include_router(models.router, tags=["models"])

# Budget Configuration API (Token Budget Configuration)
app.include_router(budget.router, prefix="/api/budget", tags=["budget"])

# Register BrainOS routes
app.include_router(brain.router, prefix="/api/brain", tags=["brain"])

# Register WebSocket routes
app.include_router(chat.router, prefix="/ws", tags=["websocket"])
app.include_router(ws_events.router, prefix="/ws", tags=["websocket"])

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
            "sentry_environment": SENTRY_ENVIRONMENT,
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

    Initializes SessionStore:
    - Tries SQLiteSessionStore (persistent)
    - Falls back to MemorySessionStore on error (degraded mode)
    - Configurable via AGENTOS_WEBUI_USE_MEMORY_STORE env var
    """
    logger.info("AgentOS WebUI starting...")
    logger.info(f"Static files: {STATIC_DIR}")
    logger.info(f"Templates: {TEMPLATES_DIR}")

    # Initialize SessionStore
    use_memory = os.getenv("AGENTOS_WEBUI_USE_MEMORY_STORE", "false").lower() == "true"

    if use_memory:
        logger.warning("Using MemorySessionStore (data will not persist)")
        store = MemorySessionStore()
    else:
        try:
            # Get DB path from environment or use default
            db_path = os.getenv("AGENTOS_DB_PATH", "store/registry.sqlite")

            # Ensure parent directory exists
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Initializing SQLiteSessionStore: {db_path}")
            store = SQLiteSessionStore(db_path)
            logger.info("SQLiteSessionStore initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SQLiteSessionStore: {e}")
            logger.warning("Falling back to MemorySessionStore (degraded mode)")
            store = MemorySessionStore()

    # Inject store into sessions API
    sessions.set_session_store(store)
    logger.info(f"SessionStore injected: {type(store).__name__}")

    # Ensure "main" session exists for backward compatibility
    try:
        if store.get_session("main") is None:
            logger.info("Creating default 'main' session")
            main_session = store.create_session(
                session_id="main",
                user_id="default",
                metadata={"title": "Main Session", "tags": ["default"]}
            )
            logger.info(f"Created main session: {main_session.session_id}")
    except Exception as e:
        logger.warning(f"Failed to create main session: {e}")

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

        # Get DB path (same as SessionStore)
        db_path = os.getenv("AGENTOS_DB_PATH", "store/registry.sqlite") if persist_logs else None

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


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown"""
    logger.info("AgentOS WebUI shutting down...")
