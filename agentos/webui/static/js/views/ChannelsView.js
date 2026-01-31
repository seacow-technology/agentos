/**
 * ChannelsView - Communication Channels Marketplace
 *
 * Features:
 * - Browse available channel adapters
 * - Setup new channels via wizard
 * - Manage existing channels
 * - View channel status and health
 */

class ChannelsView {
    constructor(container) {
        this.container = container;
        this.manifests = [];
        this.configuredChannels = [];
        this.currentWizard = null;

        this.init();
    }

    async init() {
        this.render();
        await this.loadData();
    }

    render() {
        this.container.innerHTML = `
            <div class="channels-view">
                <div class="view-header">
                    <div>
                        <h1>Communication Channels</h1>
                        <p class="text-sm text-gray-600 mt-1">
                            Connect external messaging platforms to AgentOS
                        </p>
                    </div>
                    <div class="header-actions">
                        <button class="btn-refresh" id="channels-refresh">
                            <span class="material-icons md-18">refresh</span>
                            Refresh
                        </button>
                    </div>
                </div>

                <!-- Configured Channels Section -->
                <div class="channels-section">
                    <div class="section-header">
                        <h2>Your Channels</h2>
                    </div>
                    <div id="configured-channels" class="channels-grid">
                        <div class="loading-spinner">Loading configured channels...</div>
                    </div>
                </div>

                <!-- Available Channels Section -->
                <div class="channels-section">
                    <div class="section-header">
                        <h2>Available Channels</h2>
                        <p class="text-sm text-gray-600">
                            Choose from our marketplace of verified channel adapters
                        </p>
                    </div>
                    <div id="available-channels" class="channels-grid">
                        <div class="loading-spinner">Loading available channels...</div>
                    </div>
                </div>

                <!-- Wizard Container -->
                <div id="wizard-container"></div>
            </div>
        `;

        this.setupEventListeners();
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = this.container.querySelector('#channels-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadData());
        }

        // Delegated event listeners for channel cards
        this.container.addEventListener('click', (e) => {
            const setupBtn = e.target.closest('.btn-setup-channel');
            if (setupBtn) {
                const manifestId = setupBtn.dataset.manifestId;
                this.openSetupWizard(manifestId);
            }

            const detailsBtn = e.target.closest('.btn-channel-details');
            if (detailsBtn) {
                const channelId = detailsBtn.dataset.channelId;
                this.showChannelDetails(channelId);
            }

            const toggleBtn = e.target.closest('.btn-toggle-channel');
            if (toggleBtn) {
                const channelId = toggleBtn.dataset.channelId;
                this.toggleChannel(channelId);
            }
        });
    }

    async loadData() {
        await Promise.all([
            this.loadManifests(),
            this.loadConfiguredChannels()
        ]);
    }

    async loadManifests() {
        try {
            const response = await fetch('/api/channels/manifests');
            const result = await response.json();

            if (result.ok) {
                this.manifests = result.data.manifests;
                this.renderAvailableChannels();
            } else {
                Toast.error('Failed to load available channels');
            }
        } catch (error) {
            console.error('Error loading manifests:', error);
            Toast.error('Failed to load available channels');
        }
    }

    async loadConfiguredChannels() {
        try {
            // TODO: Add API endpoint to list configured channels
            // For now, show placeholder
            const configuredContainer = this.container.querySelector('#configured-channels');
            if (configuredContainer) {
                configuredContainer.innerHTML = `
                    <div class="empty-state">
                        <span class="material-icons" style="font-size: 48px; color: var(--text-secondary);">
                            add_circle_outline
                        </span>
                        <p>No channels configured yet</p>
                        <p class="text-sm text-gray-600">
                            Choose a channel from the marketplace below to get started
                        </p>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error loading configured channels:', error);
        }
    }

    renderAvailableChannels() {
        const container = this.container.querySelector('#available-channels');
        if (!container) return;

        if (this.manifests.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <span class="material-icons" style="font-size: 48px; color: var(--text-secondary);">
                        inventory_2
                    </span>
                    <p>No channels available</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.manifests.map(manifest => this.renderChannelCard(manifest)).join('');
    }

    renderChannelCard(manifest) {
        const isVerified = manifest.metadata?.verified || false;
        const isOfficial = manifest.metadata?.official || false;
        const difficulty = manifest.metadata?.setup_difficulty || 'medium';
        const cost = manifest.metadata?.cost || 'free';

        return `
            <div class="channel-card" data-manifest-id="${manifest.id}">
                <div class="channel-card-header">
                    <div class="channel-icon">
                        <span class="material-icons">${this.getChannelIcon(manifest.icon)}</span>
                    </div>
                    <div class="channel-badges">
                        ${isOfficial ? '<span class="badge badge-official">Official</span>' : ''}
                        ${isVerified ? '<span class="badge badge-verified"><span class="material-icons md-14">verified</span></span>' : ''}
                    </div>
                </div>

                <div class="channel-card-body">
                    <h3>${manifest.name}</h3>
                    <p class="channel-description">${manifest.description}</p>

                    <div class="channel-meta">
                        <div class="meta-item">
                            <span class="material-icons md-16">business</span>
                            <span>${manifest.provider || 'Unknown'}</span>
                        </div>
                        <div class="meta-item">
                            <span class="material-icons md-16">speed</span>
                            <span class="difficulty difficulty-${difficulty}">${difficulty}</span>
                        </div>
                        <div class="meta-item">
                            <span class="material-icons md-16">attach_money</span>
                            <span>${cost}</span>
                        </div>
                    </div>

                    <div class="channel-capabilities">
                        ${manifest.capabilities.slice(0, 3).map(cap => `
                            <span class="capability-tag">${this.formatCapability(cap)}</span>
                        `).join('')}
                        ${manifest.capabilities.length > 3 ? `
                            <span class="capability-tag">+${manifest.capabilities.length - 3} more</span>
                        ` : ''}
                    </div>
                </div>

                <div class="channel-card-footer">
                    <button
                        class="btn-setup-channel btn-primary"
                        data-manifest-id="${manifest.id}"
                    >
                        <span class="material-icons md-18">add</span>
                        Setup Channel
                    </button>
                    ${manifest.docs_url ? `
                        <a
                            href="${manifest.docs_url}"
                            target="_blank"
                            rel="noopener noreferrer"
                            class="btn-secondary btn-icon"
                            title="View Documentation"
                        >
                            <span class="material-icons">open_in_new</span>
                        </a>
                    ` : ''}
                </div>
            </div>
        `;
    }

    getChannelIcon(icon) {
        const iconMap = {
            'whatsapp': 'chat',
            'telegram': 'send',
            'slack': 'tag',
            'discord': 'forum',
            'email': 'email'
        };
        return iconMap[icon] || 'message';
    }

    formatCapability(cap) {
        return cap.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    openSetupWizard(manifestId) {
        const wizardContainer = this.container.querySelector('#wizard-container');
        if (!wizardContainer) return;

        // Close existing wizard if any
        if (this.currentWizard) {
            this.currentWizard.destroy();
        }

        // Create new wizard
        this.currentWizard = new ChannelSetupWizard(wizardContainer, {
            manifestId: manifestId,
            onComplete: (channelId) => {
                this.handleSetupComplete(channelId);
            },
            onCancel: () => {
                this.handleSetupCancel();
            }
        });
    }

    handleSetupComplete(channelId) {
        Toast.success('Channel setup completed successfully');

        // Close wizard
        if (this.currentWizard) {
            this.currentWizard.destroy();
            this.currentWizard = null;
        }

        // Reload data
        this.loadData();
    }

    handleSetupCancel() {
        // Close wizard
        if (this.currentWizard) {
            this.currentWizard.destroy();
            this.currentWizard = null;
        }
    }

    showChannelDetails(channelId) {
        // TODO: Implement channel details view
        console.log('Show channel details:', channelId);
    }

    async toggleChannel(channelId) {
        // TODO: Implement channel enable/disable
        console.log('Toggle channel:', channelId);
    }

    destroy() {
        if (this.currentWizard) {
            this.currentWizard.destroy();
        }
    }
}

// Register view
window.ChannelsView = ChannelsView;
