#!/usr/bin/env python3
"""
Agent2 - WebUI Health Monitor and Auto-Recovery
持续监控 AgentOS WebUI 健康状态并自动修复问题
"""

import atexit
import json
import logging
import os
import platform
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import requests
import psutil

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - Agent2 - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / '.agentos' / 'multi_agent' / 'agent2.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WebUIMonitor:
    """WebUI 健康监控器"""

    def __init__(self):
        self.base_dir = Path.home() / '.agentos'
        self.multi_agent_dir = self.base_dir / 'multi_agent'
        self.status_file = self.multi_agent_dir / 'agent2_status.json'
        self.restart_signal = self.multi_agent_dir / 'restart_signal'
        self.pid_file = self.base_dir / 'webui.pid'

        # WebUI 配置
        self.webui_url = "http://127.0.0.1:8080"
        self.health_endpoint = f"{self.webui_url}/api/health"
        self.check_interval = 5  # 秒
        self.max_retry = 3
        self.timeout = 5  # 请求超时时间

        # 初始化状态
        self.status = {
            "status": "initializing",
            "last_check": None,
            "health_status": "unknown",
            "fixes": [],
            "consecutive_failures": 0
        }

        # 确保目录存在
        self.multi_agent_dir.mkdir(parents=True, exist_ok=True)

        # 设置信号处理 (跨平台兼容)
        # SIGINT 在所有平台上都支持 (Ctrl+C)
        signal.signal(signal.SIGINT, self._signal_handler)

        # SIGTERM 在 Windows 上不完全支持, 仅在 Unix 系统上注册
        if platform.system() != "Windows":
            signal.signal(signal.SIGTERM, self._signal_handler)
        else:
            # Windows: 使用 atexit 作为备用的清理机制
            atexit.register(self._cleanup)

        self.running = True

    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info(f"收到信号 {signum}，准备退出...")
        self.running = False
        self._cleanup()
        sys.exit(0)

    def _cleanup(self):
        """清理资源和更新状态（跨平台兼容的退出处理）"""
        if hasattr(self, 'status'):
            logger.info("正在清理并更新状态...")
            self._update_status("stopped", "unknown")

    def _update_status(self, status: str, health_status: str,
                      fix_record: Optional[Dict[str, Any]] = None):
        """更新状态文件"""
        self.status["status"] = status
        self.status["last_check"] = datetime.now(timezone.utc).isoformat()
        self.status["health_status"] = health_status

        if fix_record:
            self.status["fixes"].append(fix_record)
            # 只保留最近 50 条修复记录
            if len(self.status["fixes"]) > 50:
                self.status["fixes"] = self.status["fixes"][-50:]

        try:
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump(self.status, f, indent=2)
        except Exception as e:
            logger.error(f"更新状态文件失败: {e}")

    def _check_process_alive(self) -> bool:
        """检查进程是否存活"""
        if not self.pid_file.exists():
            logger.warning("PID 文件不存在")
            return False

        try:
            with open(self.pid_file, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())

            # 检查进程是否存在
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                # 检查进程名称是否包含 python/uvicorn
                if 'python' in process.name().lower():
                    return True

            logger.warning(f"进程 {pid} 不存在或不是 Python 进程")
            return False

        except Exception as e:
            logger.error(f"检查进程失败: {e}")
            return False

    def _check_port_listening(self) -> bool:
        """检查端口是否监听"""
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == 'LISTEN' and conn.laddr.port == 8080:
                    return True
            logger.warning("端口 8080 未监听")
            return False
        except Exception as e:
            logger.error(f"检查端口失败: {e}")
            return False

    def _check_health_api(self) -> tuple[bool, Optional[Dict[str, Any]], Optional[float]]:
        """
        检查健康检查 API

        Returns:
            (success, response_data, response_time)
        """
        try:
            start_time = time.time()
            response = requests.get(
                self.health_endpoint,
                timeout=self.timeout
            )
            response_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                status = data.get('status', 'unknown')

                if status == 'ok':
                    return True, data, response_time
                else:
                    logger.warning(f"健康检查返回非 OK 状态: {status}")
                    return False, data, response_time
            else:
                logger.warning(f"健康检查返回状态码: {response.status_code}")
                return False, None, response_time

        except requests.exceptions.Timeout:
            logger.error("健康检查超时")
            return False, None, None
        except requests.exceptions.ConnectionError:
            logger.error("无法连接到 WebUI")
            return False, None, None
        except Exception as e:
            logger.error(f"健康检查异常: {e}")
            return False, None, None

    def _diagnose(self) -> Dict[str, Any]:
        """诊断 WebUI 状态"""
        diagnosis = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "process_alive": self._check_process_alive(),
            "port_listening": self._check_port_listening(),
            "health_api_ok": False,
            "response_time": None,
            "health_data": None
        }

        health_ok, health_data, response_time = self._check_health_api()
        diagnosis["health_api_ok"] = health_ok
        diagnosis["health_data"] = health_data
        diagnosis["response_time"] = response_time

        return diagnosis

    def _create_restart_signal(self, reason: str):
        """创建重启信号文件"""
        signal_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "requested_by": "agent2"
        }

        try:
            with open(self.restart_signal, "w", encoding="utf-8") as f:
                json.dump(signal_data, f, indent=2)
            logger.info(f"已创建重启信号: {reason}")
        except Exception as e:
            logger.error(f"创建重启信号失败: {e}")

    def _fix_issue(self, diagnosis: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据诊断结果尝试修复问题

        Returns:
            修复记录
        """
        fix_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "issue": "",
            "action": "",
            "result": "failed"
        }

        # 场景 1: 进程不存在
        if not diagnosis["process_alive"]:
            fix_record["issue"] = "WebUI 进程不存在"
            fix_record["action"] = "创建重启信号"
            self._create_restart_signal("process_not_alive")
            fix_record["result"] = "signal_created"
            return fix_record

        # 场景 2: 端口未监听
        if not diagnosis["port_listening"]:
            fix_record["issue"] = "端口 8080 未监听"
            fix_record["action"] = "创建重启信号"
            self._create_restart_signal("port_not_listening")
            fix_record["result"] = "signal_created"
            return fix_record

        # 场景 3: 健康检查失败
        if not diagnosis["health_api_ok"]:
            fix_record["issue"] = "健康检查 API 失败"
            fix_record["action"] = "创建重启信号"
            self._create_restart_signal("health_check_failed")
            fix_record["result"] = "signal_created"
            return fix_record

        # 场景 4: 响应时间过长
        if diagnosis["response_time"] and diagnosis["response_time"] > 3.0:
            fix_record["issue"] = f"响应时间过长: {diagnosis['response_time']:.2f}s"
            fix_record["action"] = "记录警告"
            fix_record["result"] = "warning_logged"
            logger.warning(f"WebUI 响应时间异常: {diagnosis['response_time']:.2f}s")
            return fix_record

        return fix_record

    def _run_monitoring_cycle(self):
        """执行一次监控循环"""
        logger.info("开始健康检查...")

        # 诊断
        diagnosis = self._diagnose()

        # 判断健康状态
        if diagnosis["health_api_ok"] and diagnosis["process_alive"] and diagnosis["port_listening"]:
            health_status = "ok"
            self.status["consecutive_failures"] = 0

            response_time = diagnosis.get("response_time", 0)
            if response_time:
                logger.info(f"健康检查通过 (响应时间: {response_time:.2f}s)")
            else:
                logger.info("健康检查通过")

            self._update_status("monitoring", health_status)

        else:
            # 有问题，尝试修复
            self.status["consecutive_failures"] += 1
            health_status = "down"

            logger.warning(f"检测到异常 (连续失败: {self.status['consecutive_failures']})")
            logger.warning(f"诊断结果: {json.dumps(diagnosis, indent=2)}")

            # 如果连续失败次数超过阈值，尝试修复
            if self.status["consecutive_failures"] >= 2:
                logger.error("开始尝试修复...")
                self._update_status("fixing", health_status)

                fix_record = self._fix_issue(diagnosis)
                logger.info(f"修复操作: {fix_record['action']}, 结果: {fix_record['result']}")

                self._update_status("monitoring", health_status, fix_record)

                # 等待 Agent1 处理重启信号
                if fix_record["result"] == "signal_created":
                    logger.info("等待 Agent1 处理重启信号...")
                    time.sleep(10)  # 给 Agent1 一些时间处理
                    # 重置失败计数
                    self.status["consecutive_failures"] = 0
            else:
                self._update_status("monitoring", "warn")

    def run(self):
        """主监控循环"""
        logger.info("Agent2 监控器启动")
        logger.info(f"监控目标: {self.webui_url}")
        logger.info(f"检查间隔: {self.check_interval}秒")
        logger.info(f"状态文件: {self.status_file}")

        self._update_status("monitoring", "unknown")

        while self.running:
            try:
                self._run_monitoring_cycle()

                # 等待下一次检查
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"监控循环异常: {e}", exc_info=True)
                self._update_status("error", "unknown")
                time.sleep(self.check_interval)


def main():
    """主函数"""
    try:
        monitor = WebUIMonitor()
        monitor.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号，退出")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Agent2 运行异常: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
