/**
 * DecisionReviewView - P4-C2 Decision Review UI
 *
 * 功能:
 * - Show决策Time线（按Time倒序）
 * - 左右对比面板（Cognition at Time vs Current Cognition）
 * - 完整性验证结果Show
 * - 签字功能（对 REQUIRE_SIGNOFF 决策）
 * - 过滤器（按Type、Status）
 *
 * P4 治理系统最后 5% - 决策审查界面
 */

class DecisionReviewView {
    constructor() {
        this.decisions = [];
        this.selectedDecision = null;
        this.filters = {
            type: null,
            status: null
        };
        this.container = null;
    }

    /**
     * 渲染视图
     * @param {HTMLElement} container - 容器元素
     */
    async render(container) {
        this.container = container;

        container.innerHTML = `
            <div class="decision-review-view">
                <!-- 头部 -->
                <div class="view-header">
                    <div>
                        <h1>🏛️ Decision Review</h1>
                        <p class="text-sm text-gray-600 mt-1">Governance decision review and sign-off</p>
                    </div>
                    <div class="header-actions">
                        <button id="refresh-btn" class="btn-refresh" title="Refresh">
                            <span class="material-icons md-18">refresh</span> Refresh
                        </button>
                    </div>
                </div>

                <!-- 过滤器 -->
                <div class="filter-section">
                    <div class="filter-bar">
                        <div class="filter-item">
                            <label class="filter-label">Type</label>
                            <select id="type-filter" class="filter-select">
                                <option value="">All Types</option>
                                <option value="NAVIGATION">NAVIGATION</option>
                                <option value="COMPARE">COMPARE</option>
                                <option value="HEALTH">HEALTH</option>
                            </select>
                        </div>
                        <div class="filter-item">
                            <label class="filter-label">Status</label>
                            <select id="status-filter" class="filter-select">
                                <option value="">All Statuses</option>
                                <option value="PENDING">PENDING</option>
                                <option value="APPROVED">APPROVED</option>
                                <option value="BLOCKED">BLOCKED</option>
                                <option value="SIGNED">SIGNED</option>
                                <option value="FAILED">FAILED</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- 主内容区 -->
                <div class="content-area">
                    <!-- 左侧：Time线列表 -->
                    <div class="timeline-panel">
                        <div class="panel-header">
                            <h3>决策Time线</h3>
                            <span id="decision-count" class="count-badge">0</span>
                        </div>
                        <div id="timeline-list" class="timeline-list">
                            <div class="loading">Loading decision records...</div>
                        </div>
                    </div>

                    <!-- 右侧：Details面板 -->
                    <div class="detail-panel">
                        <div id="detail-content" class="detail-content">
                            <div class="empty-state">
                                <span class="material-icons md-48">gavel</span>
                                <p>Select a decision record to view details</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.attachEventListeners();
        await this.loadDecisions();
    }

    /**
     * 附加事件监听器
     */
    attachEventListeners() {
        // Refresh按钮
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadDecisions();
            });
        }

        // Type过滤器
        const typeFilter = document.getElementById('type-filter');
        if (typeFilter) {
            typeFilter.addEventListener('change', (e) => {
                this.filters.type = e.target.value || null;
                this.applyFilters();
            });
        }

        // Status过滤器
        const statusFilter = document.getElementById('status-filter');
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => {
                this.filters.status = e.target.value || null;
                this.applyFilters();
            });
        }
    }

    /**
     * 加载决策记录
     */
    async loadDecisions() {
        const listElement = document.getElementById('timeline-list');
        if (!listElement) return;

        try {
            listElement.innerHTML = '<div class="loading">Loading decision records...</div>';

            const response = await fetch('/api/brain/governance/decisions?limit=100');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const result = await response.json();

            if (!result.ok || !result.data) {
                throw new Error(result.error || 'Load failed');
            }

            this.decisions = result.data;
            this.renderTimeline();
            this.updateDecisionCount();
        } catch (error) {
            console.error('Failed to load decisions:', error);
            this.renderError(listElement, error);
        }
    }

    /**
     * 渲染Time线列表
     */
    renderTimeline() {
        const listElement = document.getElementById('timeline-list');
        if (!listElement) return;

        const filteredDecisions = this.getFilteredDecisions();

        if (filteredDecisions.length === 0) {
            listElement.innerHTML = `
                <div class="empty-state">
                    <span class="material-icons md-48">inbox</span>
                    <p>No decision records found</p>
                </div>
            `;
            return;
        }

        const itemsHtml = filteredDecisions.map(decision => this.renderTimelineItem(decision)).join('');
        listElement.innerHTML = itemsHtml;

        // 附加点击事件
        filteredDecisions.forEach(decision => {
            const item = document.getElementById(`decision-${decision.decision_id}`);
            if (item) {
                item.addEventListener('click', () => {
                    this.selectDecision(decision);
                });
            }
        });
    }

    /**
     * 渲染Time线项
     */
    renderTimelineItem(decision) {
        const statusClass = this.getStatusClass(decision.status);
        const verdictClass = this.getVerdictClass(decision.final_verdict);
        const isSelected = this.selectedDecision && this.selectedDecision.decision_id === decision.decision_id;

        return `
            <div id="decision-${decision.decision_id}" class="timeline-item ${isSelected ? 'selected' : ''}" data-decision-id="${decision.decision_id}">
                <div class="item-header">
                    <span class="decision-type">${this.escapeHtml(decision.decision_type)}</span>
                    <span class="decision-time">${this.formatTimestamp(decision.timestamp)}</span>
                </div>
                <div class="item-body">
                    <div class="seed-text">${this.escapeHtml(decision.seed)}</div>
                </div>
                <div class="item-footer">
                    <span class="status-badge status-${statusClass}">${this.escapeHtml(decision.status)}</span>
                    <span class="verdict-badge verdict-${verdictClass}">${this.escapeHtml(decision.final_verdict)}</span>
                    ${decision.confidence_score !== null && decision.confidence_score !== undefined ?
                        `<span class="confidence-score">${(decision.confidence_score * 100).toFixed(0)}%</span>` : ''}
                </div>
            </div>
        `;
    }

    /**
     * 选择决策
     */
    async selectDecision(decision) {
        this.selectedDecision = decision;

        // 更新Time线项的选中Status
        const allItems = document.querySelectorAll('.timeline-item');
        allItems.forEach(item => {
            item.classList.remove('selected');
        });

        const selectedItem = document.getElementById(`decision-${decision.decision_id}`);
        if (selectedItem) {
            selectedItem.classList.add('selected');
        }

        // 加载Details
        await this.loadDecisionDetail(decision.decision_id);
    }

    /**
     * 加载决策Details
     */
    async loadDecisionDetail(decisionId) {
        const detailContent = document.getElementById('detail-content');
        if (!detailContent) return;

        try {
            detailContent.innerHTML = '<div class="loading">Loading details...</div>';

            // 并行请求Details和重放数据
            const [detailResponse, replayResponse] = await Promise.all([
                fetch(`/api/brain/governance/decisions/${decisionId}`),
                fetch(`/api/brain/governance/decisions/${decisionId}/replay`)
            ]);

            if (!detailResponse.ok) {
                throw new Error(`HTTP ${detailResponse.status}: ${detailResponse.statusText}`);
            }

            const detailResult = await detailResponse.json();
            if (!detailResult.ok || !detailResult.data) {
                throw new Error(detailResult.error || 'Failed to load details');
            }

            let replayData = null;
            if (replayResponse.ok) {
                const replayResult = await replayResponse.json();
                if (replayResult.ok) {
                    replayData = replayResult.data;
                }
            }

            this.renderDetail(detailResult.data, replayData);
        } catch (error) {
            console.error('Failed to load decision detail:', error);
            this.renderDetailError(detailContent, error);
        }
    }

    /**
     * 渲染Details面板
     */
    renderDetail(detail, replay) {
        const detailContent = document.getElementById('detail-content');
        if (!detailContent) return;

        const statusClass = this.getStatusClass(detail.status);
        const verdictClass = this.getVerdictClass(detail.final_verdict);

        // 完整性检查
        const integrityPassed = detail.integrity_check && detail.integrity_check.passed;
        const integrityHtml = detail.integrity_check ? `
            <div class="integrity-check ${integrityPassed ? 'passed' : 'failed'}">
                ${integrityPassed ?
                    '<span class="material-icons md-18">check_circle</span> <span>✅ Verified</span>' :
                    '<span class="material-icons md-18">error</span> <span>❌ Integrity Broken</span>'}
            </div>
        ` : '';

        // Sign-off Information
        const signoffHtml = detail.signoff ? `
            <div class="signoff-info">
                <div class="signoff-header">
                    <span class="material-icons md-18">edit</span>
                    <strong>Signed</strong>
                </div>
                <div class="signoff-details">
                    <p><strong>Signed By:</strong> ${this.escapeHtml(detail.signoff.signed_by)}</p>
                    <p><strong>Time:</strong> ${this.formatTimestamp(detail.signoff.sign_timestamp)}</p>
                    <p><strong>Note:</strong> ${this.escapeHtml(detail.signoff.sign_note)}</p>
                </div>
            </div>
        ` : '';

        // 签字按钮
        const needSignoff = detail.status === 'PENDING' && detail.final_verdict === 'REQUIRE_SIGNOFF';
        const signoffButtonHtml = needSignoff ? `
            <button id="signoff-btn" class="btn-signoff">
                <span class="material-icons md-18">edit</span> Sign Off
            </button>
        ` : '';

        // 重放对比
        let replayHtml = '';
        if (replay) {
            replayHtml = `
                <div class="replay-section">
                    <h4>Cognitive Comparison</h4>
                    <div class="compare-panels">
                        <div class="compare-panel">
                            <h5>Cognition at Time</h5>
                            <div class="compare-content">
                                ${this.renderReplayData(replay.then_state)}
                            </div>
                        </div>
                        <div class="compare-panel">
                            <h5>Current Cognition</h5>
                            <div class="compare-content">
                                ${this.renderReplayData(replay.now_state)}
                            </div>
                        </div>
                    </div>
                    ${replay.changed_facts && replay.changed_facts.length > 0 ? `
                        <div class="changed-facts">
                            <h5>Changed Facts</h5>
                            <ul>
                                ${replay.changed_facts.map(fact => `<li>${this.escapeHtml(fact)}</li>`).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
            `;
        }

        detailContent.innerHTML = `
            <div class="detail-header">
                <div>
                    <h3>${this.escapeHtml(detail.decision_type)}</h3>
                    <p class="decision-id">ID: ${this.escapeHtml(detail.decision_id)}</p>
                </div>
                <div class="header-badges">
                    <span class="status-badge status-${statusClass}">${this.escapeHtml(detail.status)}</span>
                    <span class="verdict-badge verdict-${verdictClass}">${this.escapeHtml(detail.final_verdict)}</span>
                </div>
            </div>

            <div class="detail-body">
                <!-- Basic Information -->
                <div class="info-section">
                    <h4>Basic Information</h4>
                    <div class="info-grid">
                        <div class="info-item">
                            <label>Seed</label>
                            <span>${this.escapeHtml(detail.seed)}</span>
                        </div>
                        <div class="info-item">
                            <label>Time</label>
                            <span>${this.formatTimestamp(detail.timestamp)}</span>
                        </div>
                        ${detail.confidence_score !== null && detail.confidence_score !== undefined ? `
                            <div class="info-item">
                                <label>Confidence</label>
                                <span>${(detail.confidence_score * 100).toFixed(0)}%</span>
                            </div>
                        ` : ''}
                    </div>
                    ${integrityHtml}
                </div>

                <!-- Triggered Rules -->
                ${detail.rules_triggered && detail.rules_triggered.length > 0 ? `
                    <div class="rules-section">
                        <h4>Triggered Rules</h4>
                        <div class="rules-list">
                            ${detail.rules_triggered.map(rule => `
                                <div class="rule-item">
                                    <div class="rule-header">
                                        <span class="rule-name">${this.escapeHtml(rule.rule_name || rule.rule_id)}</span>
                                        <span class="rule-action verdict-${this.getVerdictClass(rule.action)}">${this.escapeHtml(rule.action)}</span>
                                    </div>
                                    ${rule.rationale ? `
                                        <div class="rule-rationale">${this.escapeHtml(rule.rationale)}</div>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}

                <!-- Sign-off Information -->
                ${signoffHtml}

                <!-- 重放对比 -->
                ${replayHtml}

                <!-- Audit Trail -->
                ${detail.audit_trail ? `
                    <div class="audit-section">
                        <h4>Audit Trail</h4>
                        <pre class="audit-trail">${this.escapeHtml(JSON.stringify(detail.audit_trail, null, 2))}</pre>
                    </div>
                ` : ''}
            </div>

            ${needSignoff ? `
                <div class="detail-footer">
                    ${signoffButtonHtml}
                </div>
            ` : ''}
        `;

        // 附加签字按钮事件
        if (needSignoff) {
            const signoffBtn = document.getElementById('signoff-btn');
            if (signoffBtn) {
                signoffBtn.addEventListener('click', () => {
                    this.openSignoffModal(detail);
                });
            }
        }
    }

    /**
     * 渲染重放数据
     */
    renderReplayData(state) {
        if (!state) {
            return '<p class="text-gray-500">No data</p>';
        }

        const items = [];

        if (state.results && state.results.length > 0) {
            items.push(`<div class="state-item"><strong>Result count:</strong> ${state.results.length}</div>`);
        }

        if (state.top_result) {
            items.push(`
                <div class="state-item">
                    <strong>Top Result:</strong>
                    <div class="result-card">
                        <p>${this.escapeHtml(state.top_result.content || '').substring(0, 200)}...</p>
                        <small>Score: ${(state.top_result.score || 0).toFixed(3)}</small>
                    </div>
                </div>
            `);
        }

        if (state.metadata) {
            items.push(`
                <div class="state-item">
                    <strong>Metadata:</strong>
                    <pre class="metadata-json">${this.escapeHtml(JSON.stringify(state.metadata, null, 2))}</pre>
                </div>
            `);
        }

        return items.length > 0 ? items.join('') : '<p class="text-gray-500">No data</p>';
    }

    /**
     * Open签字模态框
     */
    openSignoffModal(decision) {
        const modal = document.createElement('div');
        modal.className = 'signoff-modal';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Sign Decision</h3>
                    <button class="btn-close">
                        <span class="material-icons md-18">close</span>
                    </button>
                </div>
                <div class="modal-body">
                    <!-- Decision Summary -->
                    <div class="decision-summary">
                        <h4>Decision Summary</h4>
                        <div class="summary-grid">
                            <div class="summary-item">
                                <label>Type</label>
                                <span>${this.escapeHtml(decision.decision_type)}</span>
                            </div>
                            <div class="summary-item">
                                <label>Seed</label>
                                <span>${this.escapeHtml(decision.seed)}</span>
                            </div>
                            <div class="summary-item">
                                <label>Governance Action</label>
                                <span class="verdict-badge verdict-${this.getVerdictClass(decision.final_verdict)}">
                                    ${this.escapeHtml(decision.final_verdict)}
                                </span>
                            </div>
                        </div>
                    </div>

                    <!-- 触发Reason -->
                    ${decision.rules_triggered && decision.rules_triggered.length > 0 ? `
                        <div class="signoff-reason">
                            <h4>Why Sign-off Required</h4>
                            <ul>
                                ${decision.rules_triggered.map(rule => `
                                    <li>
                                        <strong>${this.escapeHtml(rule.rule_name || rule.rule_id)}</strong>
                                        ${rule.rationale ? `<br><small>${this.escapeHtml(rule.rationale)}</small>` : ''}
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}

                    <!-- 签字表单 -->
                    <div class="signoff-form">
                        <div class="form-group">
                            <label for="signoff-signer">Signed By *</label>
                            <input type="text" id="signoff-signer" class="form-input" placeholder="Enter your name" required>
                        </div>
                        <div class="form-group">
                            <label for="signoff-note">Note *</label>
                            <textarea id="signoff-note" class="form-textarea" rows="4" placeholder="Please provide reason for sign-off..." required></textarea>
                        </div>
                    </div>

                    <div id="signoff-error" class="error-message" style="display: none;"></div>
                </div>
                <div class="modal-footer">
                    <button id="cancel-signoff-btn" class="btn-secondary">Cancel</button>
                    <button id="confirm-signoff-btn" class="btn-primary">Confirm Sign-off</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close模态框
        const closeModal = () => {
            modal.remove();
        };

        modal.querySelector('.btn-close').addEventListener('click', closeModal);
        modal.querySelector('.modal-overlay').addEventListener('click', closeModal);
        modal.querySelector('#cancel-signoff-btn').addEventListener('click', closeModal);

        // Confirm Sign-off
        modal.querySelector('#confirm-signoff-btn').addEventListener('click', async () => {
            const signer = document.getElementById('signoff-signer').value.trim();
            const note = document.getElementById('signoff-note').value.trim();
            const errorDiv = document.getElementById('signoff-error');

            if (!signer || !note) {
                errorDiv.textContent = 'Please fill in all required fields';
                errorDiv.style.display = 'block';
                return;
            }

            try {
                errorDiv.style.display = 'none';
                const confirmBtn = modal.querySelector('#confirm-signoff-btn');
                confirmBtn.disabled = true;
                confirmBtn.textContent = 'Submitting...';

                await this.submitSignoff(decision.decision_id, signer, note);

                closeModal();

                // Refresh列表和Details
                await this.loadDecisions();
                if (this.selectedDecision) {
                    await this.loadDecisionDetail(this.selectedDecision.decision_id);
                }
            } catch (error) {
                console.error('Signoff failed:', error);
                errorDiv.textContent = `Sign-off failed: ${error.message}`;
                errorDiv.style.display = 'block';

                const confirmBtn = modal.querySelector('#confirm-signoff-btn');
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Confirm Sign-off';
            }
        });

        // ESC 键Close
        const handleEsc = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', handleEsc);
            }
        };
        document.addEventListener('keydown', handleEsc);
    }

    /**
     * 提交签字
     */
    async submitSignoff(decisionId, signedBy, note) {
        // Layer 3: 二次确认对话框
        const confirmed = await Dialog.confirm(
            '您即将对该决策进行正式签字。此操作不可撤销，具有法律效力。',
            {
                title: '确认决策签字',
                confirmText: '确认签字',
                cancelText: '取消',
                danger: true
            }
        );

        if (!confirmed) {
            console.log('[DecisionReview] User cancelled signoff confirmation');
            throw new Error('用户取消了签字确认');
        }

        // CSRF Fix: Use fetchWithCSRF for protected endpoint
        // Layer 3: Add X-Confirm-Intent header for extra protection
        const response = await window.fetchWithCSRF(`/api/brain/governance/decisions/${decisionId}/signoff`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Confirm-Intent': 'decision-signoff'  // Layer 3: Confirm Intent
            },
            body: JSON.stringify({
                signed_by: signedBy,
                note: note
            })
        });

        if (!response.ok) {
            const result = await response.json();
            throw new Error(result.error || `HTTP ${response.status}`);
        }

        const result = await response.json();
        if (!result.ok) {
            throw new Error(result.error || 'Sign-off failed');
        }

        return result.data;
    }

    /**
     * 应用过滤器
     */
    applyFilters() {
        this.renderTimeline();
        this.updateDecisionCount();
    }

    /**
     * 获取过滤后的决策
     */
    getFilteredDecisions() {
        return this.decisions.filter(decision => {
            if (this.filters.type && decision.decision_type !== this.filters.type) {
                return false;
            }
            if (this.filters.status && decision.status !== this.filters.status) {
                return false;
            }
            return true;
        });
    }

    /**
     * 更新决策计数
     */
    updateDecisionCount() {
        const countBadge = document.getElementById('decision-count');
        if (countBadge) {
            const count = this.getFilteredDecisions().length;
            countBadge.textContent = count;
        }
    }

    /**
     * 渲染ErrorStatus
     */
    renderError(container, error) {
        container.innerHTML = `
            <div class="error-state">
                <span class="material-icons md-48">error</span>
                <h3>Load failed</h3>
                <p>${this.escapeHtml(error.message)}</p>
                <button id="retry-btn" class="btn-primary">Retry</button>
            </div>
        `;

        const retryBtn = document.getElementById('retry-btn');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                this.loadDecisions();
            });
        }
    }

    /**
     * 渲染DetailsErrorStatus
     */
    renderDetailError(container, error) {
        container.innerHTML = `
            <div class="error-state">
                <span class="material-icons md-48">error</span>
                <h3>Failed to load details</h3>
                <p>${this.escapeHtml(error.message)}</p>
            </div>
        `;
    }

    /**
     * 获取Status CSS 类
     */
    getStatusClass(status) {
        const map = {
            'PENDING': 'pending',
            'APPROVED': 'approved',
            'BLOCKED': 'blocked',
            'SIGNED': 'signed',
            'FAILED': 'failed'
        };
        return map[status] || 'default';
    }

    /**
     * 获取Governance Action CSS 类
     */
    getVerdictClass(verdict) {
        const map = {
            'ALLOW': 'allow',
            'WARN': 'warn',
            'BLOCK': 'block',
            'REQUIRE_SIGNOFF': 'signoff'
        };
        return map[verdict] || 'default';
    }

    /**
     * 格式化Time戳
     */
    formatTimestamp(timestamp) {
        if (!timestamp) return 'N/A';

        try {
            const date = new Date(timestamp);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}minutes ago`;
            if (diffHours < 24) return `${diffHours}hours ago`;
            if (diffDays < 7) return `${diffDays}days ago`;

            return date.toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return timestamp;
        }
    }

    /**
     * 转义 HTML
     */
    escapeHtml(text) {
        if (text === null || text === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(text);
        return div.innerHTML;
    }

    /**
     * 销毁视图
     */
    destroy() {
        this.decisions = [];
        this.selectedDecision = null;
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Export到全局
window.DecisionReviewView = DecisionReviewView;
