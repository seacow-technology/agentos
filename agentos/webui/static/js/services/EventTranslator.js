/**
 * EventTranslator - 将技术Event转换为User友好的叙事文本
 *
 * PR-V5: Timeline View - Narrative timeline
 *
 * Features:
 * - 将19种RunnerEventType翻译为人话
 * - Provide icons, text, and levels（info/warning/error/success）
 * - Support special cases and exception explanations
 *
 * Usage:
 * ```javascript
 * const friendlyEvent = EventTranslator.translate(rawEvent);
 * // { icon: 'rocket_launch', text: 'Start task executor', level: 'info', ... }
 * ```
 */

// phase图标映射
const PHASE_ICONS = {
    'planning': 'assignment',
    'executing': 'settings',
    'verifying': 'search',
    'done': 'check_circle',
    'failed': 'cancel',
    'blocked': 'construction'
};

// phase中文Name映射
const PHASE_NAMES = {
    'planning': 'Planning',
    'executing': 'Executing',
    'verifying': 'Verifying',
    'done': 'Complete',
    'failed': 'Failed',
    'blocked': 'Blocked'
};

// EventType模板映射（19种核心EventType）
const EVENT_TEMPLATES = {
    // ========== Runner Lifecycle ==========
    'runner_spawn': {
        icon: 'rocket_launch',
        text: (payload) => {
            const pid = payload?.runner_pid || 'unknown';
            const version = payload?.runner_version || 'v1';
            return `Start task executor（PID: ${pid}, Version: ${version}）`;
        },
        level: 'info'
    },

    'runner_exit': {
        icon: 'flag',
        text: (payload) => {
            const exitCode = payload?.exit_code ?? 0;
            const reason = payload?.reason || payload?.explanation || 'Normal exit';
            return exitCode === 0
                ? `执行器Normal exit（${reason}）`
                : `Executor exited abnormally（Exit code: ${exitCode}, ${reason}）`;
        },
        level: (payload) => (payload?.exit_code === 0 ? 'success' : 'error')
    },

    // ========== phase转换 ==========
    'phase_enter': {
        icon: (payload) => PHASE_ICONS[payload?.phase] || 'place',
        text: (payload) => {
            const phase = payload?.phase || 'unknown';
            const phaseName = PHASE_NAMES[phase] || phase;
            return `Enter ${phaseName} phase`;
        },
        level: 'info'
    },

    'phase_exit': {
        icon: (payload) => {
            const phase = payload?.phase;
            if (phase === 'done') return 'check_circle';
            if (phase === 'failed') return 'cancel';
            return 'arrow_forward';
        },
        text: (payload) => {
            const phase = payload?.phase || 'unknown';
            const phaseName = PHASE_NAMES[phase] || phase;
            return `Complete ${phaseName} phase`;
        },
        level: (payload) => {
            const phase = payload?.phase;
            if (phase === 'done') return 'success';
            if (phase === 'failed') return 'error';
            return 'info';
        }
    },

    // ========== Work Items（Subtask派发） ==========
    'WORK_ITEMS_EXTRACTED': {
        icon: 'inventory_2',
        text: (payload) => {
            const count = payload?.count || payload?.total_items || 0;
            return `Extracted ${count} subtasks pending`;
        },
        level: 'info'
    },

    'work_item_dispatched': {
        icon: 'outbox',
        text: (payload) => {
            const itemId = payload?.work_item_id || payload?.span_id || 'unknown';
            const workType = payload?.work_type || 'Subtask';
            return `Dispatch subtask #${itemId}（Type: ${workType}）`;
        },
        level: 'info'
    },

    'work_item_start': {
        icon: 'play_arrow',
        text: (payload) => {
            const itemId = payload?.work_item_id || 'unknown';
            const workType = payload?.work_type || 'Task';
            return `Start executing subtask #${itemId}（${workType}）`;
        },
        level: 'info'
    },

    'WORK_ITEM_STARTED': {
        icon: 'play_arrow',
        text: (payload) => {
            const itemId = payload?.work_item_id || payload?.span_id || 'unknown';
            return `Subtask #${itemId} started`;
        },
        level: 'info'
    },

    'work_item_done': {
        icon: 'check_circle',
        text: (payload) => {
            const itemId = payload?.work_item_id || 'unknown';
            const workType = payload?.work_type || 'Task';
            return `Subtask #${itemId} Complete（${workType}）`;
        },
        level: 'success'
    },

    'work_item_complete': {
        icon: 'check_circle',
        text: (payload) => {
            const itemId = payload?.work_item_id || 'unknown';
            return `Subtask #${itemId} executed successfully`;
        },
        level: 'success'
    },

    'WORK_ITEM_COMPLETED': {
        icon: 'check_circle',
        text: (payload) => {
            const itemId = payload?.work_item_id || payload?.span_id || 'unknown';
            return `Subtask #${itemId} Completed`;
        },
        level: 'success'
    },

    'work_item_failed': {
        icon: 'cancel',
        text: (payload) => {
            const itemId = payload?.work_item_id || 'unknown';
            const reason = payload?.reason || payload?.error || 'Execution failed';
            return `Subtask #${itemId} Failed（${reason}）`;
        },
        level: 'error'
    },

    'WORK_ITEM_FAILED': {
        icon: 'cancel',
        text: (payload) => {
            const itemId = payload?.work_item_id || payload?.span_id || 'unknown';
            const error = payload?.error || 'Unknown error';
            return `Subtask #${itemId} Execution failed（${error}）`;
        },
        level: 'error'
    },

    // ========== Checkpoints（Checkpoints） ==========
    'checkpoint_begin': {
        icon: 'save',
        text: (payload) => {
            const checkpointType = payload?.checkpoint_type || 'checkpoint';
            return `Start creating checkpoint（${checkpointType}）`;
        },
        level: 'info'
    },

    'checkpoint_commit': {
        icon: 'save',
        text: (payload) => {
            const checkpointId = payload?.checkpoint_id || 'unknown';
            const evidenceCount = payload?.evidence_refs
                ? Object.keys(payload.evidence_refs).length
                : 0;
            return evidenceCount > 0
                ? `Save checkpoint ${checkpointId}（verified ${evidenceCount} evidence items）`
                : `Save checkpoint ${checkpointId}`;
        },
        level: 'success'
    },

    'checkpoint_verified': {
        icon: 'check_circle',
        text: (payload) => {
            const checkpointId = payload?.checkpoint_id || 'unknown';
            return `Checkpoints ${checkpointId} verification passed`;
        },
        level: 'success'
    },

    'checkpoint_invalid': {
        icon: 'warning',
        text: (payload) => {
            const checkpointId = payload?.checkpoint_id || 'unknown';
            const reason = payload?.reason || 'Data inconsistency';
            return `Checkpoints ${checkpointId} verification failed（${reason}）`;
        },
        level: 'warning'
    },

    // ========== Evidence（Evidence collection） ==========
    'evidence_collected': {
        icon: 'attach_file',
        text: (payload) => {
            const evidenceType = payload?.evidence_type || 'evidence';
            const evidenceId = payload?.evidence_id || 'unknown';
            return `Collect evidence：${evidenceType} (ID: ${evidenceId})`;
        },
        level: 'info'
    },

    // ========== Gates（Gates） ==========
    'gate_start': {
        icon: 'traffic',
        text: (payload) => {
            const gateType = payload?.gate_type || 'gate';
            return `Start running gate：${gateType}`;
        },
        level: 'info'
    },

    'gate_result': {
        icon: (payload) => payload?.passed ? 'check_circle' : 'cancel',
        text: (payload) => {
            const gateType = payload?.gate_type || 'gate';
            const passed = payload?.passed;

            if (passed) {
                return `Gate passed：${gateType}`;
            } else {
                const reasonCode = payload?.reason_code || 'Unknown reason';
                const hint = payload?.hint || '';
                return hint
                    ? `Gate failed：${gateType}（${reasonCode} - ${hint}）`
                    : `Gate failed：${gateType}（${reasonCode}）`;
            }
        },
        level: (payload) => payload?.passed ? 'success' : 'error'
    },

    'GATE_VERIFICATION_RESULT': {
        icon: (payload) => payload?.passed || payload?.success ? 'check_circle' : 'cancel',
        text: (payload) => {
            const gateType = payload?.gate_type || payload?.type || 'gate';
            const passed = payload?.passed || payload?.success;

            if (passed) {
                return `Gatesverification passed：${gateType}`;
            } else {
                const reason = payload?.reason || payload?.error || 'verification failed';
                return `Gatesverification failed：${gateType}（${reason}）`;
            }
        },
        level: (payload) => (payload?.passed || payload?.success) ? 'success' : 'error'
    },

    // ========== Recovery（Recovery） ==========
    'recovery_detected': {
        icon: 'refresh',
        text: (payload) => {
            const taskId = payload?.task_id || 'unknown';
            const reason = payload?.reason || 'Interruption detected';
            return `检测到Task中断（${reason}）`;
        },
        level: 'warning'
    },

    'recovery_resumed_from_checkpoint': {
        icon: 'refresh',
        text: (payload) => {
            const checkpointId = payload?.checkpoint_id || 'unknown';
            const phase = payload?.phase || 'unknown';
            return `从Checkpoints ${checkpointId} resumed（phase: ${PHASE_NAMES[phase] || phase}）`;
        },
        level: 'info'
    },

    'recovery_requeued': {
        icon: 'refresh',
        text: (payload) => {
            const taskId = payload?.task_id || 'unknown';
            return `Task ${taskId} requeued`;
        },
        level: 'info'
    }
};

export class EventTranslator {
    /**
     * 将原始Event转换为User友好的叙事Event
     *
     * @param {Object} event - 原始Event对象
     * @param {string} event.event_type - EventType
     * @param {Object} event.payload - Event载荷
     * @param {string} event.created_at - Created at
     * @param {number} event.seq - Event序列号
     * @returns {Object} 友好Event对象
     */
    static translate(event) {
        const template = EVENT_TEMPLATES[event.event_type];

        if (!template) {
            // 未知EventType，返回默认格式
            return {
                icon: 'assignment',
                text: `Event: ${event.event_type}`,
                level: 'info',
                timestamp: event.created_at,
                seq: event.seq,
                rawEvent: event,
                explanation: event.payload?.explanation || event.payload?.hint || null
            };
        }

        // Parse icon (may be function)
        const icon = typeof template.icon === 'function'
            ? template.icon(event.payload)
            : template.icon;

        // Parse text (must be function)
        const text = template.text(event.payload);

        // Parse level (may be function)
        const level = typeof template.level === 'function'
            ? template.level(event.payload)
            : template.level;

        // Extract explanation/Tip
        const explanation = event.payload?.explanation
            || event.payload?.hint
            || event.payload?.reason
            || null;

        return {
            icon,
            text,
            level,
            timestamp: event.created_at,
            seq: event.seq,
            span_id: event.span_id,
            phase: event.phase,
            rawEvent: event,
            explanation
        };
    }

    /**
     * 批量翻译Event
     *
     * @param {Array} events - Event数组
     * @returns {Array} 友好Event数组
     */
    static translateBatch(events) {
        return events.map(event => this.translate(event));
    }

    /**
     * 检查EventShould throttle（用于聚合）
     *
     * @param {string} eventType - EventType
     * @returns {boolean} Should throttle
     */
    static shouldThrottle(eventType) {
        // Progress 类Event需要节流
        const throttlePatterns = [
            /progress$/i,
            /heartbeat$/i,
            /lease_renewed$/i
        ];

        return throttlePatterns.some(pattern => pattern.test(eventType));
    }

    /**
     * 获取Event的Show优先级（用于Sort）
     *
     * @param {Object} event - 友好Event对象
     * @returns {number} Priority (higher number = higher priority)
     */
    static getPriority(event) {
        const priorityMap = {
            'error': 100,
            'warning': 80,
            'success': 60,
            'info': 40
        };

        return priorityMap[event.level] || 0;
    }

    /**
     * 判断是否为关键Event（不应被过滤）
     *
     * @param {Object} event - 友好Event对象
     * @returns {boolean} 是否为关键Event
     */
    static isCritical(event) {
        const criticalLevels = ['error', 'warning'];
        return criticalLevels.includes(event.level);
    }
}

// Export constants for external use
export { PHASE_ICONS, PHASE_NAMES, EVENT_TEMPLATES };

// Default export
export default EventTranslator;
