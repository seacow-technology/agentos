/**
 * Memory Proposals View - Review and approve/reject Memory proposals
 *
 * Task #18: UI Display Capability Status
 * Coverage: GET /api/memory/proposals, POST /api/memory/proposals/{id}/approve, POST /api/memory/proposals/{id}/reject
 */

class MemoryProposalsView {
    constructor(container) {
        this.container = container;
        this.currentFilter = 'pending';  // pending|approved|rejected|all
        this.proposals = [];
        this.refreshInterval = null;
    }

    async render() {
        this.container.innerHTML = `
            <div class="proposals-container">
                <div class="proposals-header">
                    <div>
                        <h1>Memory Proposals</h1>
                        <p class="text-sm text-gray-600 mt-1">Review and approve memory proposals from agents</p>
                    </div>
                    <div class="proposals-actions">
                        <button class="btn-refresh" id="refresh-proposals">
                            <span class="material-icons md-18">refresh</span> Refresh
                        </button>
                    </div>
                </div>

                <div class="proposals-filters">
                    <button class="filter-btn active" data-filter="pending">
                        Pending (<span id="pending-count">0</span>)
                    </button>
                    <button class="filter-btn" data-filter="approved">
                        Approved (<span id="approved-count">0</span>)
                    </button>
                    <button class="filter-btn" data-filter="rejected">
                        Rejected (<span id="rejected-count">0</span>)
                    </button>
                    <button class="filter-btn" data-filter="all">
                        All
                    </button>
                </div>

                <div class="proposals-content" id="proposals-content">
                    <div class="loading-state">
                        <div class="spinner"></div>
                        <p>Loading proposals...</p>
                    </div>
                </div>
            </div>
        `;

        // Attach event listeners
        this.container.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.handleFilterChange(e));
        });

        const refreshBtn = this.container.querySelector('#refresh-proposals');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadProposals(true));
        }

        // Load initial data
        await this.loadProposals();

        // Auto-refresh every 30 seconds
        this.refreshInterval = setInterval(() => this.loadProposals(), 30000);
    }

    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    handleFilterChange(e) {
        // Update active button
        this.container.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        e.target.closest('.filter-btn').classList.add('active');

        // Update filter and reload
        this.currentFilter = e.target.closest('.filter-btn').dataset.filter;
        this.renderProposals();
    }

    async loadProposals(forceRefresh = false) {
        try {
            const params = new URLSearchParams({
                agent_id: 'user:current',  // Current user (has ADMIN)
                limit: 100
            });

            const response = await fetch(`/api/memory/proposals?${params}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${await response.text()}`);
            }

            const data = await response.json();

            this.proposals = data.proposals || [];
            this.updateCounts();
            this.renderProposals();

            if (forceRefresh && window.showToast) {
                window.showToast(`Loaded ${this.proposals.length} proposals`, 'success', 1500);
            }

        } catch (error) {
            console.error('[Proposals] Failed to load:', error);
            const contentEl = this.container.querySelector('#proposals-content');
            if (contentEl) {
                contentEl.innerHTML = `
                    <div class="error-state">
                        <span class="material-icons" style="font-size: 48px; color: #f44336;">error_outline</span>
                        <p class="error-message">Failed to load proposals</p>
                        <p class="error-detail">${error.message}</p>
                    </div>
                `;
            }

            if (window.showToast) {
                window.showToast(`Error: ${error.message}`, 'error');
            }
        }
    }

    updateCounts() {
        const counts = {
            pending: 0,
            approved: 0,
            rejected: 0
        };

        this.proposals.forEach(p => {
            if (counts[p.status] !== undefined) {
                counts[p.status]++;
            }
        });

        const pendingEl = this.container.querySelector('#pending-count');
        const approvedEl = this.container.querySelector('#approved-count');
        const rejectedEl = this.container.querySelector('#rejected-count');

        if (pendingEl) pendingEl.textContent = counts.pending;
        if (approvedEl) approvedEl.textContent = counts.approved;
        if (rejectedEl) rejectedEl.textContent = counts.rejected;
    }

    renderProposals() {
        const content = this.container.querySelector('#proposals-content');
        if (!content) return;

        // Filter proposals
        let filtered = this.proposals;
        if (this.currentFilter !== 'all') {
            filtered = this.proposals.filter(p => p.status === this.currentFilter);
        }

        if (filtered.length === 0) {
            content.innerHTML = `
                <div class="empty-state">
                    <span class="material-icons" style="font-size: 64px; color: #9e9e9e;">inbox</span>
                    <p class="empty-message">No ${this.currentFilter} proposals</p>
                </div>
            `;
            return;
        }

        // Render proposals
        let html = '<div class="proposals-list">';

        for (const proposal of filtered) {
            html += this.renderProposalCard(proposal);
        }

        html += '</div>';
        content.innerHTML = html;

        // Attach action button listeners
        this.attachActionListeners();
    }

    renderProposalCard(proposal) {
        const memoryItem = proposal.memory_item;
        const content = memoryItem.content || {};

        // Status badge styling
        const statusStyles = {
            'pending': { bg: '#fff3e0', color: '#e65100' },
            'approved': { bg: '#e8f5e9', color: '#2e7d32' },
            'rejected': { bg: '#ffebee', color: '#c62828' }
        };
        const style = statusStyles[proposal.status] || { bg: '#f5f5f5', color: '#616161' };

        // Format timestamp
        const proposedTime = this.formatTimestamp(proposal.proposed_at_ms);
        const reviewedTime = proposal.reviewed_at_ms
            ? this.formatTimestamp(proposal.reviewed_at_ms)
            : null;

        return `
            <div class="proposal-card" data-proposal-id="${proposal.proposal_id}">
                <div class="proposal-header">
                    <div class="proposal-meta">
                        <span class="proposal-id">#${proposal.proposal_id.slice(0, 8)}</span>
                        <span class="status-badge" style="background-color: ${style.bg}; color: ${style.color};">
                            ${proposal.status.toUpperCase()}
                        </span>
                        <span class="badge badge-info">${memoryItem.type || 'memory'}</span>
                        <span class="badge badge-secondary">${memoryItem.scope || 'global'}</span>
                    </div>
                    <div class="proposal-time">
                        <span class="text-xs text-gray-600">Proposed ${proposedTime}</span>
                        ${reviewedTime ? `<span class="text-xs text-gray-600">Reviewed ${reviewedTime}</span>` : ''}
                    </div>
                </div>

                <div class="proposal-body">
                    <div class="proposal-content">
                        <div class="content-label">Memory Content:</div>
                        <div class="content-key-value">
                            <span class="content-key">${this.escapeHtml(content.key || 'N/A')}</span>
                            <span class="material-icons md-18" style="color: #9e9e9e;">arrow_forward</span>
                            <span class="content-value">${this.escapeHtml(content.value || JSON.stringify(content))}</span>
                        </div>
                    </div>

                    <div class="proposal-proposer">
                        <div class="proposer-label">Proposed by:</div>
                        <div class="proposer-id">${this.escapeHtml(proposal.proposed_by)}</div>
                        ${proposal.metadata?.reason ? `
                            <div class="proposer-reason">"${this.escapeHtml(proposal.metadata.reason)}"</div>
                        ` : ''}
                    </div>

                    ${proposal.status !== 'pending' ? `
                        <div class="proposal-review">
                            <div class="review-label">Reviewed by:</div>
                            <div class="review-id">${this.escapeHtml(proposal.reviewed_by || 'N/A')}</div>
                            ${proposal.review_reason ? `
                                <div class="review-reason">"${this.escapeHtml(proposal.review_reason)}"</div>
                            ` : ''}
                            ${proposal.resulting_memory_id ? `
                                <div class="review-result">
                                    Memory ID: <code>${this.escapeHtml(proposal.resulting_memory_id)}</code>
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                </div>

                ${proposal.status === 'pending' ? `
                    <div class="proposal-actions">
                        <button class="btn-approve btn-sm btn-success" data-proposal-id="${proposal.proposal_id}">
                            <span class="material-icons md-18">check_circle</span> Approve
                        </button>
                        <button class="btn-reject btn-sm btn-danger" data-proposal-id="${proposal.proposal_id}">
                            <span class="material-icons md-18">cancel</span> Reject
                        </button>
                    </div>
                ` : ''}
            </div>
        `;
    }

    attachActionListeners() {
        // Approve buttons
        this.container.querySelectorAll('.btn-approve').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const proposalId = e.target.closest('.btn-approve').dataset.proposalId;
                this.handleApprove(proposalId);
            });
        });

        // Reject buttons
        this.container.querySelectorAll('.btn-reject').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const proposalId = e.target.closest('.btn-reject').dataset.proposalId;
                this.handleReject(proposalId);
            });
        });
    }

    async handleApprove(proposalId) {
        const reason = prompt('Approval reason (optional):');
        // User clicked cancel
        if (reason === null) return;

        try {
            const response = await fetch(`/api/memory/proposals/${proposalId}/approve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCsrfToken()
                },
                body: JSON.stringify({
                    reviewer_id: 'user:current',
                    reason: reason || 'Approved'
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const result = await response.json();

            // Show success
            if (window.showToast) {
                window.showToast(`Proposal approved! Memory ID: ${result.memory_id}`, 'success');
            }

            // Reload
            await this.loadProposals();

        } catch (error) {
            console.error('[Proposals] Approve failed:', error);
            if (window.showToast) {
                window.showToast(`Failed to approve: ${error.message}`, 'error');
            }
        }
    }

    async handleReject(proposalId) {
        const reason = prompt('Rejection reason (REQUIRED):');

        if (!reason || !reason.trim()) {
            if (window.showToast) {
                window.showToast('Rejection reason is required', 'warning');
            }
            return;
        }

        try {
            const response = await fetch(`/api/memory/proposals/${proposalId}/reject`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCsrfToken()
                },
                body: JSON.stringify({
                    reviewer_id: 'user:current',
                    reason: reason
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            // Show success
            if (window.showToast) {
                window.showToast(`Proposal rejected: "${reason}"`, 'success');
            }

            // Reload
            await this.loadProposals();

        } catch (error) {
            console.error('[Proposals] Reject failed:', error);
            if (window.showToast) {
                window.showToast(`Failed to reject: ${error.message}`, 'error');
            }
        }
    }

    formatTimestamp(ms) {
        const date = new Date(ms);
        const now = new Date();
        const diff = now - date;

        // Less than 1 minute
        if (diff < 60000) return 'just now';

        // Less than 1 hour
        if (diff < 3600000) {
            const mins = Math.floor(diff / 60000);
            return `${mins} min${mins > 1 ? 's' : ''} ago`;
        }

        // Less than 24 hours
        if (diff < 86400000) {
            const hours = Math.floor(diff / 3600000);
            return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        }

        // Format as date
        return date.toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
