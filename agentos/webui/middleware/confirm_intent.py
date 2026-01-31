"""Confirm Intent Middleware - 敏感操作二次确认

为极高风险端点添加 X-Confirm-Intent header 校验。

这是 CSRF 防护的第三道防线：
- Layer 1: Origin/Referer 同源检查
- Layer 2: CSRF Token 校验
- Layer 3: Confirm Intent 二次确认（本模块）

对于极高风险操作（如决策签字、通信模式切换、代码执行），即使通过了前两层保护，
仍需要前端显式发送 X-Confirm-Intent header 证明这是用户有意识的操作。

Security Issue: 极高风险端点额外保护 (Task #8)
"""

import logging
import re
from typing import Callable, Optional, Dict, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 需要确认 intent 的敏感端点
# 格式: 路径模式 -> 配置
PROTECTED_ENDPOINTS: Dict[str, Dict[str, Any]] = {
    "/api/brain/governance/decisions/*/signoff": {
        "method": "POST",
        "required_intent": "decision-signoff",
        "description": "决策治理签字"
    },
    "/api/communication/mode": {
        "method": "PUT",
        "required_intent": "mode-switch",
        "description": "通信模式切换"
    },
    "/api/snippets/*/materialize": {
        "method": "POST",
        "required_intent": "snippet-execute",
        "description": "代码片段执行"
    }
}


class ConfirmIntentMiddleware(BaseHTTPMiddleware):
    """验证敏感操作的二次确认 Intent"""

    def __init__(self, app, enabled: bool = True):
        """初始化 Confirm Intent 中间件

        Args:
            app: FastAPI 应用实例
            enabled: 是否启用（默认 True，可通过环境变量禁用）
        """
        super().__init__(app)
        self.enabled = enabled

    def _match_endpoint(self, path: str, method: str) -> Optional[Dict[str, Any]]:
        """检查路径是否匹配保护端点

        Args:
            path: 请求路径
            method: HTTP 方法

        Returns:
            匹配的端点配置，或 None
        """
        for pattern, config in PROTECTED_ENDPOINTS.items():
            # 将通配符转换为正则表达式
            # /api/snippets/*/materialize -> ^/api/snippets/[^/]+/materialize$
            regex_pattern = pattern.replace("*", "[^/]+")
            regex_pattern = f"^{regex_pattern}$"

            if re.match(regex_pattern, path) and method == config["method"]:
                return config

        return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求，检查是否需要 Confirm Intent

        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            响应对象（可能是拒绝响应或正常响应）
        """
        if not self.enabled:
            return await call_next(request)

        # 检查是否是保护端点
        endpoint_config = self._match_endpoint(request.url.path, request.method)

        if endpoint_config:
            # 检查 X-Confirm-Intent header
            intent_header = request.headers.get("x-confirm-intent")
            required_intent = endpoint_config["required_intent"]

            if intent_header != required_intent:
                logger.warning(
                    f"Confirm Intent check failed: "
                    f"path={request.url.path}, method={request.method}, "
                    f"required={required_intent}, got={intent_header or '(none)'}"
                )

                return JSONResponse(
                    status_code=403,
                    content={
                        "ok": False,
                        "error_code": "CONFIRM_INTENT_REQUIRED",
                        "message": f"Sensitive operation requires confirmation: {endpoint_config['description']}",
                        "details": {
                            "hint": f"Include X-Confirm-Intent: {required_intent} header",
                            "endpoint": request.url.path,
                            "method": request.method,
                            "operation": endpoint_config["description"]
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                )

            logger.info(
                f"Confirm Intent check passed: "
                f"path={request.url.path}, intent={intent_header}"
            )

        # 通过检查，继续处理
        return await call_next(request)


def add_confirm_intent_middleware(app, enabled: bool = True):
    """添加确认 Intent 中间件到应用

    Args:
        app: FastAPI 应用实例
        enabled: 是否启用（默认 True）
    """
    app.add_middleware(ConfirmIntentMiddleware, enabled=enabled)
    logger.info(f"Confirm Intent middleware {'enabled' if enabled else 'disabled'}")
