/**
 * RouteDecisionCard - Display routing decision when creating tasks
 *
 * PR-4: Router Visualization Enhancement
 *
 * Features:
 * - Display selected instance prominently
 * - Show routing reasons and scores
 * - Display fallback chain
 * - Allow manual instance change
 */

class RouteDecisionCard {
    constructor(container, routePlan, options = {}) {
        this.container = container;
        this.routePlan = routePlan;
        this.options = {
            onChangeInstance: null,
            ...options
        };

        this.render();
    }

    render() {
        if (!this.routePlan) {
            this.container.innerHTML = '<div class="route-card-empty">No routing information available</div>';
            return;
        }

        const selected = this.routePlan.selected || 'unknown';
        const reasons = this.routePlan.reasons || [];
        const scores = this.routePlan.scores || {};
        const fallback = this.routePlan.fallback || [];

        this.container.innerHTML = `
            <div class="route-decision-card">
                <div class="route-card-header">
                    <h3>Route Decision</h3>
                    ${this.options.onChangeInstance ? `
                        <button class="btn-change-instance" id="route-change-btn">
                            Change
                        </button>
                    ` : ''}
                </div>

                <div class="route-card-body">
                    <!-- Selected Instance (Prominent) -->
                    <div class="route-selected-section">
                        <div class="route-label">Selected Instance</div>
                        <div class="route-selected-instance">${selected}</div>
                    </div>

                    <!-- Reasons -->
                    ${reasons.length > 0 ? `
                        <div class="route-reasons-section">
                            <div class="route-label">Reasons</div>
                            <ul class="route-reasons-list">
                                ${reasons.map(reason => `
                                    <li class="route-reason-item">
                                        <span class="material-icons md-18">check</span>
                                        <span class="reason-text">${this.formatReason(reason)}</span>
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}

                    <!-- Scores -->
                    ${Object.keys(scores).length > 0 ? `
                        <div class="route-scores-section">
                            <div class="route-label">Instance Scores</div>
                            <div class="route-scores-chart">
                                ${Object.entries(scores)
                                    .sort(([, a], [, b]) => b - a)
                                    .map(([instance, score]) => `
                                        <div class="route-score-item ${instance === selected ? 'selected' : ''}">
                                            <div class="score-instance-name">${instance}</div>
                                            <div class="score-bar-wrapper">
                                                <div class="score-bar" style="width: ${score * 100}%"></div>
                                                <div class="score-value">${(score * 100).toFixed(1)}%</div>
                                            </div>
                                        </div>
                                    `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    <!-- Fallback Chain -->
                    ${fallback.length > 0 ? `
                        <div class="route-fallback-section">
                            <div class="route-label">
                                Fallback Chain
                                <span class="route-label-hint">(if primary fails)</span>
                            </div>
                            <div class="route-fallback-chain">
                                ${fallback.map((inst, idx) => `
                                    <div class="fallback-item">
                                        <span class="fallback-number">${idx + 1}</span>
                                        <span class="fallback-name">${inst}</span>
                                    </div>
                                `).join('<div class="fallback-arrow"><span class="material-icons md-18">arrow_forward</span></div>')}
                            </div>
                        </div>
                    ` : ''}
                </div>

                ${this.routePlan.router_version ? `
                    <div class="route-card-footer">
                        <small>Router version: ${this.routePlan.router_version}</small>
                        ${this.routePlan.timestamp ? `
                            <small>Decided at: ${new Date(this.routePlan.timestamp).toLocaleString()}</small>
                        ` : ''}
                    </div>
                ` : ''}
            </div>
        `;

        // Setup event listeners
        if (this.options.onChangeInstance) {
            const changeBtn = this.container.querySelector('#route-change-btn');
            if (changeBtn) {
                changeBtn.addEventListener('click', () => {
                    this.options.onChangeInstance(this.routePlan);
                });
            }
        }
    }

    formatReason(reason) {
        // Format reason strings to be more human-readable
        const replacements = {
            'READY': 'Instance is ready',
            'tags_match': 'Tags match requirements',
            'capability_match': 'Capabilities match',
            'ctx>=': 'Context size sufficient (≥',
            'local_preferred': 'Local instance preferred',
            'latency': 'Low latency'
        };

        let formatted = reason;
        for (const [key, value] of Object.entries(replacements)) {
            formatted = formatted.replace(key, value);
        }

        return formatted;
    }

    update(routePlan) {
        this.routePlan = routePlan;
        this.render();
    }

    destroy() {
        this.container.innerHTML = '';
    }
}

// Export
window.RouteDecisionCard = RouteDecisionCard;
