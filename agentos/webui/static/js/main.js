// AgentOS WebUI Main JavaScript

// ============================================================================
// WebSocket Log Ring Buffer - Capture [WS] logs for diagnostics
// ============================================================================
(function initWsLogCapture(){
  const max = 200;
  window.__wsLogs = window.__wsLogs || [];

  function push(level, args){
    try {
      const msg = Array.from(args).map(a =>
        (typeof a === 'object' ? JSON.stringify(a) : String(a))
      ).join(' ');

      // Only capture [WS] and [Lifecycle] logs
      if (!msg.includes('[WS]') && !msg.includes('[Lifecycle]')) return;

      window.__wsLogs.push({
        ts: new Date().toISOString(),
        level,
        msg
      });

      // Keep max 200 entries
      if (window.__wsLogs.length > max) {
        window.__wsLogs.splice(0, window.__wsLogs.length - max);
      }
    } catch {}
  }

  // Intercept console methods
  const origLog = console.log;
  const origWarn = console.warn;
  const origErr = console.error;

  console.log = function(...args){
    push('info', args);
    return origLog.apply(console, args);
  };

  console.warn = function(...args){
    push('warn', args);
    return origWarn.apply(console, args);
  };

  console.error = function(...args){
    push('error', args);
    return origErr.apply(console, args);
  };

  // Provide function to get logs
  window.wsGetLogs = (n=20) => (window.__wsLogs || []).slice(-n);
})();

// Global state
const state = {
    currentView: 'chat',
    currentSession: null,  // Will be set when sessions are loaded
    websocket: null,
    healthCheckInterval: null,
    allSessions: [],
    providerStatusInterval: null,
    contextStatusInterval: null,
    currentProvider: null,
    currentViewInstance: null, // PR-2: Track current view instance for cleanup
    projectSelector: null, // Task #18: Project selector component
};

// ============================================================================
// CSRF Protection Helper Functions
// ============================================================================

/**
 * Get CSRF token from cookie.
 * The token is set by the server in the csrf_token cookie.
 * @returns {string|null} CSRF token or null if not found
 */
function getCsrfToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrf_token') {
            return decodeURIComponent(value);
        }
    }
    return null;
}

/**
 * Create fetch options with CSRF token for state-changing requests.
 * Automatically adds X-CSRF-Token header for POST/PUT/PATCH/DELETE requests.
 * @param {Object} options - Original fetch options
 * @returns {Object} Options with CSRF token header added
 */
function withCsrfToken(options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const needsCsrf = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method);

    if (needsCsrf) {
        const token = getCsrfToken();
        if (token) {
            options.headers = options.headers || {};
            options.headers['X-CSRF-Token'] = token;
        } else {
            console.warn('[CSRF] No CSRF token found in cookies for', method, 'request');
        }
    }

    return options;
}

// Initialize application
document.addEventListener('DOMContentLoaded', () => {
    console.log('AgentOS WebUI initializing...');

    // Setup navigation
    setupNavigation();

    // Setup refresh button
    setupRefreshButton();

    // Setup project selector (Task #18)
    setupProjectSelector();

    // Start health check
    startHealthCheck();

    // Start governance badge updates
    startGovernanceBadgeUpdates();

    // Setup WebSocket lifecycle hooks (Safari bfcache, visibility, focus)
    setupWebSocketLifecycle();

    // Load initial view (restore last view or default to chat)
    const lastView = localStorage.getItem('agentos_current_view') || 'chat';
    loadView(lastView);

    // Update navigation active state
    updateNavigationActive(lastView);

    // Auto-clear console every 2 minutes
    setInterval(() => {
        console.clear();
        console.log('Console auto-cleared at', new Date().toLocaleTimeString());
    }, 120000);

    console.log('AgentOS WebUI initialized');
});

// Setup navigation
function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();

            const view = item.dataset.view;

            // Update active state
            updateNavigationActive(view);

            // Load view
            loadView(view);
        });
    });
}

// Update navigation active state
function updateNavigationActive(viewName) {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(nav => {
        if (nav.dataset.view === viewName) {
            nav.classList.add('active');
        } else {
            nav.classList.remove('active');
        }
    });
}

// Session selector removed - use Sessions page for session management
// function setupSessionSelector() { ... }
// function loadSessions() { ... }

// Setup project selector (Task #18)
function setupProjectSelector() {
    const container = document.getElementById('project-selector-container');
    if (!container) {
        console.warn('Project selector container not found');
        return;
    }

    // Only initialize if ProjectSelector is available
    if (typeof ProjectSelector !== 'undefined') {
        state.projectSelector = new ProjectSelector(container);
    } else {
        console.warn('ProjectSelector component not loaded');
    }
}

// Setup refresh button
function setupRefreshButton() {
    const refreshBtn = document.getElementById('refresh-btn');

    refreshBtn.addEventListener('click', () => {
        // Reload current view
        loadView(state.currentView);

        // Refresh health
        updateHealth();

        // Visual feedback
        refreshBtn.classList.add('animate-spin');
        setTimeout(() => {
            refreshBtn.classList.remove('animate-spin');
        }, 500);
    });
}

// Load view
function loadView(viewName) {
    const previousView = state.currentView;
    state.currentView = viewName;

    // Save current view to localStorage for page refresh persistence
    localStorage.setItem('agentos_current_view', viewName);

    // Destroy previous view instance if exists
    if (state.currentViewInstance && typeof state.currentViewInstance.destroy === 'function') {
        state.currentViewInstance.destroy();
        state.currentViewInstance = null;
    }

    // Disconnect WebSocket when leaving chat view
    if (previousView === 'chat' && viewName !== 'chat') {
        console.log('[View] Leaving chat view, disconnecting WebSocket');
        WS.close();
    }

    // Update title
    const viewTitle = document.getElementById('view-title');
    viewTitle.textContent = viewName.charAt(0).toUpperCase() + viewName.slice(1);

    // Load view content
    const container = document.getElementById('view-container');

    switch (viewName) {
        case 'chat':
            renderChatView(container);
            break;
        case 'overview':
            renderOverviewView(container);
            break;
        case 'sessions':
            renderSessionsView(container);
            break;
        case 'projects':
            renderProjectsView(container);
            break;
        case 'tasks':
            renderTasksView(container);
            break;
        case 'events':
            renderEventsView(container);
            break;
        case 'logs':
            renderLogsView(container);
            break;
        case 'history':
            renderHistoryView(container);
            break;
        case 'pipeline':
            renderPipelineView(container);
            break;
        case 'skills':
            renderSkillsView(container);
            break;
        case 'memory':
            renderMemoryView(container);
            break;
        case 'memory-proposals':
            renderMemoryProposalsView(container);
            break;
        case 'memory-timeline':
            renderMemoryTimelineView(container);
            break;
        case 'voice':
            renderVoiceView(container);
            break;
        case 'config':
            renderConfigView(container);
            break;
        case 'context':
            renderContextView(container);
            break;
        case 'runtime':
            renderRuntimeView(container);
            break;
        case 'support':
            renderSupportView(container);
            break;
        case 'providers':
            renderProvidersView(container);
            break;
        case 'knowledge-playground':
            renderKnowledgePlaygroundView(container);
            break;
        case 'knowledge-sources':
            renderKnowledgeSourcesView(container);
            break;
        case 'knowledge-jobs':
            renderKnowledgeJobsView(container);
            break;
        case 'knowledge-health':
            renderKnowledgeHealthView(container);
            break;
        case 'snippets':
            renderSnippetsView(container);
            break;
        case 'governance-dashboard':
            renderGovernanceDashboardView(container);
            break;
        case 'governance-findings':
            renderGovernanceFindingsView(container);
            break;
        case 'governance':
            renderGovernanceView(container);
            break;
        case 'governance-quotas':
            renderQuotaView(container);
            break;
        case 'governance-trust-tiers':
            renderTrustTierView(container);
            break;
        case 'governance-provenance':
            renderProvenanceView(container);
            break;
        case 'lead-scan-history':
            renderLeadScanHistoryView(container);
            break;
        case 'execution-plans':
            renderExecutionPlansView(container);
            break;
        case 'intent-workbench':
            renderIntentWorkbenchView(container);
            break;
        case 'content-registry':
            renderContentRegistryView(container);
            break;
        case 'answer-packs':
        case 'answers':
            renderAnswerPacksView(container);
            break;
        case 'auth':
        case 'auth-profiles':
            renderAuthProfilesView(container);
            break;
        case 'mode-monitor':
            renderModeMonitorView(container);
            break;
        case 'extensions':
            renderExtensionsView(container);
            break;
        case 'marketplace':
            renderMarketplaceView(container);
            break;
        case 'mcp-package-detail':
            renderMCPPackageDetailView(container);
            break;
        case 'models':
            renderModelsView(container);
            break;
        case 'brain-dashboard':
        case 'brain':
            renderBrainDashboardView(container);
            break;
        case 'brain-query':
            renderBrainQueryConsoleView(container);
            break;
        case 'channels':
            renderChannelsView(container);
            break;
        case 'communication':
            renderCommunicationView(container);
            break;
        case 'subgraph':
            renderSubgraphView(container);
            break;
        case 'info-need-metrics':
            renderInfoNeedMetricsView(container);
            break;
        case 'decision-review':
            renderDecisionReviewView(container);
            break;
        case 'capability-dashboard':
            renderCapabilityDashboardView(container);
            break;
        case 'decision-timeline':
            renderDecisionTimelineView(container);
            break;
        case 'action-log':
            renderActionLogView(container);
            break;
        case 'evidence-chain':
            renderEvidenceChainView(container);
            break;
        case 'governance-audit':
            renderGovernanceAuditView(container);
            break;
        case 'agent-matrix':
            renderAgentMatrixView(container);
            break;
        default:
            container.innerHTML = '<div class="p-6 text-gray-500">View not implemented</div>';
    }
}

// Render Chat View - Two Column Layout
function renderChatView(container) {
    container.innerHTML = `
        <div class="flex h-full">
            <!-- Left Column: Conversations List -->
            <div class="w-80 border-r border-gray-200 bg-white flex flex-col" style="min-width: 320px; max-width: 320px;">
                <!-- Search & New Chat -->
                <div class="p-4 border-b border-gray-200">
                    <div class="flex gap-2 mb-3">
                        <input
                            type="text"
                            id="session-search"
                            placeholder="Search conversations..."
                            class="flex-1 text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        <button
                            id="new-chat-btn"
                            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
                            title="New Chat"
                        >
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                            </svg>
                        </button>
                    </div>
                    <div class="flex gap-2">
                        <button
                            id="clear-all-sessions-btn"
                            class="flex-1 px-3 py-2 text-sm border border-red-300 text-red-600 rounded-lg hover:bg-red-50 transition-colors font-medium"
                            title="Clear all sessions"
                        >
                            <svg class="w-4 h-4 inline mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            Clear All
                        </button>
                    </div>
                </div>

                <!-- Batch Conversations Toolbar -->
                <div id="batch-conversations-toolbar" class="border-b border-gray-200 bg-amber-50 px-4 py-2 flex items-center justify-between" style="display: none;">
                    <div class="flex items-center gap-3">
                        <span id="selected-conversations-count" class="text-sm font-medium text-gray-700">0 selected</span>
                        <button
                            id="select-all-conversations-btn"
                            class="text-sm text-blue-600 hover:text-blue-800 font-medium"
                            onclick="toggleSelectAllConversations()"
                        >
                            Select All
                        </button>
                    </div>
                    <div class="flex items-center gap-2">
                        <button
                            id="delete-selected-conversations-btn"
                            class="px-3 py-1.5 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors font-medium flex items-center gap-1"
                            onclick="deleteSelectedConversations()"
                        >
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            Delete Selected
                        </button>
                    </div>
                </div>

                <!-- Conversations List -->
                <div id="conversations-list" class="flex-1 overflow-y-auto">
                    <!-- Will be populated by loadConversationsList() -->
                </div>
            </div>

            <!-- Right Column: Conversation Detail -->
            <div class="flex-1 flex flex-col">
                <!-- Model Toolbar + Session Status (PR-3) -->
                <div id="chat-toolbar" class="border-b border-gray-200 bg-white px-4 py-3">
                    <!-- Row 1: Model Controls -->
                    <div class="flex items-center justify-between gap-4 mb-2">
                        <!-- Left: Model Controls -->
                        <div class="flex items-center gap-3 flex-1">
                            <!-- Model Type -->
                            <select id="model-type" class="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                                <option value="local">Local</option>
                                <option value="cloud">Cloud</option>
                            </select>

                            <!-- Provider -->
                            <select id="model-provider" class="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white min-w-32">
                                <option value="ollama">Ollama</option>
                                <option value="lmstudio">LM Studio</option>
                                <option value="llamacpp">llama.cpp</option>
                            </select>

                            <!-- Model -->
                            <select id="model-name" class="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white min-w-48">
                                <option value="">Select model...</option>
                            </select>

                            <!-- Context Status Pill -->
                            <div id="context-status" class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-100 text-sm">
                                <div class="w-2 h-2 rounded-full bg-gray-400"></div>
                                <span class="font-medium text-gray-600">Empty</span>
                            </div>
                        </div>

                        <!-- Right: Model Link Status + Self-check -->
                        <div class="flex items-center gap-3">
                            <!-- Model Link Status -->
                            <div id="model-link-status" class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-100">
                                <div class="w-2 h-2 rounded-full bg-gray-400"></div>
                                <span class="text-sm font-medium text-gray-600">Disconnected</span>
                            </div>

                            <!-- Self-check Button -->
                            <button
                                id="selfcheck-btn"
                                class="px-4 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors font-medium text-gray-700"
                                title="Run self-check"
                            >
                                Self-check
                            </button>

                            <!-- Settings Icon (for drawer) -->
                            <button
                                id="settings-drawer-btn"
                                class="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                                title="Model & Context Settings"
                            >
                                <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                </svg>
                            </button>
                        </div>
                    </div>

                    <!-- Row 2: Session Status (PR-3: Session binding) -->
                    <div class="flex items-center gap-3 pt-2 border-t border-gray-100">
                        <!-- WS Connection Status -->
                        <div id="chat-ws-status" class="flex items-center gap-2">
                            <div class="w-2 h-2 rounded-full bg-gray-400"></div>
                            <span class="text-xs font-medium text-gray-600">Not Connected</span>
                        </div>

                        <!-- Session ID Display -->
                        <div class="flex items-center gap-2 px-3 py-1 rounded-lg bg-blue-50 border border-blue-200">
                            <span class="text-xs font-semibold text-blue-800">Session:</span>
                            <code id="chat-session-id" class="text-xs font-mono text-blue-900">No session</code>
                            <button
                                id="chat-session-copy"
                                class="text-blue-600 hover:text-blue-800 transition-colors"
                                title="Copy session ID"
                                style="display: none;"
                            >
                                <span class="material-icons md-18">content_copy</span>
                            </button>
                        </div>

                        <!-- View Session Button -->
                        <button
                            id="chat-view-session"
                            class="text-xs px-3 py-1 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                            title="View session details"
                            style="display: none;"
                        >
                            View Session
                        </button>
                    </div>

                    <!-- Row 3: Phase Selector (Task #3) -->
                    <div class="mode-phase-selectors-container pt-2 border-t border-gray-100">
                        <div id="phase-selector-container"></div>
                    </div>
                </div>

                <!-- Messages -->
                <div id="messages" class="flex-1 overflow-y-auto p-6 space-y-4 bg-gray-50">
                    <div class="text-center text-gray-500 text-sm">
                        No messages yet. Start a conversation!
                    </div>
                </div>

                <!-- Input Area -->
                <div class="border-t border-gray-200 bg-white p-4">
                    <div class="relative">
                        <!-- Voice Transcript Preview -->
                        <div id="voice-transcript-preview" class="voice-transcript-preview" style="display: none;">
                            <div class="flex items-center gap-2">
                                <span class="material-icons md-18 text-blue-600">mic</span>
                                <span class="transcript-text text-sm text-gray-700"></span>
                            </div>
                        </div>

                        <!-- Autocomplete Dropdown -->
                        <div id="slash-command-autocomplete" class="slash-command-autocomplete" style="display: none;">
                            <div class="autocomplete-header">Slash Commands</div>
                            <div id="autocomplete-list" class="autocomplete-list">
                                <!-- Command suggestions will be populated here -->
                            </div>
                        </div>

                        <div class="flex gap-2 items-center">
                            <!-- Mode Selector (120px) -->
                            <div id="input-mode-selector-container"></div>

                            <!-- File Upload Button (38px) -->
                            <button
                                id="file-upload-btn"
                                class="chat-input-icon-btn"
                                title="File Upload (Coming Soon)"
                            >
                                <span class="material-icons">attach_file</span>
                            </button>

                            <!-- Voice Input Button (38px) -->
                            <button
                                id="voice-input-btn"
                                class="chat-input-icon-btn"
                                title="Voice Input (Coming Soon)"
                            >
                                <span class="material-icons">mic</span>
                            </button>

                            <!-- Text Input (flex-grow) -->
                            <textarea
                                id="chat-input"
                                placeholder="Type your message... (Shift+Enter for new line, / for commands)"
                                class="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                                rows="1"
                                style="height: 38px; min-height: 38px; line-height: 22px;"
                            ></textarea>

                            <!-- Send Button (70px) -->
                            <button
                                id="send-btn"
                                class="bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                                style="width: 70px; height: 38px; flex-shrink: 0;"
                            >
                                Send
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Setup send button
    const sendBtn = document.getElementById('send-btn');
    const input = document.getElementById('chat-input');

    sendBtn.addEventListener('click', () => sendMessage());

    input.addEventListener('keydown', (e) => {
        // Handle autocomplete navigation
        if (handleAutocompleteKeydown(e)) {
            return; // Autocomplete handled the event
        }

        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Setup autocomplete
    setupSlashCommandAutocomplete(input);

    // Setup new chat button
    document.getElementById('new-chat-btn').addEventListener('click', createNewChat);

    // Setup clear all sessions button
    document.getElementById('clear-all-sessions-btn').addEventListener('click', clearAllSessions);

    // Setup search
    document.getElementById('session-search').addEventListener('input', (e) => {
        filterConversations(e.target.value);
    });

    // Setup file upload button (placeholder)
    document.getElementById('file-upload-btn').addEventListener('click', () => {
        Dialog.alert('File upload feature is coming soon!', { title: 'Coming Soon' });
    });

    // Setup voice input button (real voice interaction)
    initializeChatVoice();

    // Setup toolbar event handlers
    setupModelToolbar();

    // Task #3: Initialize Mode & Phase Selectors
    initializeModePhaseSelectors();

    // Setup code block actions (Preview, Copy)
    setupCodeBlockActions();

    // Initialize chat (load sessions and messages)
    initializeChatView();
}

// Task #3: Mode & Phase Selectors instances
let modeSelectorInstance = null;
let phaseSelectorInstance = null;

// Task #3: Initialize Mode & Phase Selectors
function initializeModePhaseSelectors() {
    const modeContainer = document.getElementById('mode-selector-container');
    const phaseContainer = document.getElementById('phase-selector-container');
    const inputModeContainer = document.getElementById('input-mode-selector-container');

    if (!phaseContainer) {
        console.warn('Phase selector container not found');
        return;
    }

    // Use input area container for mode selector (new design)
    const targetModeContainer = inputModeContainer || modeContainer;

    if (!targetModeContainer) {
        console.warn('Mode selector container not found');
        return;
    }

    // Initialize Mode Selector (in input area)
    // Don't pass sessionId yet - it will be set when sessions are loaded
    modeSelectorInstance = new ModeSelector({
        container: targetModeContainer,
        currentMode: 'chat',  // Default mode
        sessionId: null,  // Will be set by updateModePhaseSelectorsForSession
        onChange: (mode, data) => {
            console.log('Conversation mode changed:', mode, data);

            // Update phase selector when mode changes
            if (phaseSelectorInstance) {
                phaseSelectorInstance.setConversationMode(mode);
            }
        }
    });

    // Initialize Phase Selector (in toolbar)
    // Don't pass sessionId yet - it will be set when sessions are loaded
    phaseSelectorInstance = new PhaseSelector({
        container: phaseContainer,
        currentPhase: 'planning',  // Default phase
        sessionId: null,  // Will be set by updateModePhaseSelectorsForSession
        conversationMode: 'chat',  // Default mode
        onChange: (phase, data) => {
            console.log('Execution phase changed:', phase, data);
        }
    });

    // Task #5: Expose phase selector to global scope for external info warnings
    window.phaseSelectorInstance = phaseSelectorInstance;
}

// Task #3: Update Mode & Phase Selectors when session changes
function updateModePhaseSelectorsForSession(sessionId, sessionData) {
    if (!modeSelectorInstance || !phaseSelectorInstance) {
        return;
    }

    // Extract mode and phase from session metadata
    const mode = sessionData?.conversation_mode || sessionData?.metadata?.conversation_mode || 'chat';
    const phase = sessionData?.execution_phase || sessionData?.metadata?.execution_phase || 'planning';

    // Update session ID
    modeSelectorInstance.setSessionId(sessionId);
    phaseSelectorInstance.setSessionId(sessionId);

    // Update current values
    modeSelectorInstance.setMode(mode);
    phaseSelectorInstance.setPhase(phase);
    phaseSelectorInstance.setConversationMode(mode);
}

// Initialize chat view - load sessions first, then select one
async function initializeChatView() {
    try {
        // Run lightweight chat health check first
        await initChatHealthCheck();

        // Load all sessions
        const response = await fetch('/api/sessions');
        const sessions = await response.json();

        const listContainer = document.getElementById('conversations-list');

        // Store sessions
        state.allSessions = sessions;

        if (sessions.length === 0) {
            // No sessions - show empty state
            listContainer.innerHTML = `
                <div class="p-4 text-center text-gray-500 text-sm">
                    No conversations yet.<br/>
                    Click <strong>+</strong> to start a new chat.
                </div>
            `;

            // Show empty state in messages area
            const messagesDiv = document.getElementById('messages');
            messagesDiv.innerHTML = `
                <div class="flex items-center justify-center h-full text-gray-500">
                    <div class="text-center">
                        <p class="text-lg mb-2">No conversation selected</p>
                        <p class="text-sm">Click <strong>+</strong> to start a new chat</p>
                    </div>
                </div>
            `;

            // Don't setup WebSocket or load messages
            return;
        }

        // Use the first session as current session (MUST be set before rendering list)
        const firstSession = sessions[0];
        state.currentSession = firstSession.id;

        // Render sessions list (will use state.currentSession to highlight)
        renderConversationsList(sessions);

        // Update session display
        updateChatSessionDisplay(firstSession.id);

        // Task #3: Update mode/phase selectors for initial session
        updateModePhaseSelectorsForSession(firstSession.id, firstSession);

        // Restore provider/model from session runtime (or sync from UI if not set)
        await restoreProviderFromSession(firstSession.id);

        // If session has no runtime, sync current UI selection to session
        if (!firstSession.metadata?.runtime || Object.keys(firstSession.metadata.runtime).length === 0) {
            console.log('[Initialization] Session has no runtime, syncing from UI...');
            await updateSessionRuntime();
        }

        // Setup WebSocket for this session
        setupWebSocket();

        // Load messages for this session
        await loadMessages();
    } catch (err) {
        console.error('Failed to initialize chat view:', err);
        const listContainer = document.getElementById('conversations-list');
        listContainer.innerHTML = `
            <div class="p-4 text-center text-red-500 text-sm">
                Failed to load conversations
            </div>
        `;
    }
}

// Setup code block actions (Preview, Copy, Format, Download, Collapse, Theme)
function setupCodeBlockActions() {
    const messagesDiv = document.getElementById('messages');
    if (!messagesDiv) return;

    // Load saved theme
    const savedTheme = localStorage.getItem('prism-theme') || 'tomorrow';
    applyPrismTheme(savedTheme);

    // Use event delegation for dynamically added code blocks
    messagesDiv.addEventListener('click', (e) => {
        const previewBtn = e.target.closest('.js-preview');
        const copyBtn = e.target.closest('.js-copy');
        const formatBtn = e.target.closest('.js-format');
        const downloadBtn = e.target.closest('.js-download');
        const collapseBtn = e.target.closest('.js-collapse');
        const saveSnippetBtn = e.target.closest('.js-save-snippet');

        if (previewBtn) {
            e.preventDefault();
            const codeEl = previewBtn.closest('.codeblock')?.querySelector('pre code');
            if (!codeEl) return;
            openHtmlPreview(codeEl.textContent);
            return;
        }

        if (copyBtn) {
            e.preventDefault();
            const codeEl = copyBtn.closest('.codeblock')?.querySelector('pre code');
            if (!codeEl) return;

            // Copy to clipboard
            navigator.clipboard?.writeText(codeEl.textContent).then(() => {
                // Show success feedback
                const originalHtml = copyBtn.innerHTML;
                copyBtn.innerHTML = `
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Copied!</span>
                `;
                copyBtn.classList.add('btn-action--success');

                setTimeout(() => {
                    copyBtn.innerHTML = originalHtml;
                    copyBtn.classList.remove('btn-action--success');
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy:', err);
                Dialog.alert('Failed to copy code to clipboard', { title: 'Copy Error' });
            });
            return;
        }

        if (formatBtn) {
            e.preventDefault();
            handleFormatCode(formatBtn);
            return;
        }

        if (downloadBtn) {
            e.preventDefault();
            handleDownloadCode(downloadBtn);
            return;
        }

        if (collapseBtn) {
            e.preventDefault();
            handleCollapseCode(collapseBtn);
            return;
        }

        if (saveSnippetBtn) {
            e.preventDefault();
            handleSaveSnippet(saveSnippetBtn);
            return;
        }

        const previewSnippetBtn = e.target.closest('.js-preview-snippet');
        if (previewSnippetBtn) {
            e.preventDefault();
            handlePreviewSnippet(previewSnippetBtn);
            return;
        }

        const makeTaskBtn = e.target.closest('.js-make-task');
        if (makeTaskBtn) {
            e.preventDefault();
            handleMakeTask(makeTaskBtn);
            return;
        }

        // Markdown block actions
        const mdCopyBtn = e.target.closest('.js-md-copy');
        if (mdCopyBtn) {
            e.preventDefault();
            handleMarkdownCopy(mdCopyBtn);
            return;
        }

        const mdDownloadBtn = e.target.closest('.js-md-download');
        if (mdDownloadBtn) {
            e.preventDefault();
            handleMarkdownDownload(mdDownloadBtn);
            return;
        }

        const mdExportBtn = e.target.closest('.js-md-export');
        if (mdExportBtn) {
            e.preventDefault();
            handleMarkdownExport(mdExportBtn);
            return;
        }

        const mdPrintBtn = e.target.closest('.js-md-print');
        if (mdPrintBtn) {
            e.preventDefault();
            handleMarkdownPrint(mdPrintBtn);
            return;
        }
    });

    // Theme selector change event
    messagesDiv.addEventListener('change', (e) => {
        const themeSelector = e.target.closest('.js-theme-selector');
        if (themeSelector) {
            const theme = themeSelector.value;
            applyPrismTheme(theme);
            localStorage.setItem('prism-theme', theme);

            // Update all theme selectors
            document.querySelectorAll('.js-theme-selector').forEach(selector => {
                selector.value = theme;
            });
        }

        // Markdown theme selector
        const mdThemeSelector = e.target.closest('.js-md-theme-selector');
        if (mdThemeSelector) {
            const theme = mdThemeSelector.value;
            const mdBlock = mdThemeSelector.closest('.mdblock');
            if (mdBlock) {
                mdBlock.setAttribute('data-theme', theme);
                localStorage.setItem('markdown-theme', theme);
            }
        }
    });
}

// Handle code formatting
function handleFormatCode(button) {
    const codeblock = button.closest('.codeblock');
    if (!codeblock) return;

    const codeEl = codeblock.querySelector('pre code');
    const lang = codeblock.dataset.lang || '';

    if (!codeEl || !window.prettier) {
        Dialog.alert('Prettier not loaded', { title: 'Format Error' });
        return;
    }

    try {
        const code = codeEl.textContent;
        let parser = 'babel';

        if (lang === 'html' || lang === 'htm') parser = 'html';
        else if (lang === 'css') parser = 'css';
        else if (lang === 'json') parser = 'json';
        else if (lang === 'markdown' || lang === 'md') parser = 'markdown';

        const formatted = prettier.format(code, {
            parser: parser,
            plugins: prettierPlugins,
            printWidth: 80,
            tabWidth: 2,
            semi: true,
            singleQuote: true,
        });

        // Update code content
        codeEl.textContent = formatted;

        // Re-highlight
        if (window.Prism) {
            Prism.highlightElement(codeEl);
        }

        // Show success feedback
        const originalHtml = button.innerHTML;
        button.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            <span>Formatted!</span>
        `;
        button.classList.add('btn-action--success');

        setTimeout(() => {
            button.innerHTML = originalHtml;
            button.classList.remove('btn-action--success');
        }, 2000);
    } catch (err) {
        console.error('Format failed:', err);
        Dialog.alert('Failed to format code: ' + err.message, { title: 'Format Error' });
    }
}

// Handle code download
function handleDownloadCode(button) {
    const codeblock = button.closest('.codeblock');
    if (!codeblock) return;

    const codeEl = codeblock.querySelector('pre code');
    const lang = codeblock.dataset.lang || 'txt';

    if (!codeEl) return;

    const code = codeEl.textContent;

    // Determine file extension
    const extMap = {
        'javascript': 'js',
        'typescript': 'ts',
        'python': 'py',
        'html': 'html',
        'css': 'css',
        'json': 'json',
        'yaml': 'yaml',
        'markdown': 'md',
        'bash': 'sh',
        'sql': 'sql',
    };

    const ext = extMap[lang.toLowerCase()] || lang || 'txt';
    const filename = `code-${Date.now()}.${ext}`;

    // Determine MIME type
    const mimeMap = {
        'js': 'text/javascript',
        'ts': 'text/typescript',
        'py': 'text/x-python',
        'html': 'text/html',
        'css': 'text/css',
        'json': 'application/json',
        'yaml': 'text/yaml',
        'md': 'text/markdown',
        'sh': 'text/x-sh',
        'sql': 'text/x-sql',
    };

    const mimeType = mimeMap[ext] || 'text/plain';

    // Download
    const blob = new Blob([code], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);

    // Show success feedback
    const originalHtml = button.innerHTML;
    button.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
        <span>Downloaded!</span>
    `;
    button.classList.add('btn-action--success');

    setTimeout(() => {
        button.innerHTML = originalHtml;
        button.classList.remove('btn-action--success');
    }, 2000);
}

// Handle code collapse/expand
function handleCollapseCode(button) {
    const codeblock = button.closest('.codeblock');
    if (!codeblock) return;

    const preEl = codeblock.querySelector('pre');
    if (!preEl) return;

    const isCollapsed = preEl.classList.contains('collapsed');

    if (isCollapsed) {
        preEl.classList.remove('collapsed');
        preEl.classList.add('expanded');
        button.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
            </svg>
            <span class="collapse-text">Collapse</span>
        `;
    } else {
        preEl.classList.add('collapsed');
        preEl.classList.remove('expanded');
        button.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
            <span class="collapse-text">Expand</span>
        `;
    }
}

// Handle save to snippets
function handleSaveSnippet(button) {
    const codeblock = button.closest('.codeblock');
    if (!codeblock) return;

    const codeEl = codeblock.querySelector('pre code');
    if (!codeEl) return;

    // Get raw code (not highlighted HTML)
    const code = codeEl.textContent;
    const lang = codeblock.dataset.lang || 'plaintext';

    // Get current date for default title
    const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
    const defaultTitle = `${lang} snippet ${today}`;

    // Get message metadata for source tracking
    const messageEl = button.closest('.message');
    const messageId = messageEl?.dataset.messageId || null;

    // Get current model info from toolbar
    const providerEl = document.getElementById('model-provider');
    const modelEl = document.getElementById('model-name');
    const provider = providerEl?.value || null;
    const model = modelEl?.value || null;

    // Show save snippet dialog
    openSaveSnippetDialog({
        code,
        language: lang,
        defaultTitle,
        sessionId: state.currentSession,
        messageId,
        provider,
        model
    });
}

// Open save snippet dialog
function openSaveSnippetDialog(options) {
    const { code, language, defaultTitle, sessionId, messageId, provider, model } = options;

    // Remove existing dialog if any
    const existingDialog = document.getElementById('saveSnippetDialog');
    if (existingDialog) {
        existingDialog.remove();
    }

    // Normalize language for Prism
    const prismLang = window.CodeBlockUtils?.normalizeLang(language) || language || 'plaintext';

    // Create dialog HTML
    const dialogHtml = `
        <div id="saveSnippetDialog" class="fixed inset-0 z-50 flex items-center justify-center">
            <!-- Backdrop -->
            <div class="absolute inset-0 bg-black bg-opacity-50" onclick="closeSaveSnippetDialog()"></div>

            <!-- Dialog -->
            <div class="relative bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden">
                <!-- Header -->
                <div class="px-6 py-4 border-b border-gray-200">
                    <div class="flex items-center justify-between">
                        <h3 class="text-lg font-semibold text-gray-900">Save to Snippets</h3>
                        <button
                            onclick="closeSaveSnippetDialog()"
                            class="p-1 hover:bg-gray-100 rounded-lg transition-colors"
                        >
                            <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                </div>

                <!-- Body -->
                <div class="px-6 py-4 overflow-y-auto max-h-[calc(90vh-200px)]">
                    <form id="saveSnippetForm" class="space-y-4">
                        <!-- Title -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Title <span class="text-red-500">*</span>
                            </label>
                            <input
                                type="text"
                                id="snippetTitle"
                                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                value="${escapeHtml(defaultTitle)}"
                                required
                            />
                        </div>

                        <!-- Language (readonly) -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Language
                            </label>
                            <input
                                type="text"
                                id="snippetLanguage"
                                class="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50"
                                value="${escapeHtml(language)}"
                                readonly
                            />
                        </div>

                        <!-- Tags -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Tags
                                <span class="text-xs text-gray-500 font-normal">(comma-separated)</span>
                            </label>
                            <input
                                type="text"
                                id="snippetTags"
                                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                placeholder="e.g. utility, helper, algorithm"
                            />
                        </div>

                        <!-- Summary -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Summary
                                <span class="text-xs text-gray-500 font-normal">(optional)</span>
                            </label>
                            <textarea
                                id="snippetSummary"
                                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                rows="3"
                                placeholder="Brief description of what this code does..."
                            ></textarea>
                        </div>

                        <!-- Code Preview -->
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Code Preview
                            </label>
                            <div class="border border-gray-300 rounded-lg overflow-hidden max-h-64">
                                <pre class="line-numbers language-${prismLang} !m-0" style="max-height: 16rem;"><code class="language-${prismLang}">${escapeHtml(code)}</code></pre>
                            </div>
                        </div>

                        <!-- Source Info -->
                        <div class="text-xs text-gray-500 bg-gray-50 p-3 rounded-lg">
                            <div class="font-medium mb-1">Source Information:</div>
                            <div>Session: ${escapeHtml(sessionId || 'N/A')}</div>
                            ${messageId ? `<div>Message: ${escapeHtml(messageId)}</div>` : ''}
                            ${model ? `<div>Model: ${escapeHtml(model)}</div>` : ''}
                        </div>
                    </form>
                </div>

                <!-- Footer -->
                <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
                    <button
                        type="button"
                        onclick="closeSaveSnippetDialog()"
                        class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        onclick="submitSaveSnippet()"
                        class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                    >
                        Save Snippet
                    </button>
                </div>
            </div>
        </div>
    `;

    // Add dialog to DOM
    document.body.insertAdjacentHTML('beforeend', dialogHtml);

    // Store snippet data for submission
    const dialog = document.getElementById('saveSnippetDialog');
    dialog._snippetData = {
        code,
        language,
        sessionId,
        messageId,
        provider,
        model
    };

    // Apply syntax highlighting to code preview
    if (window.Prism) {
        const codeEl = dialog.querySelector('pre code');
        if (codeEl) {
            window.Prism.highlightElement(codeEl);
        }
    }

    // Focus on title input
    document.getElementById('snippetTitle')?.focus();
}

// Close save snippet dialog
window.closeSaveSnippetDialog = function() {
    const dialog = document.getElementById('saveSnippetDialog');
    if (dialog) {
        dialog.remove();
    }
};

// Submit save snippet
window.submitSaveSnippet = async function() {
    const dialog = document.getElementById('saveSnippetDialog');
    if (!dialog || !dialog._snippetData) return;

    const { code, language, sessionId, messageId, model } = dialog._snippetData;

    // Get form values
    const title = document.getElementById('snippetTitle')?.value.trim();
    const tagsInput = document.getElementById('snippetTags')?.value.trim();
    const summary = document.getElementById('snippetSummary')?.value.trim();

    // Validate
    if (!title) {
        Dialog.alert('Please enter a title for the snippet', { title: 'Validation Error' });
        return;
    }

    // Parse tags
    const tags = tagsInput
        ? tagsInput.split(',').map(t => t.trim()).filter(t => t)
        : [];

    // Prepare request payload
    const payload = {
        title,
        language,
        code,
        tags,
        summary: summary || undefined,
        source: {
            type: 'chat',
            session_id: sessionId,
            message_id: messageId,
            model: model
        }
    };

    // Get button and store original text before try block
    const submitBtn = dialog.querySelector('button[onclick="submitSaveSnippet()"]');
    const originalText = submitBtn.textContent;

    try {
        // Show loading state
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving...';

        // Call API
        const response = await fetch('/api/snippets', withCsrfToken({
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        }));

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save snippet');
        }

        const result = await response.json();

        // Close dialog
        if (dialog) {
            dialog.remove();
        }

        // Show success message
        showToast('Snippet saved successfully!', 'success', 2000);

        console.log('Snippet saved:', result);
    } catch (err) {
        console.error('Failed to save snippet:', err);
        Dialog.alert('Failed to save snippet: ' + err.message, { title: 'Save Error' });

        // Restore button state
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
};

/**
 * Ensure codeblock has snippet_id (auto-save if needed)
 *
 * @param {HTMLElement} codeblockEl - Codeblock element
 * @returns {Promise<string|null>} snippet_id or null if failed
 */
async function ensureSnippetIdForCodeblock(codeblockEl) {
    // Check if already has snippet_id
    const existingId = codeblockEl.dataset.snippetId;
    if (existingId) {
        return existingId;
    }

    // Extract code and metadata
    const codeEl = codeblockEl.querySelector('pre code');
    if (!codeEl) return null;

    const code = codeEl.textContent;  // Raw code
    const language = codeblockEl.dataset.lang || '';
    const sessionId = codeblockEl.dataset.sessionId || state.currentSession;
    const messageId = codeblockEl.dataset.messageId || null;

    // Validate sessionId
    if (!sessionId) {
        console.error('No valid session ID for code block operations');
        return;
    }

    // Get current model
    const modelEl = document.getElementById('model-name');
    const model = modelEl?.value || 'claude-3-opus-20240229';

    // Auto-save with minimal metadata
    const now = new Date();
    const defaultTitle = `${language || 'code'} snippet ${now.toISOString().split('T')[0]}`;

    try {
        const response = await fetch('/api/snippets', withCsrfToken({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: defaultTitle,
                language: language || 'plaintext',
                code: code,
                tags: [],
                source: {
                    type: 'chat',
                    session_id: sessionId,
                    message_id: messageId,
                    model: model
                }
            })
        }));

        if (!response.ok) {
            throw new Error('Failed to save snippet');
        }

        const result = await response.json();
        const snippetId = result.id;

        // Write back to codeblock
        codeblockEl.dataset.snippetId = snippetId;

        console.log('Auto-saved snippet:', snippetId);
        return snippetId;

    } catch (err) {
        console.error('Failed to auto-save snippet:', err);
        showToast('Failed to save snippet', 'error', 3000);
        return null;
    }
}

// Handle preview snippet button
async function handlePreviewSnippet(button) {
    const codeblock = button.closest('.codeblock');
    if (!codeblock) return;

    // Ensure snippet_id exists
    const snippetId = await ensureSnippetIdForCodeblock(codeblock);
    if (!snippetId) return;

    // Detect preset (Auto)
    const language = codeblock.dataset.lang || '';
    const codeEl = codeblock.querySelector('pre code');
    const code = codeEl?.textContent || '';

    let preset = 'html-basic';  // Default

    // Auto-detect Three.js
    if (language === 'javascript' || language === 'js') {
        if (code.includes('THREE.') || code.includes('FontLoader') || code.includes('OrbitControls')) {
            preset = 'three-webgl-umd';
        }
    }

    // Show loading
    button.disabled = true;
    const originalHtml = button.innerHTML;
    button.innerHTML = '<span>Creating preview...</span>';

    try {
        // Call preview API
        const response = await fetch(`/api/snippets/${snippetId}/preview`, withCsrfToken({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preset })
        }));

        if (!response.ok) {
            throw new Error('Failed to create preview');
        }

        const data = await response.json();

        // Open preview dialog
        openPreviewDialog({
            url: data.url,
            preset: data.preset,
            deps: data.deps_injected || [],
            expiresAt: data.expires_at
        });

    } catch (err) {
        console.error('Preview failed:', err);
        showToast('Failed to create preview: ' + err.message, 'error', 3000);
    } finally {
        // Restore button
        button.disabled = false;
        button.innerHTML = originalHtml;
    }
}

// Handle make task button
async function handleMakeTask(button) {
    const codeblock = button.closest('.codeblock');
    if (!codeblock) return;

    // Ensure snippet_id exists
    const snippetId = await ensureSnippetIdForCodeblock(codeblock);
    if (!snippetId) return;

    // Prompt for target path
    const language = codeblock.dataset.lang || 'txt';
    const defaultPath = `examples/snippet_${Date.now()}.${language}`;

    const targetPath = await Dialog.prompt('Enter target file path (relative):', {
        title: 'Create Task',
        defaultValue: defaultPath,
        placeholder: 'examples/my_file.html'
    });
    if (!targetPath) return;

    // Show loading
    button.disabled = true;
    const originalHtml = button.innerHTML;
    button.innerHTML = '<span>Creating draft...</span>';

    try {
        // Call materialize API
        const response = await fetch(`/api/snippets/${snippetId}/materialize`, withCsrfToken({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_path: targetPath,
                description: `Write snippet to ${targetPath}`
            })
        }));

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to materialize');
        }

        const data = await response.json();

        // Show task draft dialog
        openTaskDraftDialog(data.task_draft);

        showToast('Task draft created', 'success', 2000);

    } catch (err) {
        console.error('Materialize failed:', err);
        showToast('Failed to create task: ' + err.message, 'error', 3000);
    } finally {
        // Restore button
        button.disabled = false;
        button.innerHTML = originalHtml;
    }
}

// Handle markdown copy
function handleMarkdownCopy(button) {
    const mdBlock = button.closest('.mdblock');
    if (!mdBlock) return;

    const mdContent = mdBlock.dataset.mdContent;
    if (!mdContent) return;

    navigator.clipboard.writeText(mdContent).then(() => {
        // Show success feedback
        const originalHtml = button.innerHTML;
        button.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
            <span>Copied!</span>
        `;
        button.classList.add('btn-md-copy--success');

        setTimeout(() => {
            button.innerHTML = originalHtml;
            button.classList.remove('btn-md-copy--success');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy markdown:', err);
        showToast('Failed to copy markdown', 'error', 2000);
    });
}

// Handle markdown download
function handleMarkdownDownload(button) {
    const mdBlock = button.closest('.mdblock');
    if (!mdBlock) return;

    const mdContent = mdBlock.dataset.mdContent;
    if (!mdContent) return;

    // Create filename with timestamp
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[:]/g, '-');
    const filename = `markdown-${timestamp}.md`;

    // Create blob and download
    const blob = new Blob([mdContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);

    showToast('Markdown downloaded', 'success', 2000);
}

// Handle markdown export to PDF
async function handleMarkdownExport(button) {
    const mdBlock = button.closest('.mdblock');
    if (!mdBlock) return;

    const mdContent = mdBlock.querySelector('.mdblock__content');
    if (!mdContent) return;

    // Show loading state
    button.disabled = true;
    const originalHtml = button.innerHTML;
    button.innerHTML = '<span>Exporting...</span>';

    try {
        // Use browser's print dialog with custom CSS for PDF export
        const printWindow = window.open('', '_blank');
        if (!printWindow) {
            throw new Error('Failed to open print window');
        }

        // Use modern DOM API instead of deprecated document.write
        const htmlContent = `
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Markdown Export</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                        line-height: 1.7;
                        max-width: 800px;
                        margin: 2rem auto;
                        padding: 2rem;
                        color: #24292f;
                    }
                    h1, h2, h3, h4, h5, h6 {
                        margin-top: 1.5rem;
                        margin-bottom: 0.75rem;
                        font-weight: 600;
                        line-height: 1.3;
                    }
                    h1 { font-size: 2rem; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }
                    h2 { font-size: 1.5rem; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.375rem; }
                    h3 { font-size: 1.25rem; }
                    ul, ol { padding-left: 1.5rem; margin-bottom: 1rem; }
                    li { margin-bottom: 0.375rem; }
                    code {
                        background-color: #f3f4f6;
                        color: #ef4444;
                        padding: 0.125rem 0.375rem;
                        border-radius: 0.25rem;
                        font-family: Monaco, Courier, monospace;
                        font-size: 0.875rem;
                    }
                    pre {
                        background-color: #f6f8fa;
                        padding: 1rem;
                        border-radius: 0.375rem;
                        overflow-x: auto;
                    }
                    pre code {
                        background-color: transparent;
                        color: inherit;
                        padding: 0;
                    }
                    blockquote {
                        margin: 1rem 0;
                        padding-left: 1rem;
                        border-left: 4px solid #e5e7eb;
                        color: #6b7280;
                    }
                    table {
                        width: 100%;
                        border-collapse: collapse;
                        margin: 1rem 0;
                    }
                    table th, table td {
                        border: 1px solid #e5e7eb;
                        padding: 0.5rem 0.75rem;
                        text-align: left;
                    }
                    table th {
                        background-color: #f9fafb;
                        font-weight: 600;
                    }
                    @media print {
                        body { margin: 0; padding: 1rem; }
                    }
                </style>
            </head>
            <body>
                ${mdContent.innerHTML}
            </body>
            </html>
        `;

        printWindow.document.open();
        printWindow.document.documentElement.innerHTML = htmlContent;
        printWindow.document.close();

        // Wait for content to load, then trigger print dialog
        printWindow.onload = () => {
            setTimeout(() => {
                printWindow.print();
                printWindow.close();
            }, 250);
        };

        showToast('Opening print dialog...', 'info', 2000);
    } catch (err) {
        console.error('Failed to export markdown:', err);
        showToast('Failed to export: ' + err.message, 'error', 3000);
    } finally {
        button.disabled = false;
        button.innerHTML = originalHtml;
    }
}

// Handle markdown print
function handleMarkdownPrint(button) {
    const mdBlock = button.closest('.mdblock');
    if (!mdBlock) return;

    const mdContent = mdBlock.querySelector('.mdblock__content');
    if (!mdContent) return;

    // Create temporary print window
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
        showToast('Failed to open print window', 'error', 2000);
        return;
    }

    // Use modern DOM API instead of deprecated document.write
    const htmlContent = `
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Print Markdown</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    line-height: 1.7;
                    max-width: 800px;
                    margin: 2rem auto;
                    padding: 2rem;
                    color: #24292f;
                }
                h1, h2, h3, h4, h5, h6 {
                    margin-top: 1.5rem;
                    margin-bottom: 0.75rem;
                    font-weight: 600;
                }
                @media print {
                    body { margin: 0; padding: 1rem; }
                }
            </style>
        </head>
        <body>
            ${mdContent.innerHTML}
        </body>
        </html>
    `;

    printWindow.document.open();
    printWindow.document.documentElement.innerHTML = htmlContent;
    printWindow.document.close();

    printWindow.onload = () => {
        setTimeout(() => {
            printWindow.print();
            printWindow.close();
        }, 250);
    };
}

// Open preview dialog
function openPreviewDialog({ url, preset, deps, expiresAt }) {
    // Remove existing dialog
    const existing = document.getElementById('previewDialog');
    if (existing) existing.remove();

    const expiresText = expiresAt
        ? new Date(expiresAt * 1000).toLocaleString()
        : 'N/A';

    const depsHtml = deps.length > 0
        ? `<details class="text-xs text-gray-600">
            <summary class="cursor-pointer hover:text-gray-800">Dependencies (${deps.length})</summary>
            <ul class="mt-2 ml-4 list-disc">${deps.map(d => `<li><code class="text-xs bg-gray-100 px-1 py-0.5 rounded">${escapeHtml(d)}</code></li>`).join('')}</ul>
           </details>`
        : '<p class="text-xs text-gray-600">No dependencies</p>';

    const dialogHtml = `
        <div id="previewDialog" class="fixed inset-0 z-50 flex items-center justify-center">
            <div class="absolute inset-0 bg-black bg-opacity-50" onclick="document.getElementById('previewDialog').remove()"></div>

            <div class="relative bg-white rounded-lg shadow-xl w-full max-w-4xl mx-4 max-h-[90vh] overflow-hidden">
                <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                    <div>
                        <h3 class="text-lg font-semibold">Preview</h3>
                        <div class="text-sm text-gray-600">
                            Preset: <code class="bg-gray-100 px-1 py-0.5 rounded">${escapeHtml(preset)}</code> | Expires: ${escapeHtml(expiresText)}
                        </div>
                    </div>
                    <button onclick="document.getElementById('previewDialog').remove()" class="p-1 hover:bg-gray-100 rounded-lg">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div class="px-6 py-2 bg-gray-50 border-b text-sm">
                    ${depsHtml}
                </div>

                <div class="p-0" style="height: calc(90vh - 180px);">
                    <iframe src="${escapeHtml(url)}" class="w-full h-full border-0"></iframe>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', dialogHtml);
}

// Open task draft dialog
function openTaskDraftDialog(draft) {
    // Remove existing dialog
    const existing = document.getElementById('taskDraftDialog');
    if (existing) existing.remove();

    const dialogHtml = `
        <div id="taskDraftDialog" class="fixed inset-0 z-50 flex items-center justify-center">
            <div class="absolute inset-0 bg-black bg-opacity-50" onclick="document.getElementById('taskDraftDialog').remove()"></div>

            <div class="relative bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden">
                <div class="px-6 py-4 border-b border-gray-200">
                    <h3 class="text-lg font-semibold">Task Draft Created</h3>
                </div>

                <div class="px-6 py-4 overflow-y-auto max-h-[calc(90vh-200px)]">
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700">Title</label>
                            <p class="text-sm text-gray-900">${escapeHtml(draft.title)}</p>
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700">Description</label>
                            <p class="text-sm text-gray-900">${escapeHtml(draft.description)}</p>
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700">Target Path</label>
                            <code class="text-sm bg-gray-100 px-2 py-1 rounded">${escapeHtml(draft.target_path)}</code>
                        </div>

                        <div>
                            <label class="block text-sm font-medium text-gray-700">Risk Level</label>
                            <span class="inline-block px-2 py-1 text-xs font-medium rounded ${
                                draft.risk_level === 'HIGH' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                            }">${escapeHtml(draft.risk_level)}</span>
                        </div>

                        ${draft.requires_admin_token ? '<div class="text-sm text-amber-600"><span class="material-icons md-18">warning</span> Requires admin token to execute</div>' : ''}

                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">Draft JSON</label>
                            <pre class="bg-gray-50 p-3 rounded text-xs overflow-x-auto">${escapeHtml(JSON.stringify(draft, null, 2))}</pre>
                        </div>
                    </div>
                </div>

                <div class="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
                    <button onclick="navigator.clipboard.writeText('${escapeHtml(JSON.stringify(draft))}'); showToast('Copied to clipboard', 'success', 2000);" class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50">
                        Copy JSON
                    </button>
                    <button onclick="document.getElementById('taskDraftDialog').remove()" class="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700">
                        Close
                    </button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', dialogHtml);
}

// Initialize HTML preview dialog
function ensurePreviewDialog() {
    const dlg = document.getElementById('htmlPreviewDlg');
    const btnClose = document.getElementById('htmlPreviewClose');
    const btnNewTab = document.getElementById('htmlPreviewNewTab');
    const btnFullscreen = document.getElementById('htmlPreviewFullscreen');
    const btnConsoleToggle = document.getElementById('htmlPreviewConsoleToggle');
    const btnEdit = document.getElementById('htmlPreviewEdit');
    const btnHistory = document.getElementById('htmlPreviewHistory');
    const btnShare = document.getElementById('htmlPreviewShare');
    const frame = document.getElementById('htmlPreviewFrame');
    const consolePanel = document.getElementById('htmlPreviewConsole');
    const consoleClear = document.getElementById('consoleClear');
    const dlgBody = document.querySelector('.preview-dlg__body');
    const historySidebar = document.getElementById('htmlPreviewHistorySidebar');
    const historyClose = document.getElementById('historyClose');
    const historyClearAll = document.getElementById('historyClearAll');

    if (!dlg || !btnClose || !frame) {
        console.warn('Preview dialog elements not found');
        return null;
    }

    // Ensure event listeners are only attached once
    if (!dlg.dataset.initialized) {
        // Store current HTML code
        dlg._currentHtmlCode = '';
        dlg._originalHtmlCode = '';

        // Close button
        btnClose.addEventListener('click', () => {
            dlg.close();
        });

        // New Tab button
        if (btnNewTab) {
            btnNewTab.addEventListener('click', () => {
                if (dlg._currentHtmlCode) {
                    openHtmlInNewTab(dlg._currentHtmlCode);
                }
            });
        }

        // Fullscreen button
        if (btnFullscreen) {
            btnFullscreen.addEventListener('click', () => {
                togglePreviewFullscreen(dlg);
            });
        }

        // Console Toggle button
        if (btnConsoleToggle && consolePanel) {
            btnConsoleToggle.addEventListener('click', () => {
                toggleConsolePanel(consolePanel, dlgBody);
            });
        }

        // Edit button
        if (btnEdit) {
            btnEdit.addEventListener('click', () => {
                toggleEditMode();
            });
        }

        // History button
        if (btnHistory) {
            btnHistory.addEventListener('click', () => {
                toggleHistorySidebar();
            });
        }

        // Share button
        if (btnShare) {
            btnShare.addEventListener('click', () => {
                sharePreview();
            });
        }

        // Console Clear button
        if (consoleClear) {
            consoleClear.addEventListener('click', () => {
                clearConsoleOutput();
            });
        }

        // History Close button
        if (historyClose) {
            historyClose.addEventListener('click', () => {
                toggleHistorySidebar();
            });
        }

        // History Clear All button
        if (historyClearAll) {
            historyClearAll.addEventListener('click', async () => {
                const confirmed = await Dialog.confirm('Clear all preview history?', {
                    title: 'Clear History',
                    confirmText: 'Clear',
                    danger: true
                });
                if (confirmed) {
                    PreviewHistory.clear();
                }
            });
        }

        // Editor tabs
        const editorTabs = document.querySelectorAll('.editor-tab');
        editorTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;
                switchEditorTab(tabName);
            });
        });

        // Editor Apply button
        const editorApply = document.getElementById('editorApply');
        if (editorApply) {
            editorApply.addEventListener('click', () => {
                applyEditorChanges();
            });
        }

        // Editor Reset button
        const editorReset = document.getElementById('editorReset');
        if (editorReset) {
            editorReset.addEventListener('click', () => {
                resetEditor();
            });
        }

        // Listen for console messages from iframe
        window.addEventListener('message', (e) => {
            if (e.data && e.data.type === 'console') {
                addConsoleMessage(e.data.method, e.data.args);
            }
        });

        // Click outside to close
        dlg.addEventListener('click', (e) => {
            const rect = dlg.getBoundingClientRect();
            const inDialog =
                rect.top <= e.clientY &&
                e.clientY <= rect.bottom &&
                rect.left <= e.clientX &&
                e.clientX <= rect.right;
            if (!inDialog) {
                dlg.close();
            }
        });

        // Escape key to close (or exit fullscreen)
        dlg.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                } else {
                    dlg.close();
                }
            }
        });

        // On close, reset state
        dlg.addEventListener('close', () => {
            clearConsoleOutput();
            if (document.fullscreenElement) {
                document.exitFullscreen();
            }

            // Hide editor and history
            const editor = document.getElementById('htmlPreviewEditor');
            if (editor) editor.style.display = 'none';

            if (historySidebar) historySidebar.style.display = 'none';
        });

        dlg.dataset.initialized = 'true';
    }

    return { dlg, frame };
}

// Open HTML preview in dialog
function openHtmlPreview(htmlCode) {
    const refs = ensurePreviewDialog();
    if (!refs) {
        Dialog.alert('Preview dialog not available. Please refresh the page.', { title: 'Preview Error' });
        return;
    }

    // Clear console before loading new preview
    clearConsoleOutput();

    // Inject console capture script
    const consoleScript = `
<script>
(function() {
    const original = {
        log: console.log,
        error: console.error,
        warn: console.warn,
        info: console.info
    };

    ['log', 'error', 'warn', 'info'].forEach(method => {
        console[method] = function(...args) {
            original[method].apply(console, args);
            window.parent.postMessage({
                type: 'console',
                method: method,
                args: args.map(arg => {
                    try {
                        return typeof arg === 'object' ? JSON.stringify(arg, null, 2) : String(arg);
                    } catch {
                        return '[Object]';
                    }
                })
            }, '*');
        };
    });
})();
</script>`;

    // Wrap HTML if it's not a complete document
    let wrapped = htmlCode.includes('<html')
        ? htmlCode
        : `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
body {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    padding: 20px;
    line-height: 1.6;
    color: #333;
}
* {
    box-sizing: border-box;
}
</style>
</head>
<body>
${htmlCode}
</body>
</html>`;

    // Inject console capture script before </body>
    wrapped = wrapped.replace('</body>', consoleScript + '</body>');

    // Store current HTML code
    refs.dlg._currentHtmlCode = wrapped;
    refs.dlg._originalHtmlCode = wrapped;

    // Add to history
    PreviewHistory.add(wrapped);

    // Use server endpoint instead of Blob URL to support external CDN
    // This allows iframe to have real origin and load Three.js, D3.js, etc.
    fetch('/api/preview', withCsrfToken({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html: wrapped })
    }))
    .then(res => res.json())
    .then(data => {
        // Delete previous session if exists
        if (refs.frame._previewSession) {
            fetch(`/api/preview/${refs.frame._previewSession}`, withCsrfToken({ method: 'DELETE' }));
        }

        // Load preview via server endpoint
        refs.frame.src = data.url;
        refs.frame._previewSession = data.session_id;
    })
    .catch(err => {
        console.error('Failed to create preview session:', err);
        Dialog.alert('Failed to load preview', { title: 'Preview Error' });
    });

    refs.dlg.showModal();
}

// Open HTML in new tab
function openHtmlInNewTab(htmlCode) {
    const blob = new Blob([htmlCode], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');

    // Release URL after 5 seconds to avoid memory leak
    setTimeout(() => URL.revokeObjectURL(url), 5000);
}

// Toggle preview fullscreen
function togglePreviewFullscreen(dlg) {
    if (!document.fullscreenElement) {
        dlg.requestFullscreen().catch(err => {
            console.error('Failed to enter fullscreen:', err);
        });
    } else {
        document.exitFullscreen();
    }
}

// Toggle console panel
function toggleConsolePanel(consolePanel, dlgBody) {
    if (!consolePanel) return;

    const isVisible = consolePanel.style.display !== 'none';

    if (isVisible) {
        consolePanel.style.display = 'none';
        if (dlgBody) {
            dlgBody.classList.remove('console-visible');
        }
    } else {
        consolePanel.style.display = 'flex';
        if (dlgBody) {
            dlgBody.classList.add('console-visible');
        }
    }
}

// Clear console output
function clearConsoleOutput() {
    const consoleOutput = document.getElementById('consoleOutput');
    if (consoleOutput) {
        consoleOutput.innerHTML = '<div class="console-empty">Console is ready. Messages will appear here.</div>';
    }
}

// Add console message
function addConsoleMessage(method, args) {
    const consoleOutput = document.getElementById('consoleOutput');
    if (!consoleOutput) return;

    // Remove empty message if present
    const emptyMsg = consoleOutput.querySelector('.console-empty');
    if (emptyMsg) {
        emptyMsg.remove();
    }

    // Create message element
    const messageEl = document.createElement('div');
    messageEl.className = `console-message ${method}`;

    const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });

    messageEl.innerHTML = `
        <span class="console-time">${time}</span>
        <span class="console-type">${method}</span>
        ${args.join(' ')}
    `;

    consoleOutput.appendChild(messageEl);

    // Auto-scroll to bottom
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

// ========================================
// Phase 4: Advanced Features
// ========================================

// Apply Prism theme
function applyPrismTheme(theme) {
    const themeLink = document.getElementById('prism-theme');
    if (!themeLink) return;

    const themeUrls = {
        'tomorrow': '/static/vendor/prismjs/themes/prism-tomorrow.min.css',
        'okaidia': '/static/vendor/prismjs/themes/prism-okaidia.min.css',
        'dracula': '/static/vendor/prismjs/themes/prism-dracula.min.css',
        'one-dark': '/static/vendor/prismjs/themes/prism-one-dark.min.css',
        'solarized-dark': '/static/vendor/prismjs/themes/prism-solarizedlight.min.css',
        'monokai': '/static/vendor/prismjs/themes/prism-okaidia.min.css' // Using Okaidia as Monokai alternative
    };

    themeLink.href = themeUrls[theme] || themeUrls['tomorrow'];

    // Re-highlight all code blocks
    if (window.Prism) {
        Prism.highlightAll();
    }
}

// Toggle edit mode
function toggleEditMode() {
    const dlg = document.getElementById('htmlPreviewDlg');
    const editor = document.getElementById('htmlPreviewEditor');
    const body = document.querySelector('.preview-dlg__body');

    if (!dlg || !editor || !body) return;

    const isEditMode = editor.style.display !== 'none';

    if (isEditMode) {
        // Exit edit mode
        editor.style.display = 'none';
    } else {
        // Enter edit mode
        editor.style.display = 'flex';

        // Load current HTML into editor
        const htmlCode = dlg._currentHtmlCode || '';

        // Extract HTML, CSS, JS from combined code
        const extracted = extractHtmlCssJs(htmlCode);
        document.getElementById('editorHtml').value = extracted.html;
        document.getElementById('editorCss').value = extracted.css;
        document.getElementById('editorJs').value = extracted.js;
    }
}

// Extract HTML, CSS, JS from combined code
function extractHtmlCssJs(htmlCode) {
    const result = { html: '', css: '', js: '' };

    // Extract CSS from <style> tags
    const styleRegex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
    let styleMatch;
    let cssContent = '';
    while ((styleMatch = styleRegex.exec(htmlCode)) !== null) {
        cssContent += styleMatch[1] + '\n';
    }
    result.css = cssContent.trim();

    // Extract JS from <script> tags (excluding console capture script)
    const scriptRegex = /<script[^>]*>([\s\S]*?)<\/script>/gi;
    let scriptMatch;
    let jsContent = '';
    while ((scriptMatch = scriptRegex.exec(htmlCode)) !== null) {
        const script = scriptMatch[1];
        // Skip console capture script
        if (!script.includes('window.parent.postMessage')) {
            jsContent += script + '\n';
        }
    }
    result.js = jsContent.trim();

    // Remove style and script tags from HTML
    let bodyContent = htmlCode.replace(styleRegex, '').replace(scriptRegex, '');

    // Extract content between <body> tags if present
    const bodyRegex = /<body[^>]*>([\s\S]*?)<\/body>/i;
    const bodyMatch = bodyContent.match(bodyRegex);
    if (bodyMatch) {
        result.html = bodyMatch[1].trim();
    } else {
        // If no body tags, use the whole content minus head
        const headRegex = /<head[^>]*>[\s\S]*?<\/head>/i;
        bodyContent = bodyContent.replace(headRegex, '');
        bodyContent = bodyContent.replace(/<!doctype[^>]*>/i, '');
        bodyContent = bodyContent.replace(/<\/?html[^>]*>/gi, '');
        bodyContent = bodyContent.replace(/<\/?head[^>]*>/gi, '');
        bodyContent = bodyContent.replace(/<\/?body[^>]*>/gi, '');
        result.html = bodyContent.trim();
    }

    return result;
}

// Apply editor changes
function applyEditorChanges() {
    const html = document.getElementById('editorHtml').value;
    const css = document.getElementById('editorCss').value;
    const js = document.getElementById('editorJs').value;

    // Combine into full HTML
    const combined = `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
body {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    padding: 20px;
    line-height: 1.6;
    color: #333;
}
* {
    box-sizing: border-box;
}
${css}
</style>
</head>
<body>
${html}
<script>
${js}
</script>
</body>
</html>`;

    // Update preview
    const refs = ensurePreviewDialog();
    if (refs) {
        refs.dlg._currentHtmlCode = combined;

        // Use server endpoint to support external CDN
        fetch('/api/preview', withCsrfToken({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ html: combined })
        }))
        .then(res => res.json())
        .then(data => {
            // Delete previous session if exists
            if (refs.frame._previewSession) {
                fetch(`/api/preview/${refs.frame._previewSession}`, withCsrfToken({ method: 'DELETE' }));
            }

            // Load updated preview
            refs.frame.src = data.url;
            refs.frame._previewSession = data.session_id;
        })
        .catch(err => {
            console.error('Failed to update preview:', err);
        });
    }
}

// Reset editor to original code
function resetEditor() {
    const dlg = document.getElementById('htmlPreviewDlg');
    if (!dlg) return;

    const htmlCode = dlg._originalHtmlCode || dlg._currentHtmlCode || '';
    const extracted = extractHtmlCssJs(htmlCode);

    document.getElementById('editorHtml').value = extracted.html;
    document.getElementById('editorCss').value = extracted.css;
    document.getElementById('editorJs').value = extracted.js;

    // Apply changes
    applyEditorChanges();
}

// Switch editor tab
function switchEditorTab(tab) {
    const tabs = ['html', 'css', 'js'];
    tabs.forEach(t => {
        const tabBtn = document.querySelector(`.editor-tab[data-tab="${t}"]`);
        const textarea = document.getElementById(`editor${t.charAt(0).toUpperCase() + t.slice(1)}`);

        if (t === tab) {
            tabBtn?.classList.add('active');
            if (textarea) textarea.style.display = 'block';
        } else {
            tabBtn?.classList.remove('active');
            if (textarea) textarea.style.display = 'none';
        }
    });
}

// Preview History Management
const PreviewHistory = {
    MAX_ITEMS: 10,
    STORAGE_KEY: 'agentos_preview_history',

    load() {
        try {
            const data = localStorage.getItem(this.STORAGE_KEY);
            return data ? JSON.parse(data) : [];
        } catch {
            return [];
        }
    },

    save(items) {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(items));
        } catch (err) {
            console.error('Failed to save history:', err);
        }
    },

    add(code) {
        const items = this.load();

        // Create new item
        const item = {
            id: Date.now(),
            timestamp: new Date().toISOString(),
            code: code,
            title: this.extractTitle(code),
            preview: code.slice(0, 100)
        };

        // Add to beginning
        items.unshift(item);

        // Keep only MAX_ITEMS
        if (items.length > this.MAX_ITEMS) {
            items.splice(this.MAX_ITEMS);
        }

        this.save(items);
        this.render();
    },

    extractTitle(code) {
        // Try to extract title from <title> tag
        const titleMatch = code.match(/<title[^>]*>(.*?)<\/title>/i);
        if (titleMatch && titleMatch[1].trim()) {
            return titleMatch[1].trim();
        }

        // Try to extract from first <h1>
        const h1Match = code.match(/<h1[^>]*>(.*?)<\/h1>/i);
        if (h1Match && h1Match[1].trim()) {
            return h1Match[1].replace(/<[^>]*>/g, '').trim();
        }

        // Default
        return 'Untitled Preview';
    },

    delete(id) {
        const items = this.load().filter(item => item.id !== id);
        this.save(items);
        this.render();
    },

    clear() {
        this.save([]);
        this.render();
    },

    open(id) {
        const items = this.load();
        const item = items.find(i => i.id === id);
        if (item) {
            openHtmlPreview(item.code);
        }
    },

    render() {
        const listEl = document.getElementById('historyList');
        if (!listEl) return;

        const items = this.load();

        if (items.length === 0) {
            listEl.innerHTML = '<div class="history-empty">No preview history yet</div>';
            return;
        }

        listEl.innerHTML = items.map(item => {
            const date = new Date(item.timestamp);
            const timeStr = date.toLocaleString();

            return `
                <div class="history-item" data-id="${item.id}">
                    <div class="history-item-title">${this.escapeHtml(item.title)}</div>
                    <div class="history-item-time">${timeStr}</div>
                    <div class="history-item-preview">${this.escapeHtml(item.preview)}</div>
                    <button class="history-item-delete" data-id="${item.id}" title="Delete">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            `;
        }).join('');

        // Add click handlers
        listEl.querySelectorAll('.history-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.history-item-delete')) {
                    const id = parseInt(item.dataset.id);
                    this.open(id);
                }
            });
        });

        listEl.querySelectorAll('.history-item-delete').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = parseInt(btn.dataset.id);
                this.delete(id);
            });
        });
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Toggle history sidebar
function toggleHistorySidebar() {
    const sidebar = document.getElementById('htmlPreviewHistorySidebar');
    if (!sidebar) return;

    const isVisible = sidebar.style.display !== 'none';

    if (isVisible) {
        sidebar.style.display = 'none';
    } else {
        sidebar.style.display = 'flex';
        PreviewHistory.render();
    }
}

// Share preview (generate shareable link)
async function sharePreview() {
    const dlg = document.getElementById('htmlPreviewDlg');
    if (!dlg || !dlg._currentHtmlCode) {
        Dialog.alert('No preview to share', { title: 'Share Error' });
        return;
    }

    const code = dlg._currentHtmlCode;

    try {
        const response = await fetch('/api/share', withCsrfToken({
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ code })
        }));

        if (!response.ok) {
            throw new Error('Failed to create share link');
        }

        const data = await response.json();
        const shareUrl = `${window.location.origin}/share/${data.id}`;

        // Copy to clipboard
        await navigator.clipboard.writeText(shareUrl);

        // Show success message
        Dialog.alert(`Share link copied to clipboard:\n${shareUrl}`, { title: 'Share Success' });
    } catch (err) {
        console.error('Share failed:', err);
        Dialog.alert('Failed to create share link. Feature may not be available.', { title: 'Share Error' });
    }
}

// Apply syntax highlighting to code blocks
function highlightCodeBlocks(element) {
    if (!window.Prism) {
        console.warn('PrismJS not loaded, skipping syntax highlighting');
        return;
    }

    try {
        // Highlight all code blocks within the element
        Prism.highlightAllUnder(element);
        console.log('Syntax highlighting applied to code blocks');
    } catch (err) {
        console.error('Failed to apply syntax highlighting:', err);
    }
}

// ============================================================================
// ============================================================================
// Message Queue - Prevents concurrent message processing (H-8 Fix)
// ============================================================================
class MessageQueue {
  constructor() {
    this.queue = [];
    this.processing = false;
  }

  /**
   * Add message to queue and process
   * @param {Object} message - Message to send
   * @returns {Promise<boolean>} Success status
   */
  async enqueue(message) {
    console.log('[MessageQueue] Enqueuing message, queue length:', this.queue.length);

    return new Promise((resolve) => {
      this.queue.push({ message, resolve });

      // Start processing if not already processing
      if (!this.processing) {
        this.processQueue();
      }
    });
  }

  /**
   * Process messages in queue sequentially
   */
  async processQueue() {
    if (this.processing) {
      console.log('[MessageQueue] Already processing');
      return;
    }

    this.processing = true;
    this.updateUIState(true);

    console.log('[MessageQueue] Starting queue processing, items:', this.queue.length);

    while (this.queue.length > 0) {
      const { message, resolve } = this.queue.shift();

      console.log('[MessageQueue] Processing message, remaining:', this.queue.length);

      try {
        // Send message via WebSocket
        const success = await this.sendAndWait(message);
        resolve(success);
      } catch (err) {
        console.error('[MessageQueue] Error processing message:', err);
        resolve(false);
      }
    }

    this.processing = false;
    this.updateUIState(false);

    console.log('[MessageQueue] Queue processing complete');
  }

  /**
   * Send message and wait for response
   * @param {Object} message - Message to send
   * @returns {Promise<boolean>} Success status
   */
  async sendAndWait(message) {
    return new Promise((resolve) => {
      // Set up one-time listener for message.end or error
      const messageId = Date.now().toString();
      let responseReceived = false;

      const timeout = setTimeout(() => {
        if (!responseReceived) {
          console.warn('[MessageQueue] Response timeout for message');
          cleanup();
          resolve(false);
        }
      }, 60000); // 60 second timeout

      const cleanup = () => {
        clearTimeout(timeout);
        window.removeEventListener('ws:message:end', onMessageEnd);
        window.removeEventListener('ws:message:error', onMessageError);
      };

      const onMessageEnd = (event) => {
        responseReceived = true;
        cleanup();
        console.log('[MessageQueue] Message completed successfully');
        resolve(true);
      };

      const onMessageError = (event) => {
        responseReceived = true;
        cleanup();
        console.warn('[MessageQueue] Message completed with error');
        resolve(true); // Still resolve to process next message
      };

      // Listen for completion events
      window.addEventListener('ws:message:end', onMessageEnd, { once: true });
      window.addEventListener('ws:message:error', onMessageError, { once: true });

      // Send the message
      const sent = WS.send(message);

      if (!sent) {
        cleanup();
        resolve(false);
      }
    });
  }

  /**
   * Update UI state (disable/enable send button, show indicator)
   * @param {boolean} processing - Whether processing is active
   */
  updateUIState(processing) {
    const sendBtn = document.getElementById('send-btn');
    const input = document.getElementById('chat-input');

    if (sendBtn) {
      sendBtn.disabled = processing;

      if (processing) {
        sendBtn.classList.add('processing');
        sendBtn.title = 'Processing message...';
      } else {
        sendBtn.classList.remove('processing');
        sendBtn.title = 'Send message';
      }
    }

    if (input) {
      input.disabled = processing;
    }

    // Show/hide processing indicator
    this.updateProcessingIndicator(processing);
  }

  /**
   * Show/hide processing indicator in chat
   * @param {boolean} show - Whether to show indicator
   */
  updateProcessingIndicator(show) {
    let indicator = document.getElementById('chat-processing-indicator');

    if (show && !indicator) {
      // Create indicator
      indicator = document.createElement('div');
      indicator.id = 'chat-processing-indicator';
      indicator.className = 'chat-processing-indicator';
      indicator.innerHTML = `
        <div class="processing-spinner"></div>
        <span>Processing message...</span>
      `;

      const messagesDiv = document.getElementById('messages');
      if (messagesDiv) {
        messagesDiv.parentNode.insertBefore(indicator, messagesDiv.nextSibling);
      }
    } else if (!show && indicator) {
      // Remove indicator
      indicator.remove();
    }
  }

  /**
   * Clear queue (for session change or reset)
   */
  clear() {
    console.log('[MessageQueue] Clearing queue, items:', this.queue.length);
    this.queue = [];
    this.processing = false;
    this.updateUIState(false);
  }
}

// Global message queue instance
const messageQueue = new MessageQueue();

// WebSocket Manager - Singleton with reconnection, heartbeat, lifecycle
// ============================================================================
const WS = {
  ws: null,
  url: null,
  reconnectTimer: null,
  heartbeatTimer: null,
  pongTimer: null,
  reconnectDelay: 1000,
  maxReconnectDelay: 30000,
  heartbeatInterval: 30000,
  pongTimeout: 60000,
  manualClose: false,
  connecting: false,
  lastActivity: Date.now(),

  connect(sessionId = state.currentSession) {
    console.log('[WS] connect() called, sessionId:', sessionId);

    if (this.connecting) {
      console.log('[WS] Already connecting, skipping...');
      return;
    }

    this.manualClose = false;
    this.connecting = true;

    // Close existing connection
    if (this.ws) {
      console.log('[WS] Closing existing connection...');
      this.ws.onclose = null; // Prevent reconnect
      this.ws.close();
      this.ws = null;
    }

    // Clear timers
    this._clearTimers();

    // Build URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.url = `${protocol}//${window.location.host}/ws/chat/${sessionId}`;

    console.log('[WS] Connecting to:', this.url);
    updateChatWSStatus('connecting', 'Connecting...');

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('[WS] Connected successfully');
        this.connecting = false;
        this.reconnectDelay = 1000; // Reset backoff
        updateChatWSStatus('connected', 'Connected');
        this._startHeartbeat();
        this.lastActivity = Date.now();
      };

      this.ws.onmessage = (event) => {
        this.lastActivity = Date.now();

        try {
          const data = JSON.parse(event.data);

          // Handle pong (JSON format from backend: {"type": "pong", "ts": "..."})
          if (data.type === 'pong') {
            console.log('[WS] Received pong');
            this._clearPongTimer();
            return;
          }

          // Pass to handleIncomingChatMessage
          handleIncomingChatMessage(data);

        } catch (err) {
          console.warn('[WS] Message parse error (invalid JSON from server):', err);
          // Don't show to user - this is a technical error that should be fixed on backend
        }
      };

      this.ws.onerror = (error) => {
        console.error('[WS] Error:', error);
        this.connecting = false;
        updateChatWSStatus('disconnected', 'Connection Error');
      };

      this.ws.onclose = (event) => {
        console.log('[WS] Closed, code:', event.code, 'reason:', event.reason, 'manualClose:', this.manualClose);
        this.connecting = false;
        this.ws = null;
        this._clearTimers();
        updateChatWSStatus('disconnected', 'Disconnected');

        // Task #7: Clear message states on disconnect to prevent stale state on reconnect
        console.log('[WS] Clearing message states on disconnect:', messageStates.size, 'entries');
        messageStates.clear();

        // Auto-reconnect unless manually closed
        if (!this.manualClose) {
          console.log('[WS] Scheduling reconnect in', this.reconnectDelay, 'ms');
          this.reconnectTimer = setTimeout(() => {
            console.log('[WS] Reconnecting...');
            this.connect(sessionId);
          }, this.reconnectDelay);

          // Exponential backoff
          this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
        }
      };

      // Update state reference
      state.websocket = this.ws;

    } catch (err) {
      console.error('[WS] Connect error:', err);
      this.connecting = false;
      updateChatWSStatus('disconnected', 'Failed to connect');
    }
  },

  close() {
    console.log('[WS] Manual close');
    this.manualClose = true;
    this._clearTimers();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    state.websocket = null;
  },

  send(data) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error('[WS] Not connected, readyState:', this.ws?.readyState);

      // Trigger reconnect
      console.log('[WS] Attempting reconnect...');
      this.connect();

      Dialog.alert('WebSocket disconnected. Reconnecting...', { title: 'Connection Lost' });
      return false;
    }

    try {
      const payload = typeof data === 'string' ? data : JSON.stringify(data);
      this.ws.send(payload);
      this.lastActivity = Date.now();
      return true;
    } catch (err) {
      console.error('[WS] Send error:', err);
      return false;
    }
  },

  _startHeartbeat() {
    this._clearHeartbeatTimer();

    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        const idle = Date.now() - this.lastActivity;

        if (idle > this.heartbeatInterval) {
          console.log('[WS] Sending ping (idle:', idle, 'ms)');

          try {
            this.ws.send('ping');

            // Set pong timeout
            this.pongTimer = setTimeout(() => {
              console.warn('[WS] Pong timeout, closing connection');
              this.ws.close();
            }, this.pongTimeout);

          } catch (err) {
            console.error('[WS] Ping error:', err);
          }
        }
      }
    }, this.heartbeatInterval);
  },

  _clearHeartbeatTimer() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  },

  _clearPongTimer() {
    if (this.pongTimer) {
      clearTimeout(this.pongTimer);
      this.pongTimer = null;
    }
  },

  _clearTimers() {
    this._clearHeartbeatTimer();
    this._clearPongTimer();

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
};

// Adapter for existing handleWebSocketMessage
function handleIncomingChatMessage(data) {
  handleWebSocketMessage(data);
}

// Lifecycle hooks for Safari bfcache and visibility
let lifecycleHooksInstalled = false;

function setupWebSocketLifecycle() {
  // Prevent duplicate event listener registration
  if (lifecycleHooksInstalled) {
    console.log('[Lifecycle] Hooks already installed, skipping');
    return;
  }

  console.log('[Lifecycle] Setting up WebSocket lifecycle hooks');
  lifecycleHooksInstalled = true;

  // Safari bfcache: restore connection on pageshow.persisted
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) {
      console.log('[Lifecycle] Page restored from bfcache, reconnecting WebSocket');
      // Only reconnect if on chat view
      if (state.currentView === 'chat') {
        WS.connect();
      }
    }
  });

  // Visibility API: reconnect when page becomes visible
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      console.log('[Lifecycle] Page visible, checking WebSocket');

      // Only reconnect if on chat view
      if (state.currentView === 'chat' && (!WS.ws || WS.ws.readyState !== WebSocket.OPEN)) {
        console.log('[Lifecycle] WebSocket not open, reconnecting');
        WS.connect();
      }
    }
  });

  // Focus event: reconnect on window focus
  window.addEventListener('focus', () => {
    console.log('[Lifecycle] Window focused, checking WebSocket');

    // Only reconnect if on chat view
    if (state.currentView === 'chat' && (!WS.ws || WS.ws.readyState !== WebSocket.OPEN)) {
      console.log('[Lifecycle] WebSocket not open, reconnecting');
      WS.connect();
    }
  });
}

// Debug helpers
window.wsDebug = () => {
  console.log('[WS Debug]', {
    connected: WS.ws?.readyState === WebSocket.OPEN,
    readyState: WS.ws?.readyState,
    url: WS.url,
    reconnectDelay: WS.reconnectDelay,
    manualClose: WS.manualClose,
    connecting: WS.connecting,
    lastActivity: new Date(WS.lastActivity).toISOString(),
    idleTime: Date.now() - WS.lastActivity,
    lifecycleHooksInstalled: lifecycleHooksInstalled,
    currentView: state.currentView,
    messagesProcessed: processedMessages.size
  });
};

window.wsReconnect = () => {
  console.log('[WS] Manual reconnect triggered');
  WS.connect();
};

// Clear processed messages tracking (useful for debugging)
window.wsClearTracking = () => {
  const count = processedMessages.size;
  processedMessages.clear();
  console.log(`[WS] Cleared ${count} tracked messages`);
};

// Setup WebSocket
function setupWebSocket() {
    console.log('[WS] setupWebSocket() called, delegating to WS.connect()');
    WS.connect(state.currentSession);
}

// Task #7: Enhanced message state tracking for deduplication
// Track full message lifecycle: start -> deltas -> end
const messageStates = new Map();  // message_id -> {state, seq, lastUpdateTime}
const MESSAGE_TRACKING_LIMIT = 100; // Keep last 100 message IDs

// Clean up old message states periodically
function cleanupMessageStates() {
    if (messageStates.size > MESSAGE_TRACKING_LIMIT) {
        const now = Date.now();
        const staleThreshold = 5 * 60 * 1000; // 5 minutes

        // Remove stale entries
        for (const [msgId, state] of messageStates.entries()) {
            if (now - state.lastUpdateTime > staleThreshold) {
                messageStates.delete(msgId);
            }
        }

        // If still over limit, remove oldest entries
        if (messageStates.size > MESSAGE_TRACKING_LIMIT) {
            const sorted = Array.from(messageStates.entries())
                .sort((a, b) => a[1].lastUpdateTime - b[1].lastUpdateTime);
            const toRemove = sorted.slice(0, messageStates.size - MESSAGE_TRACKING_LIMIT);
            toRemove.forEach(([msgId]) => messageStates.delete(msgId));
        }
    }
}

// Handle WebSocket message
function handleWebSocketMessage(message) {
    const messagesDiv = document.getElementById('messages');

    // If messages div doesn't exist (not on chat view), only log and return
    if (!messagesDiv) {
        console.log('[WS] Message received but not on chat view, ignoring UI update:', message.type);
        return;
    }

    // Task #7: Enhanced message deduplication with full lifecycle tracking
    if (message.type === 'message.start') {
        // Check for duplicate message.start
        if (message.message_id && messageStates.has(message.message_id)) {
            const state = messageStates.get(message.message_id);
            if (state.state !== 'ended') {
                console.warn('[WS] Duplicate message.start detected, skipping:', message.message_id, 'current state:', state.state);
                return;
            }
            // If message was ended, allow reuse of message_id (rare case)
            console.log('[WS] Reusing message_id after previous completion:', message.message_id);
        }

        // Create new assistant message element (empty, will be filled by deltas)
        // Pass metadata for extension detection (Task #11)
        const assistantMsg = createMessageElement('assistant', '', message.metadata || {});
        assistantMsg.dataset.messageId = message.message_id;
        messagesDiv.appendChild(assistantMsg);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        console.log('[WS] Started receiving message:', message.message_id, 'seq:', message.seq || 0);

        // Track this message with full state
        if (message.message_id) {
            messageStates.set(message.message_id, {
                state: 'streaming',
                seq: message.seq || 0,
                lastUpdateTime: Date.now(),
                chunkCount: 0
            });
            cleanupMessageStates();
        }

    } else if (message.type === 'message.delta') {
        // Task #7: Deduplicate deltas using sequence numbers
        const state = messageStates.get(message.message_id);
        if (!state) {
            console.warn('[WS] Received delta without start, skipping:', message.message_id);
            return;
        }

        // Check sequence number if provided by backend
        if (message.seq !== undefined && message.seq !== null) {
            if (message.seq <= state.seq) {
                console.warn('[WS] Duplicate or out-of-order delta detected, skipping:',
                    'msg_id:', message.message_id, 'received seq:', message.seq, 'current seq:', state.seq);
                return;
            }
            state.seq = message.seq;
        } else {
            // Backend doesn't provide seq, increment locally
            state.seq += 1;
        }

        state.lastUpdateTime = Date.now();
        state.chunkCount += 1;

        // Append content to the last assistant message
        let lastMsg = messagesDiv.lastElementChild;
        if (lastMsg && lastMsg.classList.contains('assistant')) {
            const contentDiv = lastMsg.querySelector('.content');
            contentDiv.textContent += message.content;
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        } else {
            console.warn('[WS] Received delta but no assistant message element found');
        }

    } else if (message.type === 'message.end') {
        // Task #7: Deduplicate message.end
        const state = messageStates.get(message.message_id);
        if (!state) {
            console.warn('[WS] Received end without start, skipping:', message.message_id);
            return;
        }

        if (state.state === 'ended') {
            console.warn('[WS] Duplicate message.end detected, skipping:', message.message_id);
            return;
        }

        // Mark as ended
        state.state = 'ended';
        state.lastUpdateTime = Date.now();

        console.log('[WS] Finished receiving message:', message.message_id,
            'chunks:', state.chunkCount, 'metadata:', message.metadata);

        // Find the message element and rerender with code block parsing
        const msgEl = messagesDiv.querySelector(`[data-message-id="${message.message_id}"]`);
        if (msgEl && msgEl.classList.contains('assistant')) {
            const contentDiv = msgEl.querySelector('.content');
            if (contentDiv) {
                const fullText = contentDiv.textContent;

                // Rerender with code block parsing using CodeBlockUtils
                if (window.CodeBlockUtils && window.CodeBlockUtils.renderAssistantMessage) {
                    contentDiv.innerHTML = window.CodeBlockUtils.renderAssistantMessage(fullText);

                    // Apply syntax highlighting
                    highlightCodeBlocks(contentDiv);
                }
            }

            // Task #5: Check for external_info declarations
            if (message.external_info && Array.isArray(message.external_info) && message.external_info.length > 0) {
                console.log('External info declarations detected:', message.external_info);
                displayExternalInfoWarning(msgEl, message.external_info);
            }
        }

        // H-8 Fix: Dispatch event to notify MessageQueue
        window.dispatchEvent(new CustomEvent('ws:message:end', { detail: message }));

    } else if (message.type === 'message.error') {
        // Show error message
        const errorMsg = createMessageElement('assistant', message.content, message.metadata || {});
        errorMsg.classList.add('error');
        messagesDiv.appendChild(errorMsg);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        console.error('Message error:', message.content);

        // H-8 Fix: Dispatch event to notify MessageQueue
        window.dispatchEvent(new CustomEvent('ws:message:error', { detail: message }));

    } else if (message.type === 'completion_info') {
        // P1-8: Handle completion truncation info
        console.log('Completion info:', message.info);
        if (message.info && message.info.truncated) {
            displayCompletionHint(messagesDiv);
        }

    } else if (message.type === 'budget_update') {
        // NEW: Handle budget update
        console.log('Budget update:', message.data);
        updateBudgetIndicator(message.data);

    } else if (message.type === 'event') {
        // Handle events
        console.log('Event:', message);

    } else if (message.type === 'error') {
        // Filter out technical errors that users don't need to see
        const technicalErrors = ['Invalid JSON', 'invalid json'];
        const shouldSkip = technicalErrors.some(err =>
            message.content && message.content.toLowerCase().includes(err.toLowerCase())
        );

        if (shouldSkip) {
            console.warn('WebSocket technical error (filtered from UI):', message.content);
            return;
        }

        // Show error
        const errorMsg = createMessageElement('event', `Error: ${message.content}`);
        messagesDiv.appendChild(errorMsg);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        console.error('WebSocket error:', message.content);

    } else {
        console.warn('Unknown message type:', message.type);
    }
}

// Send message
async function sendMessage() {
    const input = document.getElementById('chat-input');
    const content = input.value.trim();

    if (!content) return;

    // Quick health check before sending (lightweight, non-blocking)
    // This provides early feedback if chat is not available
    const health = await checkChatHealth();
    if (!health.is_healthy) {
        console.warn('Chat health check failed before sending message:', health);

        // Show toast notification
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #dc3545;
            color: white;
            padding: 12px 20px;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            z-index: 9999;
            font-size: 14px;
            max-width: 400px;
        `;
        toast.innerHTML = `
            <strong>Cannot send message</strong><br>
            ${health.issues.join(', ')}
        `;
        document.body.appendChild(toast);

        // Auto-remove toast after 3 seconds
        setTimeout(() => toast.remove(), 3000);

        // Show warning banner if not already visible
        if (!document.getElementById('chat-health-warning')) {
            showChatHealthWarning(health.issues || [], health.hints || []);
        }

        return; // Prevent sending
    }

    // Get current provider and model selection
    const providerEl = document.getElementById('model-provider');
    const modelEl = document.getElementById('model-name');
    const modelTypeEl = document.getElementById('model-type');

    const metadata = {};

    if (modelTypeEl && modelTypeEl.value) {
        metadata.model_type = modelTypeEl.value;
    }

    if (providerEl && providerEl.value) {
        metadata.provider = providerEl.value;
    }

    if (modelEl && modelEl.value) {
        metadata.model = modelEl.value;
    }

    console.log('Sending message with metadata:', metadata);

    // Add user message to UI
    const messagesDiv = document.getElementById('messages');
    const userMsg = createMessageElement('user', content);
    messagesDiv.appendChild(userMsg);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;

    // Clear input immediately for better UX
    input.value = '';

    // Send via message queue (H-8 Fix: prevents concurrent processing)
    const sent = await messageQueue.enqueue({
        type: 'user_message',
        content: content,
        metadata: metadata,
    });

    if (!sent) {
        console.error('[MessageQueue] Failed to send message');

        // Show error message in chat
        const errorMsg = createMessageElement('assistant', '⚠️ Failed to send message. Please try again.');
        messagesDiv.appendChild(errorMsg);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
}

// Create message element
function createMessageElement(role, content, metadata = {}) {
    const div = document.createElement('div');

    // Check if this is an extension output (Task #11)
    const isExtension = metadata && metadata.is_extension_output === true;

    if (isExtension) {
        div.className = 'message extension';

        const extensionName = metadata.extension_name || metadata.extension_id || 'Extension';
        const action = metadata.action || metadata.action_id || 'default';
        const extensionId = metadata.extension_id || '';
        const status = metadata.status || 'unknown';
        const command = metadata.command || metadata.extension_command || '';

        div.innerHTML = `
            <div class="extension-header">
                <div class="extension-icon">extension</div>
                <div class="extension-info">
                    <div class="extension-name">${escapeHtml(extensionName)}</div>
                    <div class="extension-action">Action: ${escapeHtml(action)}</div>
                </div>
            </div>
            <div class="content">${escapeHtml(content)}</div>
            <div class="extension-meta">
                <div class="extension-meta-toggle" onclick="toggleExtensionMeta(this)">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                    </svg>
                    <span>Extension Details</span>
                </div>
                <div class="extension-meta-content" style="display: none;">
                    <div class="extension-meta-row">
                        <span class="extension-meta-label">Extension ID:</span>
                        <span class="extension-meta-value">${escapeHtml(extensionId)}</span>
                    </div>
                    <div class="extension-meta-row">
                        <span class="extension-meta-label">Action:</span>
                        <span class="extension-meta-value">${escapeHtml(action)}</span>
                    </div>
                    ${command ? `
                    <div class="extension-meta-row">
                        <span class="extension-meta-label">Command:</span>
                        <span class="extension-meta-value">${escapeHtml(command)}</span>
                    </div>
                    ` : ''}
                    <div class="extension-meta-row">
                        <span class="extension-meta-label">Status:</span>
                        <span class="extension-meta-value">${escapeHtml(status)}</span>
                    </div>
                    <div class="extension-meta-row">
                        <span class="extension-meta-label">Executed:</span>
                        <span class="extension-meta-value">${new Date().toLocaleString()}</span>
                    </div>
                </div>
            </div>
        `;
    } else {
        div.className = `message ${role}`;

        // 检查是否为语音消息
        const isVoiceMessage = metadata && metadata.source === 'voice';
        const voiceIcon = isVoiceMessage ? (role === 'user' ? '🎤' : '🔊') : '';

        div.innerHTML = `
            <div class="role">${role}${voiceIcon ? ' ' + voiceIcon : ''}</div>
            <div class="content">${escapeHtml(content)}</div>
            <div class="timestamp">${new Date().toLocaleTimeString()}</div>
        `;
    }

    return div;
}

// Toggle extension metadata visibility (Task #11)
function toggleExtensionMeta(toggleElement) {
    const content = toggleElement.nextElementSibling;
    const isExpanded = content.style.display !== 'none';

    if (isExpanded) {
        content.style.display = 'none';
        toggleElement.classList.remove('expanded');
    } else {
        content.style.display = 'block';
        toggleElement.classList.add('expanded');
    }
}

// Display completion truncation hint (P1-8)
function displayCompletionHint(messagesDiv) {
    // Check if hint already exists for the last message
    const lastMessage = messagesDiv.lastElementChild;
    if (!lastMessage || !lastMessage.classList.contains('assistant')) {
        return;
    }

    // Don't add duplicate hints
    const existingHint = lastMessage.nextElementSibling;
    if (existingHint && existingHint.classList.contains('completion-hint')) {
        return;
    }

    // Create hint element
    const hintEl = document.createElement('div');
    hintEl.className = 'completion-hint';
    hintEl.innerHTML = `
        <span class="hint-icon">
            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
        </span>
        <span class="hint-message">Response truncated due to completion token limit</span>
        <span class="hint-action" onclick="openSettingsForTokenLimit()">Token limits are configurable in Settings.</span>
    `;

    // Insert after the last message
    lastMessage.after(hintEl);
}

// Open settings to adjust token limit (P1-8)
function openSettingsForTokenLimit() {
    // Navigate to settings view (if available)
    // For now, just show a toast with instructions
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #3b82f6;
        color: white;
        padding: 12px 20px;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        z-index: 9999;
        font-size: 14px;
        max-width: 400px;
    `;
    toast.innerHTML = `
        <strong>Token Limit Configuration</strong><br>
        Token limits can be adjusted in your provider settings or model configuration.
    `;
    document.body.appendChild(toast);

    // Auto-remove toast after 3 seconds
    setTimeout(() => toast.remove(), 3000);
}

/**
 * Display external information warning block (Task #5)
 *
 * Shows a clear warning when the LLM declares external info needs.
 * Provides buttons to populate /comm commands (no auto-execution).
 * Offers option to switch to execution phase.
 *
 * @param {HTMLElement} messageElement - The assistant message element
 * @param {Array} externalInfoDeclarations - Array of external info declarations
 */
function displayExternalInfoWarning(messageElement, externalInfoDeclarations) {
    console.log('[ExternalInfo] Displaying warning for', externalInfoDeclarations.length, 'declarations');

    // Don't add duplicate warnings
    const existingWarning = messageElement.querySelector('.external-info-warning');
    if (existingWarning) {
        console.log('[ExternalInfo] Warning already exists, skipping');
        return;
    }

    // Filter only required declarations (required === true)
    const requiredDeclarations = externalInfoDeclarations.filter(decl => decl.required === true);

    if (requiredDeclarations.length === 0) {
        console.log('[ExternalInfo] No required declarations, skipping warning');
        return;
    }

    // Create warning element
    const warningEl = document.createElement('div');
    warningEl.className = 'external-info-warning';

    // Build action buttons from suggested_actions
    let actionButtonsHtml = '';
    requiredDeclarations.forEach((decl, index) => {
        if (decl.suggested_actions && Array.isArray(decl.suggested_actions)) {
            decl.suggested_actions.forEach((action, actionIndex) => {
                const command = action.command || '';
                const label = action.label || command;
                const buttonId = `external-info-action-${index}-${actionIndex}`;

                actionButtonsHtml += `
                    <button class="external-info-action-btn"
                            data-command="${escapeHtml(command)}"
                            id="${buttonId}">
                        <span class="action-icon">arrow_forward</span>
                        <span>${escapeHtml(label)}</span>
                    </button>
                `;
            });
        }
    });

    // Build warning HTML
    warningEl.innerHTML = `
        <div class="external-info-warning-header">
            <span class="external-info-warning-icon">warning</span>
            <span class="external-info-warning-title">External Information Required</span>
        </div>

        <div class="external-info-warning-message">
            This response requires verified external information sources.
            <strong>No external access has been performed.</strong>
        </div>

        <div class="external-info-warning-notice">
            The assistant has identified ${requiredDeclarations.length} external information need(s)
            that cannot be fulfilled in the current planning phase.
        </div>

        ${actionButtonsHtml ? `
            <div class="external-info-actions">
                <div class="external-info-action-label">Suggested Actions:</div>
                <div class="external-info-action-buttons">
                    ${actionButtonsHtml}
                </div>
            </div>
        ` : ''}

        <div class="external-info-phase-switch">
            <button class="external-info-phase-switch-btn" id="external-info-switch-phase">
                <span class="switch-icon">power_settings_new</span>
                <span>Switch to Execution Phase</span>
            </button>
        </div>
    `;

    // Insert warning after the message content
    const contentDiv = messageElement.querySelector('.content');
    if (contentDiv) {
        contentDiv.after(warningEl);
    } else {
        messageElement.appendChild(warningEl);
    }

    // Attach event listeners to action buttons
    requiredDeclarations.forEach((decl, index) => {
        if (decl.suggested_actions && Array.isArray(decl.suggested_actions)) {
            decl.suggested_actions.forEach((action, actionIndex) => {
                const buttonId = `external-info-action-${index}-${actionIndex}`;
                const button = document.getElementById(buttonId);
                if (button) {
                    button.addEventListener('click', () => {
                        populateCommandInInput(action.command);
                    });
                }
            });
        }
    });

    // Attach event listener to phase switch button
    const switchPhaseBtn = document.getElementById('external-info-switch-phase');
    if (switchPhaseBtn) {
        switchPhaseBtn.addEventListener('click', () => {
            triggerPhaseSwitchToExecution();
        });
    }

    console.log('[ExternalInfo] Warning displayed successfully');
}

/**
 * Populate a command in the chat input (Task #5)
 * Does not auto-execute - requires user confirmation
 *
 * @param {string} command - The command to populate
 */
function populateCommandInInput(command) {
    const input = document.getElementById('chat-input');
    if (!input) {
        console.error('[ExternalInfo] Chat input not found');
        return;
    }

    input.value = command;
    input.focus();

    console.log('[ExternalInfo] Populated command:', command);

    // Show a toast to inform the user
    showToast('Command populated. Press Enter to execute.', 'info', 2000);
}

/**
 * Trigger phase switch to execution (Task #5)
 * Uses the PhaseSelector component if available
 */
function triggerPhaseSwitchToExecution() {
    console.log('[ExternalInfo] Triggering phase switch to execution');

    // Check if PhaseSelector is available in global scope
    if (window.phaseSelectorInstance && typeof window.phaseSelectorInstance.selectPhase === 'function') {
        window.phaseSelectorInstance.selectPhase('execution');
        showToast('Switching to execution phase...', 'info', 2000);
    } else {
        // Fallback: Try to click the execution phase button directly
        const executionPhaseBtn = document.querySelector('[data-phase="execution"]');
        if (executionPhaseBtn) {
            executionPhaseBtn.click();
        } else {
            console.error('[ExternalInfo] Phase selector not found');
            showToast('Phase selector not available. Please switch manually.', 'error', 3000);
        }
    }
}

// Create a new session (backend will generate ULID)
async function createSession(title = 'New Chat') {
    try {
        const response = await fetch('/api/sessions', withCsrfToken({
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: title
                // Do not pass session_id - let backend generate ULID
            })
        }));

        if (!response.ok) {
            throw new Error(`Failed to create session: ${response.statusText}`);
        }

        const session = await response.json();
        console.log(`Session created successfully: ${session.id}`);
        return session;
    } catch (err) {
        console.error('Failed to create session:', err);
        throw err;
    }
}

// Load messages
async function loadMessages() {
    try {
        const response = await fetch(`/api/sessions/${state.currentSession}/messages`);

        const messagesDiv = document.getElementById('messages');

        // Check if response is ok
        if (!response.ok) {
            // If session doesn't exist (404), show error instead of auto-creating
            if (response.status === 404) {
                console.error(`Session ${state.currentSession} not found`);
                messagesDiv.innerHTML = '<div class="text-center text-red-500 text-sm">Session not found. Please create a new chat.</div>';
                return;
            }
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const messages = await response.json();

        // Clear existing messages
        messagesDiv.innerHTML = '';

        // Check if messages is an array
        if (!Array.isArray(messages)) {
            console.error('Invalid messages format:', messages);
            messagesDiv.innerHTML = '<div class="text-center text-red-500 text-sm">Error: Invalid message format</div>';
            return;
        }

        if (messages.length === 0) {
            messagesDiv.innerHTML = '<div class="text-center text-gray-500 text-sm">No messages yet. Start a conversation!</div>';
            return;
        }

        messages.forEach(msg => {
            // Pass metadata to createMessageElement for extension detection (Task #11)
            const msgEl = createMessageElement(msg.role, msg.content, msg.metadata || {});

            // Set message ID for source tracking
            if (msg.id) {
                msgEl.dataset.messageId = msg.id;
            }

            messagesDiv.appendChild(msgEl);

            // Apply code block parsing and syntax highlighting to assistant messages
            // Skip if it's an extension message (already formatted)
            const isExtension = msg.metadata && msg.metadata.is_extension_output === true;
            if (msg.role === 'assistant' && !isExtension && window.CodeBlockUtils) {
                const contentDiv = msgEl.querySelector('.content');
                if (contentDiv) {
                    contentDiv.innerHTML = window.CodeBlockUtils.renderAssistantMessage(msg.content);
                    highlightCodeBlocks(contentDiv);
                }
            }
        });

        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    } catch (err) {
        console.error('Failed to load messages:', err);
        const messagesDiv = document.getElementById('messages');
        if (messagesDiv) {
            messagesDiv.innerHTML = '<div class="text-center text-red-500 text-sm">Failed to load messages</div>';
        }
    }
}

// Load conversations list
async function loadConversationsList() {
    try {
        const response = await fetch('/api/sessions');
        const sessions = await response.json();

        const listContainer = document.getElementById('conversations-list');

        if (sessions.length === 0) {
            listContainer.innerHTML = `
                <div class="p-4 text-center text-gray-500 text-sm">
                    No conversations yet.<br/>
                    Click <strong>+</strong> to start a new chat.
                </div>
            `;
            return;
        }

        // Store for filtering
        state.allSessions = sessions;

        renderConversationsList(sessions);
    } catch (err) {
        console.error('Failed to load conversations:', err);
        document.getElementById('conversations-list').innerHTML = `
            <div class="p-4 text-center text-red-500 text-sm">
                Failed to load conversations
            </div>
        `;
    }
}

// Render conversations list
function renderConversationsList(sessions) {
    const listContainer = document.getElementById('conversations-list');

    const html = sessions.map(session => {
        const isActive = session.id === state.currentSession;
        const activeClass = isActive ? 'bg-blue-50 border-l-3 border-blue-600' : 'hover:bg-gray-50';

        return `
            <div
                class="conversation-item ${activeClass} p-4 border-b border-gray-200 transition-colors relative group"
                data-session-id="${session.id}"
            >
                <!-- Checkbox for batch selection -->
                <div class="conversation-checkbox-wrapper" onclick="event.stopPropagation();">
                    <input
                        type="checkbox"
                        class="conversation-checkbox"
                        data-session-id="${session.id}"
                        onchange="toggleConversationSelection()"
                    />
                </div>

                <div class="cursor-pointer" onclick="switchSession('${session.id}')">
                    <div class="flex items-start justify-between mb-2">
                        <h4 class="font-semibold text-sm text-gray-900 truncate flex-1 pr-8">
                            ${escapeHtml(session.title || session.id)}
                        </h4>
                        <span class="text-xs text-gray-500 ml-2">
                            ${formatTimeAgo(session.created_at)}
                        </span>
                    </div>

                    <div class="flex gap-2 flex-wrap">
                        <span class="badge info text-xs">Local</span>
                        <span class="badge info text-xs">Empty</span>
                    </div>
                </div>

                <!-- Delete button (visible on hover) -->
                <button
                    class="absolute top-2 right-2 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-100"
                    onclick="event.stopPropagation(); deleteSession('${session.id}')"
                    title="Delete conversation"
                >
                    <svg class="w-4 h-4 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                </button>
            </div>
        `;
    }).join('');

    listContainer.innerHTML = html;

    // Update batch toolbar state
    updateBatchConversationsToolbar();
}

// Filter conversations by search term
function filterConversations(searchTerm) {
    if (!state.allSessions) return;

    const filtered = state.allSessions.filter(session => {
        const title = (session.title || session.id).toLowerCase();
        return title.includes(searchTerm.toLowerCase());
    });

    renderConversationsList(filtered);
}

// Switch to a different session
async function switchSession(sessionId) {
    if (sessionId === state.currentSession) return;

    // H-8 Fix: Clear message queue on session switch
    messageQueue.clear();

    state.currentSession = sessionId;

    // PR-3: Update session display in toolbar
    updateChatSessionDisplay(sessionId);

    // Task #3: Fetch session data and update mode/phase selectors
    try {
        const response = await fetch(`/api/sessions/${sessionId}`);
        if (response.ok) {
            const sessionData = await response.json();
            updateModePhaseSelectorsForSession(sessionId, sessionData);
        }
    } catch (err) {
        console.error('Failed to fetch session data for selectors:', err);
    }

    // Reload messages
    await loadMessages();

    // Reconnect WebSocket
    setupWebSocket();

    // Update context status (Task #8)
    loadContextStatus();

    // Update Memory Badge (Task #9)
    updateMemoryBadge(sessionId);

    // Restore provider/model from session runtime
    await restoreProviderFromSession(sessionId);

    // Update active state in list
    document.querySelectorAll('.conversation-item').forEach(item => {
        if (item.dataset.sessionId === sessionId) {
            item.classList.add('bg-blue-50', 'border-l-3', 'border-blue-600');
            item.classList.remove('hover:bg-gray-50');
        } else {
            item.classList.remove('bg-blue-50', 'border-l-3', 'border-blue-600');
            item.classList.add('hover:bg-gray-50');
        }
    });
}

// PR-3: Update chat session display in toolbar
function updateChatSessionDisplay(sessionId) {
    const sessionIdDisplay = document.getElementById('chat-session-id');
    const sessionCopyBtn = document.getElementById('chat-session-copy');
    const viewSessionBtn = document.getElementById('chat-view-session');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    if (!sessionIdDisplay) return; // Not in chat view

    if (sessionId) {
        // Show session ID
        sessionIdDisplay.textContent = sessionId;
        sessionCopyBtn.style.display = 'inline-block';
        viewSessionBtn.style.display = 'inline-block';

        // Enable input (PR-3 护栏Rule)
        if (chatInput) {
            chatInput.disabled = false;
            chatInput.placeholder = 'Type your message... (Shift+Enter for new line)';
        }
        if (sendBtn) {
            sendBtn.disabled = false;
        }

        // Setup copy button
        sessionCopyBtn.onclick = () => {
            navigator.clipboard.writeText(sessionId);
            showToast('Session ID copied', 'success', 1500);
        };

        // Setup view session button
        viewSessionBtn.onclick = () => {
            window.navigateToView('sessions', { session_id: sessionId });
        };
    } else {
        // No session - disable input (PR-3 护栏Rule)
        sessionIdDisplay.textContent = 'No session';
        sessionCopyBtn.style.display = 'none';
        viewSessionBtn.style.display = 'none';

        if (chatInput) {
            chatInput.disabled = true;
            chatInput.placeholder = 'Select a session first to start chatting';
        }
        if (sendBtn) {
            sendBtn.disabled = true;
        }
    }
}

// PR-3: Update WebSocket status display
function updateChatWSStatus(status, message) {
    const wsStatus = document.getElementById('chat-ws-status');
    if (!wsStatus) return; // Not in chat view

    const dot = wsStatus.querySelector('.w-2');
    const text = wsStatus.querySelector('span');

    if (status === 'connected') {
        dot.className = 'w-2 h-2 rounded-full bg-green-500';
        text.textContent = message || 'Connected';
        text.className = 'text-xs font-medium text-green-700';
    } else if (status === 'connecting') {
        dot.className = 'w-2 h-2 rounded-full bg-yellow-500 animate-pulse';
        text.textContent = message || 'Connecting...';
        text.className = 'text-xs font-medium text-yellow-700';
    } else if (status === 'disconnected') {
        dot.className = 'w-2 h-2 rounded-full bg-red-500';
        text.textContent = message || 'Disconnected';
        text.className = 'text-xs font-medium text-red-700';
    } else {
        dot.className = 'w-2 h-2 rounded-full bg-gray-400';
        text.textContent = message || 'Not Connected';
        text.className = 'text-xs font-medium text-gray-600';
    }
}

// Create new chat
async function createNewChat() {
    try {
        const response = await fetch('/api/sessions', withCsrfToken({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: `Chat ${new Date().toLocaleString()}`,
                tags: ['user-created'],
            }),
        }));

        const newSession = await response.json();

        // Switch to new session
        await switchSession(newSession.id);

        // Reload conversations list
        await loadConversationsList();
    } catch (err) {
        console.error('Failed to create new chat:', err);
        Dialog.alert('Failed to create new chat', { title: 'Error' });
    }
}

// Delete a single session
async function deleteSession(sessionId) {
    const confirmed = await Dialog.confirm('Delete this conversation? This action cannot be undone.', {
        title: 'Delete Conversation',
        confirmText: 'Delete',
        danger: true
    });
    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch(`/api/sessions/${sessionId}`, withCsrfToken({
            method: 'DELETE',
        }));

        if (!response.ok) {
            throw new Error('Failed to delete session');
        }

        console.log(`Deleted session: ${sessionId}`);

        // If deleting current session, switch to a different one or create new
        if (sessionId === state.currentSession) {
            // Try to switch to another session
            const sessions = state.allSessions || [];
            const otherSession = sessions.find(s => s.id !== sessionId);

            if (otherSession) {
                await switchSession(otherSession.id);
            } else {
                // No other sessions, create a new one
                await createNewChat();
            }
        }

        // Reload conversations list
        await loadConversationsList();
    } catch (err) {
        console.error('Failed to delete session:', err);
        Dialog.alert('Failed to delete conversation', { title: 'Error' });
    }
}

// Clear all sessions
async function clearAllSessions() {
    const confirmed1 = await Dialog.confirm('Delete ALL conversations? This will clear your entire chat history. This action cannot be undone.', {
        title: 'Delete All Conversations',
        confirmText: 'Continue',
        danger: true
    });
    if (!confirmed1) {
        return;
    }

    // Double confirmation for safety
    const confirmed2 = await Dialog.confirm('Are you ABSOLUTELY sure? All conversations will be permanently deleted.', {
        title: 'Final Confirmation',
        confirmText: 'Delete All',
        danger: true
    });
    if (!confirmed2) {
        return;
    }

    try {
        const response = await fetch('/api/sessions', withCsrfToken({
            method: 'DELETE',
        }));

        if (!response.ok) {
            throw new Error('Failed to clear all sessions');
        }

        const result = await response.json();
        console.log(`Cleared all sessions: ${result.deleted_count} deleted`);

        // Clear current state
        state.currentSession = null;
        state.allSessions = [];

        // Clear messages UI
        const messagesDiv = document.getElementById('messages');
        if (messagesDiv) {
            messagesDiv.innerHTML = `
                <div class="flex items-center justify-center h-full text-gray-500">
                    <div class="text-center">
                        <p class="text-lg mb-2">All conversations cleared</p>
                        <p class="text-sm">Click <strong>+</strong> to start a new chat</p>
                    </div>
                </div>
            `;
        }

        // Update session display
        updateChatSessionDisplay(null);

        // Reload conversations list (should be empty)
        await loadConversationsList();

        Dialog.alert(`Successfully deleted ${result.deleted_count} conversation(s)`, { title: 'Success' });
    } catch (err) {
        console.error('Failed to clear all sessions:', err);
        Dialog.alert('Failed to clear all conversations', { title: 'Error' });
    }
}

// ============================================================================
// Batch Delete Conversations (Sessions)
// ============================================================================

// Toggle conversation selection
function toggleConversationSelection() {
    updateBatchConversationsToolbar();
}

// Toggle select all conversations
function toggleSelectAllConversations() {
    const checkboxes = document.querySelectorAll('.conversation-checkbox');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);

    checkboxes.forEach(cb => {
        cb.checked = !allChecked;
    });

    updateBatchConversationsToolbar();
}

// Update batch conversations toolbar state
function updateBatchConversationsToolbar() {
    const toolbar = document.getElementById('batch-conversations-toolbar');
    const selectedCheckboxes = document.querySelectorAll('.conversation-checkbox:checked');
    const selectedCount = selectedCheckboxes.length;
    const countDisplay = document.getElementById('selected-conversations-count');
    const selectAllBtn = document.getElementById('select-all-conversations-btn');

    if (!toolbar) return;

    if (selectedCount > 0) {
        toolbar.style.display = 'flex';
        if (countDisplay) {
            countDisplay.textContent = `${selectedCount} selected`;
        }
        if (selectAllBtn) {
            const allCheckboxes = document.querySelectorAll('.conversation-checkbox');
            const allChecked = selectedCount === allCheckboxes.length;
            selectAllBtn.textContent = allChecked ? 'Deselect All' : 'Select All';
        }

        // Add highlight to selected items
        selectedCheckboxes.forEach(cb => {
            const item = cb.closest('.conversation-item');
            if (item) {
                item.classList.add('conversation-selected');
            }
        });

        // Remove highlight from unselected items
        const allCheckboxes = document.querySelectorAll('.conversation-checkbox:not(:checked)');
        allCheckboxes.forEach(cb => {
            const item = cb.closest('.conversation-item');
            if (item) {
                item.classList.remove('conversation-selected');
            }
        });
    } else {
        toolbar.style.display = 'none';

        // Remove all highlights
        const allItems = document.querySelectorAll('.conversation-item');
        allItems.forEach(item => {
            item.classList.remove('conversation-selected');
        });
    }
}

// Delete selected conversations
async function deleteSelectedConversations() {
    const selectedCheckboxes = document.querySelectorAll('.conversation-checkbox:checked');
    const sessionIds = Array.from(selectedCheckboxes).map(cb => cb.dataset.sessionId);

    if (sessionIds.length === 0) {
        Dialog.alert('No conversations selected', { title: 'Delete Conversations' });
        return;
    }

    const confirmed = await Dialog.confirm(
        `Delete ${sessionIds.length} selected conversation(s)? This action cannot be undone.`,
        {
            title: 'Delete Conversations',
            confirmText: 'Delete',
            danger: true
        }
    );

    if (!confirmed) {
        return;
    }

    try {
        let deletedCount = 0;
        let failedCount = 0;

        // Delete each session
        for (const sessionId of sessionIds) {
            try {
                const response = await fetch(`/api/sessions/${sessionId}`, withCsrfToken({
                    method: 'DELETE'
                }));

                if (response.ok) {
                    deletedCount++;

                    // If deleting current session, switch to another
                    if (sessionId === state.currentSession) {
                        const remainingSessions = state.allSessions.filter(s => !sessionIds.includes(s.id));
                        if (remainingSessions.length > 0) {
                            await switchSession(remainingSessions[0].id);
                        } else {
                            // No sessions left, create a new one
                            await createNewChat();
                        }
                    }
                } else {
                    failedCount++;
                }
            } catch (err) {
                console.error(`Failed to delete session ${sessionId}:`, err);
                failedCount++;
            }
        }

        // Reload conversations list
        await loadConversationsList();

        // Show success message
        if (deletedCount > 0) {
            showToast(
                `Successfully deleted ${deletedCount} conversation(s)`,
                'success',
                2000
            );
        }

        // Show warning if any failed
        if (failedCount > 0) {
            showToast(
                `Warning: ${failedCount} conversation(s) failed to delete`,
                'warning',
                3000
            );
        }

        // Reset toolbar
        updateBatchConversationsToolbar();
    } catch (err) {
        console.error('Failed to delete conversations:', err);
        Dialog.alert('Failed to delete selected conversations', { title: 'Error' });
    }
}

// Format time ago (helper function)
// Task #14: Added defensive timezone validation
function formatTimeAgo(timestamp) {
    if (!timestamp) return 'Unknown';

    // Defensive check: same as formatTimestamp
    if (typeof timestamp === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(timestamp)) {
        const isDev = (typeof process !== 'undefined' && process.env && process.env.NODE_ENV === 'development') ||
                      window.location.hostname === 'localhost' ||
                      window.location.hostname === '127.0.0.1';

        if (isDev) {
            console.warn(`[formatTimeAgo] Timestamp without timezone: ${timestamp}. Assuming UTC.`);
        }

        timestamp = timestamp + 'Z';
    }

    try {
        const now = new Date();
        const then = new Date(timestamp);

        if (isNaN(then.getTime())) {
            console.error(`[formatTimeAgo] Invalid timestamp: ${timestamp}`);
            return 'Unknown';
        }

        const seconds = Math.floor((now - then) / 1000);

        if (seconds < 60) return 'Just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;

        return then.toLocaleDateString();
    } catch (e) {
        console.error(`[formatTimeAgo] Error parsing timestamp: ${timestamp}`, e);
        return 'Unknown';
    }
}

// Restore provider/model from session runtime to UI
async function restoreProviderFromSession(sessionId) {
    try {
        const response = await fetch(`/api/sessions/${sessionId}/runtime`);
        if (!response.ok) {
            console.log('[Restore Provider] Session has no runtime, skipping');
            return;
        }

        const data = await response.json();
        if (!data.runtime) {
            console.log('[Restore Provider] Session runtime is empty, skipping');
            return;
        }

        const { provider, model } = data.runtime;
        console.log('[Restore Provider] Restoring from session:', { provider, model });

        // Update UI selects
        const providerEl = document.getElementById('model-provider');
        const modelEl = document.getElementById('model-name');

        if (providerEl && provider) {
            // Extract provider type from instance ID (e.g., 'llamacpp:qwen3-coder-30b' → 'llamacpp')
            const providerType = provider.includes(':') ? provider.split(':')[0] : provider;
            console.log('[Restore Provider] Extracted provider type:', providerType);

            providerEl.value = providerType;
            state.currentProvider = providerType;
            // Reload models for this provider
            await loadAvailableModels();
            console.log('[Restore Provider] Models loaded, options count:', modelEl?.options.length);
        }

        if (modelEl && model) {
            console.log('[Restore Provider] Setting model to:', model);
            modelEl.value = model;
            console.log('[Restore Provider] Model value after setting:', modelEl.value);
            // Check if the value was actually set (if not, the option doesn't exist)
            if (modelEl.value !== model) {
                console.warn('[Restore Provider] ⚠️  Model not found in dropdown:', model);
                console.log('[Restore Provider] Available models:',
                    Array.from(modelEl.options).map(opt => opt.value));
            }
        }

        // Update status display
        refreshProviderStatus();

        console.log('[Restore Provider] Provider/model restored successfully');
    } catch (err) {
        console.error('[Restore Provider] Error restoring provider from session:', err);
    }
}

// Update session runtime when provider/model changes
async function updateSessionRuntime() {
    if (!state.currentSession) {
        console.log('[Update Session Runtime] No active session, skipping');
        return;
    }

    const providerEl = document.getElementById('model-provider');
    const modelEl = document.getElementById('model-name');

    let provider = providerEl ? providerEl.value : null;
    const model = modelEl ? modelEl.value : null;

    if (!provider) {
        console.log('[Update Session Runtime] No provider selected, skipping');
        return;
    }

    try {
        // For multi-instance providers (like llamacpp), need to match the full instance ID
        // Backend expects: "llamacpp:qwen3-coder-30b", not just "llamacpp"
        if (provider === 'llamacpp' && model) {
            // Get provider status to find matching instance
            const statusResp = await fetch('/api/providers/status');
            if (statusResp.ok) {
                const statusData = await statusResp.json();

                // Find llamacpp instance that matches the model
                const modelNormalized = model.toLowerCase().replace('.gguf', '').replace(/_/g, '-');
                const matchingInstance = statusData.providers.find(p => {
                    if (!p.id.startsWith('llamacpp:')) return false;
                    const instanceId = p.id.split(':')[1] || '';
                    return instanceId.includes(modelNormalized) || modelNormalized.includes(instanceId);
                });

                if (matchingInstance) {
                    provider = matchingInstance.id;
                    console.log('[Update Session Runtime] Matched llamacpp instance:', provider);
                } else {
                    console.warn('[Update Session Runtime] No matching llamacpp instance found for model:', model);
                    // Still try with provider type, backend might handle it
                }
            }
        }

        console.log('[Update Session Runtime] Updating session runtime:', { provider, model });
        const response = await fetch(`/api/sessions/${state.currentSession}/runtime`, withCsrfToken({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, model }),
        }));

        if (response.ok) {
            console.log('[Update Session Runtime] Session runtime updated successfully');
        } else {
            const errorText = await response.text();
            console.warn('[Update Session Runtime] Failed to update session runtime:', errorText);
        }
    } catch (err) {
        console.error('[Update Session Runtime] Error updating session runtime:', err);
    }
}

// Setup Model Toolbar
function setupModelToolbar() {
    const modelTypeSelect = document.getElementById('model-type');
    const modelProviderSelect = document.getElementById('model-provider');
    const modelNameSelect = document.getElementById('model-name');
    const selfcheckBtn = document.getElementById('selfcheck-btn');
    const settingsBtn = document.getElementById('settings-drawer-btn');

    // Model type change handler
    modelTypeSelect.addEventListener('change', (e) => {
        updateProviderOptions(e.target.value);
        refreshProviderStatus();
    });

    // Provider change handler
    modelProviderSelect.addEventListener('change', async () => {
        state.currentProvider = modelProviderSelect.value;
        console.log('[Provider Selection] Provider changed to:', state.currentProvider);
        // Save to localStorage
        localStorage.setItem('agentos_model_provider', modelProviderSelect.value);
        loadAvailableModels();
        refreshProviderStatus();

        // Sync to session runtime
        await updateSessionRuntime();
    });

    // Model change handler
    modelNameSelect.addEventListener('change', async () => {
        // Model selected - status will be reflected in next status poll
        console.log('Model selected:', modelNameSelect.value);
        // Save to localStorage
        if (modelNameSelect.value) {
            localStorage.setItem('agentos_model_name', modelNameSelect.value);
        }

        // Sync to session runtime
        await updateSessionRuntime();
    });

    // Self-check button
    selfcheckBtn.addEventListener('click', runSelfCheck);

    // Settings drawer button
    settingsBtn.addEventListener('click', () => {
        openSettingsDrawer();
    });

    // Initialize - restore from localStorage or use defaults
    const savedProvider = localStorage.getItem('agentos_model_provider');
    const savedModel = localStorage.getItem('agentos_model_name');

    updateProviderOptions('local');

    // Restore provider selection
    if (savedProvider && modelProviderSelect) {
        modelProviderSelect.value = savedProvider;
        state.currentProvider = savedProvider;
        console.log('[Initialization] Restored provider from localStorage:', savedProvider);
    } else {
        state.currentProvider = 'ollama';
        console.log('[Initialization] Using default provider: ollama');
    }

    // Load models for selected provider
    loadAvailableModels().then(() => {
        // Restore model selection after models are loaded
        if (savedModel && modelNameSelect) {
            // Check if saved model exists in the options
            const modelOption = Array.from(modelNameSelect.options).find(opt => opt.value === savedModel);
            if (modelOption) {
                modelNameSelect.value = savedModel;
                console.log('Restored model selection:', savedModel);
            }
        }
    });

    // Start provider status polling
    startProviderStatusPolling();

    // Start context status polling (Task #8)
    startContextStatusPolling();
    loadContextStatus(); // Initial load
}

// Update provider options based on model type
function updateProviderOptions(modelType) {
    const providerSelect = document.getElementById('model-provider');

    if (modelType === 'local') {
        providerSelect.innerHTML = `
            <option value="ollama">Ollama</option>
            <option value="lmstudio">LM Studio</option>
            <option value="llamacpp">llama.cpp</option>
        `;
    } else {
        providerSelect.innerHTML = `
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="bedrock">AWS Bedrock</option>
            <option value="azure">Azure OpenAI</option>
        `;
    }

    loadAvailableModels();
}

// Load available models for selected provider
async function loadAvailableModels() {
    const provider = document.getElementById('model-provider').value;
    const modelSelect = document.getElementById('model-name');

    if (!provider) {
        modelSelect.innerHTML = '<option value="">Select provider first</option>';
        return;
    }

    modelSelect.innerHTML = '<option value="">Loading...</option>';

    try {
        const response = await fetch(`/api/providers/${provider}/models`);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            console.warn(`Provider ${provider} not available:`, error.detail);
            modelSelect.innerHTML = '<option value="">Provider not available</option>';
            return;
        }

        const data = await response.json();

        if (data.models && data.models.length > 0) {
            const options = data.models.map(model =>
                `<option value="${model.id}">${model.label}</option>`
            ).join('');

            modelSelect.innerHTML = `
                <option value="">Select model...</option>
                ${options}
            `;
        } else {
            modelSelect.innerHTML = '<option value="">No models available</option>';
        }
    } catch (err) {
        console.error('Failed to load models:', err);
        modelSelect.innerHTML = '<option value="">Error loading models</option>';
    }
}

// Update model link status
function updateModelLinkStatus(status, statusData = null) {
    console.log('[Model Link Status] Updating status to:', status, 'with data:', statusData);

    const statusEl = document.getElementById('model-link-status');
    if (!statusEl) {
        // Element doesn't exist in current view
        console.log('[Model Link Status] Status element not found in DOM');
        return;
    }
    const dot = statusEl.querySelector('.w-2');
    const text = statusEl.querySelector('span');

    // Remove old classes
    statusEl.classList.remove('bg-gray-100', 'bg-red-50', 'bg-yellow-50', 'bg-green-50', 'bg-blue-50');
    dot.classList.remove('bg-gray-400', 'bg-red-500', 'bg-yellow-500', 'bg-green-500', 'bg-blue-500', 'animate-pulse');

    // Build tooltip
    let title = '';
    if (statusData) {
        title = `Endpoint: ${statusData.endpoint || 'N/A'}\n`;
        if (statusData.latency_ms) {
            title += `Latency: ${statusData.latency_ms}ms\n`;
        }
        if (statusData.last_error) {
            title += `Error: ${statusData.last_error}`;
        }
    }
    statusEl.title = title;

    switch (status) {
        case 'DISCONNECTED':
            statusEl.classList.add('bg-gray-100');
            dot.classList.add('bg-gray-400');
            text.textContent = 'Disconnected';
            text.className = 'text-sm font-medium text-gray-600';
            console.log('[Model Link Status] ✅ Display updated to: DISCONNECTED (gray)');
            break;
        case 'CONNECTING':
            statusEl.classList.add('bg-blue-50');
            dot.classList.add('bg-blue-500', 'animate-pulse');
            text.textContent = 'Connecting...';
            text.className = 'text-sm font-medium text-blue-700';
            console.log('[Model Link Status] ✅ Display updated to: CONNECTING (blue)');
            break;
        case 'READY':
            statusEl.classList.add('bg-green-50');
            dot.classList.add('bg-green-500');
            const latencyText = statusData?.latency_ms ? ` (${Math.round(statusData.latency_ms)}ms)` : '';
            text.textContent = `Ready${latencyText}`;
            text.className = 'text-sm font-medium text-green-700';
            console.log('[Model Link Status] ✅ Display updated to: READY (green)');
            break;
        case 'RUNNING':
            statusEl.classList.add('bg-green-50');
            dot.classList.add('bg-green-500');
            text.textContent = 'Running';
            text.className = 'text-sm font-medium text-green-700';
            console.log('[Model Link Status] ✅ Display updated to: RUNNING (green)');
            break;
        case 'DEGRADED':
            statusEl.classList.add('bg-yellow-50');
            dot.classList.add('bg-yellow-500');
            text.textContent = 'Degraded';
            text.className = 'text-sm font-medium text-yellow-700';
            console.log('[Model Link Status] ✅ Display updated to: DEGRADED (yellow)');
            break;
        case 'ERROR':
            statusEl.classList.add('bg-red-50');
            dot.classList.add('bg-red-500');
            text.textContent = 'Error';
            text.className = 'text-sm font-medium text-red-700';
            console.log('[Model Link Status] ✅ Display updated to: ERROR (red)');
            break;
        default:
            console.log('[Model Link Status] ⚠️  Unknown status received:', status);
    }
}

// Update context status
function updateContextStatus(status) {
    const statusEl = document.getElementById('context-status');
    if (!statusEl) {
        // Element doesn't exist in current view
        return;
    }
    const dot = statusEl.querySelector('.w-2');
    const text = statusEl.querySelector('span');

    // Remove old classes
    statusEl.classList.remove('bg-gray-100', 'bg-green-50', 'bg-blue-50', 'bg-yellow-50', 'bg-red-50');
    dot.classList.remove('bg-gray-400', 'bg-green-500', 'bg-blue-500', 'bg-yellow-500', 'bg-red-500');

    switch (status) {
        case 'EMPTY':
            statusEl.classList.add('bg-gray-100');
            dot.classList.add('bg-gray-400');
            text.textContent = 'Empty';
            text.className = 'font-medium text-gray-600';
            break;
        case 'ATTACHED':
            statusEl.classList.add('bg-green-50');
            dot.classList.add('bg-green-500');
            text.textContent = 'Attached';
            text.className = 'font-medium text-green-700';
            break;
        case 'BUILDING':
            statusEl.classList.add('bg-blue-50');
            dot.classList.add('bg-blue-500', 'animate-pulse');
            text.textContent = 'Building...';
            text.className = 'font-medium text-blue-700';
            break;
        case 'STALE':
            statusEl.classList.add('bg-yellow-50');
            dot.classList.add('bg-yellow-500');
            text.textContent = 'Stale';
            text.className = 'font-medium text-yellow-700';
            break;
        case 'ERROR':
            statusEl.classList.add('bg-red-50');
            dot.classList.add('bg-red-500');
            text.textContent = 'Error';
            text.className = 'font-medium text-red-700';
            break;
    }
}

// Start provider status polling
function startProviderStatusPolling() {
    // Initial fetch
    refreshProviderStatus();

    // Poll every 5 seconds
    if (state.providerStatusInterval) {
        clearInterval(state.providerStatusInterval);
    }

    state.providerStatusInterval = setInterval(() => {
        refreshProviderStatus();
    }, 5000);
}

// Refresh provider status
async function refreshProviderStatus() {
    console.log('[Provider Status Poll] === START (v2-session-aware) ===');
    try {
        const response = await fetch('/api/providers/status');
        const data = await response.json();

        // IMPORTANT: Get provider from current session's runtime config (consistent with self-check)
        let currentProvider = null;
        let currentModel = null;
        console.log('[Provider Status Poll] state.currentSession:', state.currentSession);

        if (state.currentSession) {
            try {
                const sessionResp = await fetch(`/api/sessions/${state.currentSession}/runtime`);
                if (sessionResp.ok) {
                    const sessionData = await sessionResp.json();
                    if (sessionData.runtime) {
                        currentProvider = sessionData.runtime.provider;
                        currentModel = sessionData.runtime.model;
                        console.log('[Provider Status Poll] Using session runtime:', { provider: currentProvider, model: currentModel });
                    }
                }
            } catch (err) {
                console.warn('[Provider Status Poll] Failed to get session runtime, falling back to UI:', err);
            }
        }

        // Fallback to UI selection if session runtime not available
        if (!currentProvider) {
            const providerEl = document.getElementById('model-provider');
            const modelEl = document.getElementById('model-name');
            currentProvider = state.currentProvider || (providerEl ? providerEl.value : null);
            currentModel = modelEl ? modelEl.value : null;
            console.log('[Provider Status Poll] Fallback to UI selection:', { provider: currentProvider, model: currentModel });
        }

        // Debug: Log current selection
        console.log('[Provider Status Poll] Final provider:', currentProvider);
        console.log('[Provider Status Poll] Final model:', currentModel);
        console.log('[Provider Status Poll] All providers from API:', data.providers.map(p => ({ id: p.id, state: p.state })));

        if (!currentProvider) {
            // No provider selected or element doesn't exist
            console.log('[Provider Status Poll] No provider selected, skipping update');
            return;
        }

        // Try exact match first (e.g., "ollama", "llamacpp:qwen3-coder-30b")
        let providerStatus = data.providers.find(p => p.id === currentProvider);
        if (providerStatus) {
            console.log('[Provider Status Poll] ✅ Found exact match for provider:', providerStatus.id, '| state:', providerStatus.state);
        }

        // If no exact match, try to find instances with prefix match
        if (!providerStatus) {
            const prefix = `${currentProvider}:`;
            const matchingProviders = data.providers.filter(p => p.id.startsWith(prefix));
            console.log('[Provider Status Poll] ⚠️  No exact match, trying prefix match with:', prefix);
            console.log('[Provider Status Poll] Matching providers:', matchingProviders.map(p => ({ id: p.id, state: p.state })));

            if (matchingProviders.length > 0) {
                // If a model is selected, try to find the specific instance by matching model name
                if (currentModel) {
                    // Normalize model name for matching (lowercase, remove .gguf, replace _ with -)
                    const modelNormalized = currentModel.toLowerCase().replace('.gguf', '').replace(/_/g, '-');
                    console.log('[Provider Status Poll] Trying to match by model name:', modelNormalized);

                    // Try to find instance whose ID contains the model name
                    providerStatus = matchingProviders.find(p => {
                        const instanceId = p.id.split(':')[1] || ''; // Extract instance ID after ":"
                        const matches = instanceId.includes(modelNormalized) || modelNormalized.includes(instanceId);
                        if (matches) {
                            console.log('[Provider Status Poll]   ✓ Match found:', p.id, '(instanceId:', instanceId, ')');
                        }
                        return matches;
                    });

                    if (providerStatus) {
                        console.log('[Provider Status Poll] ✅ Matched by model name:', providerStatus.id, '| state:', providerStatus.state);
                    } else {
                        console.log('[Provider Status Poll] ⚠️  No model-based match, falling back to first READY or first instance');
                        // Fallback: pick first READY instance
                        providerStatus = matchingProviders.find(p => p.state === 'READY') || matchingProviders[0];
                        console.log('[Provider Status Poll] Selected fallback:', providerStatus.id, '| state:', providerStatus.state);
                    }
                } else {
                    console.log('[Provider Status Poll] No model specified, selecting first READY or first instance');
                    // No model selected, pick first READY instance or first instance
                    providerStatus = matchingProviders.find(p => p.state === 'READY') || matchingProviders[0];
                    console.log('[Provider Status Poll] Selected:', providerStatus.id, '| state:', providerStatus.state);
                }
            } else {
                console.log('[Provider Status Poll] ❌ No matching providers found for prefix:', prefix);
            }
        }

        if (providerStatus) {
            console.log('[Provider Status Poll] 🎯 FINAL RESULT:', {
                id: providerStatus.id,
                state: providerStatus.state,
                endpoint: providerStatus.endpoint,
                error: providerStatus.last_error
            });
            console.log('[Provider Status Poll] 📤 Calling updateModelLinkStatus with state:', providerStatus.state);
            updateModelLinkStatus(providerStatus.state, providerStatus);
        } else {
            // Provider not found, show disconnected
            console.log('[Provider Status Poll] ❌ Provider not found in status response');
            console.log('[Provider Status Poll] 📤 Calling updateModelLinkStatus with state: DISCONNECTED');
            updateModelLinkStatus('DISCONNECTED');
        }
    } catch (err) {
        console.error('Failed to fetch provider status:', err);
        updateModelLinkStatus('ERROR');
    }
}

// Open Settings Drawer
function openSettingsDrawer() {
    // Check if drawer already exists
    let drawer = document.getElementById('settings-drawer');
    if (drawer) {
        drawer.classList.remove('hidden');
        return;
    }

    // Create drawer
    const drawerHTML = `
        <div id="settings-drawer" class="fixed inset-0 z-50">
            <!-- Backdrop -->
            <div class="absolute inset-0 bg-black bg-opacity-50" onclick="closeSettingsDrawer()"></div>

            <!-- Drawer -->
            <div class="absolute right-0 top-0 h-full w-96 bg-white shadow-xl flex flex-col">
                <!-- Header -->
                <div class="flex items-center justify-between p-4 border-b border-gray-200">
                    <h2 class="text-lg font-semibold text-gray-900">Settings</h2>
                    <button
                        onclick="closeSettingsDrawer()"
                        class="p-1 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                        <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <!-- Tabs -->
                <div class="flex border-b border-gray-200">
                    <button
                        class="drawer-tab active px-4 py-2 text-sm font-medium"
                        data-tab="local-setup"
                        onclick="switchDrawerTab('local-setup')"
                    >
                        Local Setup
                    </button>
                    <button
                        class="drawer-tab px-4 py-2 text-sm font-medium"
                        data-tab="cloud-config"
                        onclick="switchDrawerTab('cloud-config')"
                    >
                        Cloud Config
                    </button>
                    <button
                        class="drawer-tab px-4 py-2 text-sm font-medium"
                        data-tab="context"
                        onclick="switchDrawerTab('context')"
                    >
                        Context
                    </button>
                </div>

                <!-- Content -->
                <div class="flex-1 overflow-y-auto">
                    <div id="drawer-tab-local-setup" class="drawer-tab-content p-4">
                        <h3 class="font-semibold mb-3">Local Model Providers</h3>
                        <div id="local-detect-results" class="space-y-3">
                            <div class="text-center text-gray-500 text-sm py-4">
                                Loading...
                            </div>
                        </div>
                        <button
                            onclick="refreshLocalDetect()"
                            class="mt-4 w-full px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                        >
                            Refresh Detection
                        </button>
                    </div>

                    <div id="drawer-tab-cloud-config" class="drawer-tab-content hidden p-4">
                        <h3 class="font-semibold mb-3">Cloud Provider Config</h3>

                        <!-- OpenAI Config -->
                        <div class="border border-gray-200 rounded-lg p-4 mb-4">
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="font-semibold text-sm">OpenAI</h4>
                                <div id="openai-status" class="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-gray-100">
                                    <div class="w-2 h-2 rounded-full bg-gray-400"></div>
                                    <span class="text-xs font-medium text-gray-600">Unknown</span>
                                </div>
                            </div>

                            <div class="space-y-3">
                                <div>
                                    <label class="block text-xs text-gray-600 mb-1">API Key</label>
                                    <input
                                        type="password"
                                        id="openai-api-key"
                                        placeholder="sk-..."
                                        class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                                <div>
                                    <label class="block text-xs text-gray-600 mb-1">Base URL (optional)</label>
                                    <input
                                        type="text"
                                        id="openai-base-url"
                                        placeholder="https://api.openai.com/v1"
                                        class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                <div id="openai-test-result" class="hidden text-xs"></div>

                                <div class="flex gap-2">
                                    <button
                                        onclick="saveAndTestCloudProvider('openai')"
                                        class="flex-1 px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                                    >
                                        Save & Test
                                    </button>
                                    <button
                                        onclick="clearCloudProvider('openai')"
                                        class="px-3 py-2 text-sm font-medium text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300 transition-colors"
                                    >
                                        Clear
                                    </button>
                                </div>
                            </div>
                        </div>

                        <!-- Anthropic Config -->
                        <div class="border border-gray-200 rounded-lg p-4">
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="font-semibold text-sm">Anthropic</h4>
                                <div id="anthropic-status" class="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-gray-100">
                                    <div class="w-2 h-2 rounded-full bg-gray-400"></div>
                                    <span class="text-xs font-medium text-gray-600">Unknown</span>
                                </div>
                            </div>

                            <div class="space-y-3">
                                <div>
                                    <label class="block text-xs text-gray-600 mb-1">API Key</label>
                                    <input
                                        type="password"
                                        id="anthropic-api-key"
                                        placeholder="sk-ant-..."
                                        class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                                <div>
                                    <label class="block text-xs text-gray-600 mb-1">Base URL (optional)</label>
                                    <input
                                        type="text"
                                        id="anthropic-base-url"
                                        placeholder="https://api.anthropic.com/v1"
                                        class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>

                                <div id="anthropic-test-result" class="hidden text-xs"></div>

                                <div class="flex gap-2">
                                    <button
                                        onclick="saveAndTestCloudProvider('anthropic')"
                                        class="flex-1 px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                                    >
                                        Save & Test
                                    </button>
                                    <button
                                        onclick="clearCloudProvider('anthropic')"
                                        class="px-3 py-2 text-sm font-medium text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300 transition-colors"
                                    >
                                        Clear
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div id="drawer-tab-context" class="drawer-tab-content hidden p-4">
                        <h3 class="font-semibold mb-3">Context Management</h3>

                        <!-- Context Status Summary -->
                        <div id="context-status-summary" class="mb-4 p-3 border border-gray-200 rounded-lg bg-gray-50">
                            <div class="text-xs text-gray-500">Loading...</div>
                        </div>

                        <!-- Memory Configuration -->
                        <div class="border border-gray-200 rounded-lg p-4 mb-4">
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="font-semibold text-sm">Memory</h4>
                                <label class="relative inline-flex items-center cursor-pointer">
                                    <input type="checkbox" id="memory-enabled" class="sr-only peer">
                                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                                </label>
                            </div>

                            <div id="memory-config" class="space-y-3">
                                <div>
                                    <label class="block text-xs text-gray-600 mb-1">Namespace</label>
                                    <input
                                        type="text"
                                        id="memory-namespace"
                                        placeholder="e.g., main"
                                        class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                                <div id="memory-status-detail" class="text-xs text-gray-600"></div>
                            </div>
                        </div>

                        <!-- RAG Configuration -->
                        <div class="border border-gray-200 rounded-lg p-4 mb-4">
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="font-semibold text-sm">RAG</h4>
                                <label class="relative inline-flex items-center cursor-pointer">
                                    <input type="checkbox" id="rag-enabled" class="sr-only peer">
                                    <div class="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                                </label>
                            </div>

                            <div id="rag-config" class="space-y-3">
                                <div>
                                    <label class="block text-xs text-gray-600 mb-1">Index</label>
                                    <input
                                        type="text"
                                        id="rag-index"
                                        placeholder="e.g., project-default"
                                        class="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                                <div id="rag-status-detail" class="text-xs text-gray-600"></div>
                            </div>
                        </div>

                        <!-- Actions -->
                        <div class="flex gap-2">
                            <button
                                onclick="attachContext()"
                                class="flex-1 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                            >
                                Attach
                            </button>
                            <button
                                onclick="detachContext()"
                                class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300 transition-colors"
                            >
                                Detach
                            </button>
                            <button
                                onclick="refreshContext()"
                                class="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                            >
                                Refresh
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Append to body
    document.body.insertAdjacentHTML('beforeend', drawerHTML);

    // Load local detection results
    refreshLocalDetect();

    // Refresh cloud provider status (Task #6)
    refreshCloudProviderStatus('openai');
    refreshCloudProviderStatus('anthropic');

    // Load context status (Task #8)
    loadContextStatus();
}

// Close Settings Drawer
function closeSettingsDrawer() {
    const drawer = document.getElementById('settings-drawer');
    if (drawer) {
        drawer.classList.add('hidden');
    }
}

// Switch drawer tab
function switchDrawerTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.drawer-tab').forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Update tab content
    document.querySelectorAll('.drawer-tab-content').forEach(content => {
        if (content.id === `drawer-tab-${tabName}`) {
            content.classList.remove('hidden');
        } else {
            content.classList.add('hidden');
        }
    });
}

// Refresh local detection (matches Providers page logic)
async function refreshLocalDetect() {
    const container = document.getElementById('local-detect-results');
    container.innerHTML = '<div class="text-center text-gray-500 text-sm py-4">Loading...</div>';

    try {
        // Use instances API to match Providers page
        const response = await fetch('/api/providers/instances');
        const data = await response.json();

        if (!data.instances || data.instances.length === 0) {
            container.innerHTML = '<div class="text-center text-gray-500 text-sm py-4">No instances configured</div>';
            return;
        }

        // Group instances by provider_id (match Providers page logic)
        const byProvider = {
            ollama: [],
            lmstudio: [],
            llamacpp: []
        };

        data.instances.forEach(inst => {
            if (byProvider[inst.provider_id]) {
                byProvider[inst.provider_id].push(inst);
            }
        });

        // Render each provider section
        const html = Object.keys(byProvider).map(providerId => {
            const instances = byProvider[providerId];

            if (instances.length === 0) {
                return ''; // Skip empty providers
            }

            const instancesHtml = instances.map(inst => {
                const stateClass = {
                    'READY': 'text-green-600',
                    'ERROR': 'text-red-600',
                    'DISCONNECTED': 'text-gray-400'
                }[inst.state] || 'text-gray-500';

                const stateBg = {
                    'READY': 'bg-green-50',
                    'ERROR': 'bg-red-50',
                    'DISCONNECTED': 'bg-gray-100'
                }[inst.state] || 'bg-gray-100';

                const stateDot = {
                    'READY': 'bg-green-500',
                    'ERROR': 'bg-red-500',
                    'DISCONNECTED': 'bg-gray-400'
                }[inst.state] || 'bg-gray-400';

                const processInfo = inst.process_running
                    ? `<span class="text-green-600">PID ${inst.process_pid}</span>`
                    : '<span class="text-gray-400">Stopped</span>';

                const modelsCount = inst.models?.length || 0;

                return `
                    <div class="border-t border-gray-200 py-2 px-3 hover:bg-gray-50">
                        <div class="flex items-center justify-between mb-1">
                            <div class="flex items-center gap-2">
                                <code class="text-xs font-mono font-semibold">${inst.instance_id}</code>
                                <div class="flex items-center gap-1.5 px-2 py-0.5 rounded ${stateBg}">
                                    <div class="w-1.5 h-1.5 rounded-full ${stateDot}"></div>
                                    <span class="text-xs font-medium ${stateClass}">${inst.state}</span>
                                </div>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
                            <div class="flex justify-between">
                                <span>Endpoint:</span>
                                <span class="text-gray-800 truncate">${inst.base_url}</span>
                            </div>
                            <div class="flex justify-between">
                                <span>Process:</span>
                                ${processInfo}
                            </div>
                            <div class="flex justify-between">
                                <span>Models:</span>
                                <span class="text-gray-800">${modelsCount}</span>
                            </div>
                            ${inst.latency_ms ? `
                                <div class="flex justify-between">
                                    <span>Latency:</span>
                                    <span class="text-gray-800">${inst.latency_ms}ms</span>
                                </div>
                            ` : ''}
                        </div>
                        ${inst.last_error ? `
                            <div class="mt-1 p-1.5 bg-red-50 rounded text-xs text-red-700">
                                <span class="material-icons md-18">warning</span> ${escapeHtml(inst.last_error)}
                            </div>
                        ` : ''}
                        <div class="mt-2 flex gap-2">
                            ${inst.has_launch_config && !inst.process_running ? `
                                <button
                                    onclick="startInstance('${inst.provider_id}', '${inst.instance_id}')"
                                    class="flex-1 px-2 py-1 text-xs font-medium text-white bg-green-600 rounded hover:bg-green-700 transition-colors"
                                >
                                    Start
                                </button>
                            ` : ''}
                            ${inst.has_launch_config && inst.process_running ? `
                                <button
                                    onclick="stopInstance('${inst.provider_id}', '${inst.instance_id}')"
                                    class="flex-1 px-2 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 transition-colors"
                                >
                                    Stop
                                </button>
                            ` : ''}
                            <button
                                onclick="testInstance('${inst.instance_key}')"
                                class="flex-1 px-2 py-1 text-xs font-medium text-gray-700 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
                            >
                                Test
                            </button>
                        </div>
                    </div>
                `;
            }).join('');

            return `
                <div class="mb-3">
                    <div class="flex items-center justify-between mb-2 px-1">
                        <h4 class="font-semibold text-sm capitalize">${providerId}</h4>
                        <span class="text-xs text-gray-500">${instances.length} instance(s)</span>
                    </div>
                    <div class="border border-gray-200 rounded-lg overflow-hidden">
                        ${instancesHtml}
                    </div>
                </div>
            `;
        }).filter(Boolean).join('');

        container.innerHTML = html || '<div class="text-center text-gray-500 text-sm py-4">No instances found</div>';

    } catch (err) {
        console.error('Failed to load local providers:', err);
        container.innerHTML = '<div class="text-center text-red-500 text-sm py-4">Error: ' + err.message + '</div>';
    }
}

// Instance control functions (match Providers page)
window.startInstance = async function(providerId, instanceId) {
    try {
        const response = await fetch(`/api/providers/${providerId}/instances/start`, withCsrfToken({
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('admin_token') || ''}`
            },
            body: JSON.stringify({ instance_id: instanceId })
        }));
        const data = await response.json();

        if (data.ok || data.status === 'started' || data.status === 'running') {
            showToast(`${instanceId} started`, 'success', 1500);
            setTimeout(() => refreshLocalDetect(), 1000);
        } else {
            showToast(`Failed to start: ${data.message || data.error}`, 'error');
        }
    } catch (err) {
        console.error(`Failed to start instance:`, err);
        showToast(`Error: ${err.message}`, 'error');
    }
};

window.stopInstance = async function(providerId, instanceId) {
    try {
        const response = await fetch(`/api/providers/${providerId}/instances/stop`, withCsrfToken({
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('admin_token') || ''}`
            },
            body: JSON.stringify({ instance_id: instanceId })
        }));
        const data = await response.json();

        if (data.ok || data.status === 'stopped' || data.status === 'not_running') {
            showToast(`${instanceId} stopped`, 'success', 1500);
            setTimeout(() => refreshLocalDetect(), 500);
        } else {
            showToast(`Failed to stop: ${data.message || data.error}`, 'error');
        }
    } catch (err) {
        console.error(`Failed to stop instance:`, err);
        showToast(`Error: ${err.message}`, 'error');
    }
};

window.testInstance = async function(instanceKey) {
    try {
        showToast(`Refreshing ${instanceKey}...`, 'info', 800);

        // Just refresh instances to get latest state
        await refreshLocalDetect();

        showToast('Status refreshed', 'success', 1000);
    } catch (err) {
        console.error(`Failed to refresh instance:`, err);
        showToast(`Refresh failed: ${err.message}`, 'error');
    }
};

// Run self-check (Task #7)
async function runSelfCheck() {
    const btn = document.getElementById('selfcheck-btn');
    btn.disabled = true;
    btn.textContent = 'Checking...';

    try {
        // Call self-check API
        const response = await fetch('/api/selfcheck', withCsrfToken({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.currentSession,
                include_network: true,  // Actively probe all providers for accurate status
                include_context: true,
            }),
        }));

        const result = await response.json();

        // Open results drawer
        openSelfCheckDrawer(result);
    } catch (err) {
        console.error('Self-check failed:', err);
        Dialog.alert('Self-check failed: ' + err.message, { title: 'Self-check Error' });
    } finally {
        btn.disabled = false;
        btn.textContent = 'Self-check';
    }
}

// Open Self-check Results Drawer (Task #7)
function openSelfCheckDrawer(result) {
    // Close existing drawer if any
    const existing = document.getElementById('selfcheck-drawer');
    if (existing) {
        existing.remove();
    }

    // Determine summary badge color
    let summaryBadge = '';
    if (result.summary === 'OK') {
        summaryBadge = '<span class="badge success"><span class="material-icons md-18">check</span> ALL PASS</span>';
    } else if (result.summary === 'WARN') {
        summaryBadge = '<span class="badge warning"><span class="material-icons md-18">warning</span> WARNINGS</span>';
    } else {
        summaryBadge = '<span class="badge error"><span class="material-icons md-18">cancel</span> FAILURES</span>';
    }

    // Add version badge if available
    const versionBadge = result.version ? `<span class="badge" style="background: #6366f1; color: white; margin-left: 8px;">${result.version}</span>` : '';

    const drawerHTML = `
        <div id="selfcheck-drawer" class="fixed inset-0 z-50">
            <!-- Backdrop -->
            <div class="absolute inset-0 bg-black bg-opacity-50" onclick="closeSelfCheckDrawer()"></div>

            <!-- Drawer -->
            <div class="absolute right-0 top-0 h-full w-[600px] bg-white shadow-xl flex flex-col">
                <!-- Header -->
                <div class="p-4 border-b border-gray-200">
                    <div class="flex items-center justify-between mb-2">
                        <h2 class="text-lg font-semibold text-gray-900">System Self-check</h2>
                        <button
                            onclick="closeSelfCheckDrawer()"
                            class="p-1 hover:bg-gray-100 rounded-lg transition-colors"
                        >
                            <svg class="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    </div>
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            ${summaryBadge}
                            ${versionBadge}
                            <span class="text-xs text-gray-500">${new Date(result.ts).toLocaleTimeString()}</span>
                        </div>
                        <button
                            onclick="runSelfCheck(); closeSelfCheckDrawer();"
                            class="text-xs px-3 py-1 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                        >
                            Re-run
                        </button>
                    </div>
                </div>

                <!-- Filters -->
                <div class="flex gap-2 p-4 border-b border-gray-200">
                    <button
                        class="selfcheck-filter active px-3 py-1 text-sm rounded-lg"
                        data-filter="all"
                        onclick="filterSelfCheckResults('all')"
                    >
                        All (${result.items.length})
                    </button>
                    <button
                        class="selfcheck-filter px-3 py-1 text-sm rounded-lg"
                        data-filter="fail"
                        onclick="filterSelfCheckResults('fail')"
                    >
                        Fail (${result.items.filter(i => i.status === 'FAIL').length})
                    </button>
                    <button
                        class="selfcheck-filter px-3 py-1 text-sm rounded-lg"
                        data-filter="warn"
                        onclick="filterSelfCheckResults('warn')"
                    >
                        Warn (${result.items.filter(i => i.status === 'WARN').length})
                    </button>
                </div>

                <!-- Results -->
                <div class="flex-1 overflow-y-auto p-4">
                    <div id="selfcheck-results" class="space-y-3">
                        ${renderSelfCheckItems(result.items)}
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', drawerHTML);

    // Store results for filtering
    window._selfCheckResults = result.items;
}

// Render self-check items (Task #7)
function renderSelfCheckItems(items) {
    // Enhanced empty state guidance (Phase C3)
    if (items.length === 0) {
        return `
            <div class="text-center text-gray-500 py-8">
                <div class="text-4xl mb-3"><span class="material-icons md-36">search</span></div>
                <p class="text-sm font-medium">No checks available</p>
                <p class="text-xs mt-1">Run self-check to diagnose system health</p>
            </div>
        `;
    }

    return items.map(item => {
        let icon = '';
        let statusColor = '';
        let bgColor = '';
        let pulseClass = '';  // Phase C3: Add pulse animation for FAIL

        if (item.status === 'PASS') {
            icon = '<span class="material-icons md-18">check</span>';
            statusColor = 'text-green-700';
            bgColor = 'bg-green-50';
        } else if (item.status === 'WARN') {
            icon = '<span class="material-icons md-18">warning</span>';
            statusColor = 'text-yellow-700';
            bgColor = 'bg-yellow-50';
        } else {
            icon = '<span class="material-icons md-18">cancel</span>';
            statusColor = 'text-red-700';
            bgColor = 'bg-red-50';
            pulseClass = 'animate-pulse';  // Phase C3: Red pulse for FAIL
        }

        const actionsHTML = item.actions && item.actions.length > 0
            ? `<div class="mt-2 flex gap-2">
                ${item.actions.map(action => {
                    if (action.method && action.path) {
                        // API action
                        return `<button
                            onclick="executeSelfCheckAction('${action.method}', '${action.path}')"
                            class="px-3 py-1 text-xs font-medium text-white bg-blue-600 rounded hover:bg-blue-700 transition-colors"
                        >
                            ${escapeHtml(action.label)}
                        </button>`;
                    } else if (action.ui) {
                        // UI action
                        return `<button
                            onclick="executeSelfCheckUIAction('${action.ui}')"
                            class="px-3 py-1 text-xs font-medium text-gray-700 bg-gray-200 rounded hover:bg-gray-300 transition-colors"
                        >
                            ${escapeHtml(action.label)}
                        </button>`;
                    }
                    return '';
                }).join('')}
            </div>`
            : '';

        return `
            <div class="border border-gray-200 rounded-lg p-3 selfcheck-item" data-status="${item.status.toLowerCase()}">
                <div class="flex items-start gap-3">
                    <div class="flex-shrink-0 w-6 h-6 rounded-full ${bgColor} ${pulseClass} flex items-center justify-center">
                        <span class="${statusColor} text-sm font-bold">${icon}</span>
                    </div>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-start justify-between">
                            <h4 class="font-medium text-sm text-gray-900">${escapeHtml(item.name)}</h4>
                            <span class="badge ${item.status === 'PASS' ? 'success' : item.status === 'WARN' ? 'warning' : 'error'} ml-2">
                                ${item.status}
                            </span>
                        </div>
                        <p class="text-xs text-gray-600 mt-1">${escapeHtml(item.detail)}</p>
                        ${item.hint ? `<p class="text-xs text-blue-600 mt-1">lightbulb ${escapeHtml(item.hint)}</p>` : ''}
                        ${actionsHTML}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Filter self-check results (Task #7)
function filterSelfCheckResults(filter) {
    // Update filter buttons
    document.querySelectorAll('.selfcheck-filter').forEach(btn => {
        if (btn.dataset.filter === filter) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Filter items
    const items = document.querySelectorAll('.selfcheck-item');
    items.forEach(item => {
        const status = item.dataset.status;
        if (filter === 'all') {
            item.style.display = 'block';
        } else if (filter === status) {
            item.style.display = 'block';
        } else {
            item.style.display = 'none';
        }
    });
}

// Execute self-check action (Task #7)
async function executeSelfCheckAction(method, path) {
    try {
        const response = await fetch(path, {
            method: method,
        });

        if (response.ok) {
            // Action succeeded - refresh self-check and provider status
            setTimeout(() => {
                runSelfCheck();
                closeSelfCheckDrawer();
                refreshProviderStatus();
            }, 1000);
        } else {
            Dialog.alert('Action failed: ' + response.statusText, { title: 'Action Error' });
        }
    } catch (err) {
        console.error('Failed to execute action:', err);
        Dialog.alert('Action failed: ' + err.message, { title: 'Action Error' });
    }
}

// Execute UI action (Task #7)
function executeSelfCheckUIAction(uiAction) {
    if (uiAction === 'drawer.cloud') {
        closeSelfCheckDrawer();
        openSettingsDrawer();
        switchDrawerTab('cloud-config');
    }
}

// Close self-check drawer (Task #7)
function closeSelfCheckDrawer() {
    const drawer = document.getElementById('selfcheck-drawer');
    if (drawer) {
        drawer.remove();
    }
}

// Render other views (placeholders)
function renderOverviewView(container) {
    container.innerHTML = `
        <div class="p-6">
            <h3 class="text-lg font-semibold mb-4">System Overview</h3>
            <div id="overview-content" class="text-gray-600">Loading...</div>
        </div>
    `;

    loadOverview();
}

async function loadOverview() {
    try {
        const response = await fetch('/api/health');
        const health = await response.json();

        // Fetch governance data (optional, graceful degradation)
        let governanceHtml = '';
        try {
            const govResponse = await fetch('/api/governance/dashboard?timeframe=7d');
            if (govResponse.ok) {
                const govData = await govResponse.json();
                const metrics = govData.metrics || {};
                const riskLevel = metrics.risk_level || 'UNKNOWN';
                const openFindings = metrics.open_findings || 0;
                const riskColor = riskLevel === 'HIGH' || riskLevel === 'CRITICAL' ? 'error' :
                                 riskLevel === 'MEDIUM' ? 'warning' : 'success';

                governanceHtml = `
                    <div class="bg-white border border-gray-200 rounded-lg p-4">
                        <h4 class="font-semibold mb-2">Governance Status</h4>
                        <div class="space-y-2">
                            <div class="flex justify-between">
                                <span class="text-gray-600">Risk Level:</span>
                                <span class="badge ${riskColor}">${riskLevel}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Open Findings:</span>
                                <span class="${openFindings > 0 ? 'text-orange-600 font-semibold' : ''}">${openFindings}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-gray-600">Blocked Rate:</span>
                                <span>${((metrics.blocked_rate || 0) * 100).toFixed(1)}%</span>
                            </div>
                            <div class="mt-3">
                                <a href="#" data-view="governance-dashboard" class="text-sm text-blue-600 hover:text-blue-800 nav-link-inline">
                                    View Governance Dashboard →
                                </a>
                            </div>
                        </div>
                    </div>
                `;
            }
        } catch (govErr) {
            console.warn('Governance data not available:', govErr.message);
        }

        const content = document.getElementById('overview-content');
        content.innerHTML = `
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="bg-white border border-gray-200 rounded-lg p-4">
                    <h4 class="font-semibold mb-2">System Status</h4>
                    <div class="space-y-2">
                        <div class="flex justify-between">
                            <span class="text-gray-600">Status:</span>
                            <span class="badge ${health.status === 'ok' ? 'success' : 'error'}">${health.status.toUpperCase()}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">Uptime:</span>
                            <span>${Math.floor(health.uptime_seconds / 60)} minutes</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">PID:</span>
                            <span>${health.metrics.pid}</span>
                        </div>
                    </div>
                </div>

                <div class="bg-white border border-gray-200 rounded-lg p-4">
                    <h4 class="font-semibold mb-2">Resource Usage</h4>
                    <div class="space-y-2">
                        <div class="flex justify-between">
                            <span class="text-gray-600">CPU:</span>
                            <span>${health.metrics.cpu_percent.toFixed(1)}%</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">Memory:</span>
                            <span>${health.metrics.memory_mb.toFixed(1)} MB</span>
                        </div>
                    </div>
                </div>

                <div class="bg-white border border-gray-200 rounded-lg p-4">
                    <h4 class="font-semibold mb-2">Components</h4>
                    <div class="space-y-2">
                        ${Object.entries(health.components).map(([name, status]) => `
                            <div class="flex justify-between">
                                <span class="text-gray-600">${name}:</span>
                                <span class="badge ${status === 'ok' ? 'success' : 'error'}">${status.toUpperCase()}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div class="bg-white border border-gray-200 rounded-lg p-4">
                    <h4 class="font-semibold mb-2">System Info</h4>
                    <div class="space-y-2">
                        <div class="flex justify-between">
                            <span class="text-gray-600">Version:</span>
                            <span>0.3.0</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">API:</span>
                            <span class="badge success">ONLINE</span>
                        </div>
                    </div>
                </div>

                ${governanceHtml}
            </div>
        `;

        // Attach click handlers to inline nav links
        document.querySelectorAll('.nav-link-inline').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const view = link.dataset.view;
                if (view) {
                    updateNavigationActive(view);
                    loadView(view);
                }
            });
        });
    } catch (err) {
        document.getElementById('overview-content').innerHTML = `<div class="text-red-600">Error: ${err.message}</div>`;
    }
}

// Render Sessions View (PR-3: First-class citizen)
function renderSessionsView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new SessionsView(container);
}

async function loadSessionsList() {
    try {
        const response = await fetch('/api/sessions');
        const sessions = await response.json();

        const content = document.getElementById('sessions-content');

        if (sessions.length === 0) {
            content.innerHTML = '<div class="text-gray-500">No sessions available</div>';
            return;
        }

        const html = sessions.map(session => `
            <div class="bg-white border border-gray-200 rounded-lg p-4 mb-4">
                <div class="flex items-center justify-between mb-2">
                    <h4 class="font-semibold">${session.title}</h4>
                    <span class="text-xs text-gray-500">${session.id}</span>
                </div>
                <div class="text-sm text-gray-600 mb-2">
                    Created: ${new Date(session.created_at).toLocaleString()}
                </div>
                ${session.tags && session.tags.length > 0 ? `
                    <div class="flex gap-2 flex-wrap">
                        ${session.tags.map(tag => `<span class="badge info">${tag}</span>`).join('')}
                    </div>
                ` : ''}
            </div>
        `).join('');

        content.innerHTML = html;
    } catch (err) {
        document.getElementById('sessions-content').innerHTML = `<div class="text-red-600">Error: ${err.message}</div>`;
    }
}

// Render Projects View (Phase 6.2: Multi-repository)
function renderProjectsView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new ProjectsView(container);
}

// Render Tasks View (PR-2: Observability)
function renderTasksView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new TasksView(container);
}

// Render Events View (PR-2: Observability)
function renderEventsView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new EventsView(container);
}

// Render Pipeline View (PR-V4: Pipeline Visualization)
function renderPipelineView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Get task ID from URL hash or prompt user
    const urlParams = new URLSearchParams(window.location.hash.split('?')[1] || '');
    const taskId = urlParams.get('task_id');

    if (!taskId) {
        // Show task selector
        container.innerHTML = `
            <div class="p-8">
                <h2 class="text-2xl font-bold mb-4">Pipeline Visualization</h2>
                <p class="text-gray-600 mb-4">Enter a task ID to visualize its execution pipeline:</p>
                <div class="flex gap-4 max-w-md">
                    <input
                        type="text"
                        id="pipeline-task-id-input"
                        placeholder="task_abc123..."
                        class="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                        id="pipeline-load-btn"
                        class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                        Load
                    </button>
                </div>
            </div>
        `;

        const input = container.querySelector('#pipeline-task-id-input');
        const btn = container.querySelector('#pipeline-load-btn');

        btn.addEventListener('click', () => {
            const taskId = input.value.trim();
            if (taskId) {
                window.location.hash = `#pipeline?task_id=${taskId}`;
                loadView('pipeline');
            }
        });

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                btn.click();
            }
        });

        return;
    }

    // Create new view instance
    state.currentViewInstance = new PipelineView(container, taskId);
}

// Render Logs View (PR-2: Observability - Updated)
function renderLogsView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new LogsView(container);
}

// History View
function renderHistoryView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new HistoryView(container);
}

async function loadLogs() {
    try {
        const response = await fetch('/api/logs?limit=100');
        const logs = await response.json();

        const content = document.getElementById('logs-content');

        if (logs.length === 0) {
            content.innerHTML = '<div class="text-gray-500">No logs available</div>';
            return;
        }

        const html = `
            <div class="bg-white border border-gray-200 rounded-lg overflow-hidden">
                <div class="overflow-y-auto" style="max-height: 600px;">
                    <table class="min-w-full divide-y divide-gray-200">
                        <thead class="bg-gray-50 sticky top-0">
                            <tr>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Level</th>
                                <th class="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Message</th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            ${logs.map(log => `
                                <tr>
                                    <td class="px-4 py-2 text-xs text-gray-500 whitespace-nowrap">
                                        ${new Date(log.timestamp).toLocaleTimeString()}
                                    </td>
                                    <td class="px-4 py-2 whitespace-nowrap">
                                        <span class="badge ${log.level === 'ERROR' ? 'error' : log.level === 'WARNING' ? 'warn' : 'info'}">
                                            ${log.level}
                                        </span>
                                    </td>
                                    <td class="px-4 py-2 text-sm text-gray-900">
                                        ${escapeHtml(log.message)}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        content.innerHTML = html;
    } catch (err) {
        document.getElementById('logs-content').innerHTML = `<div class="text-red-600">Error: ${err.message}</div>`;
    }
}

// PR-4: Skills View (Updated for PR-0201-2026-6: Marketplace UX)
function renderSkillsView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new marketplace view instance
    // Use SkillsMarketplaceView if available, otherwise fall back to SkillsView
    const ViewClass = window.SkillsMarketplaceView || window.SkillsView;
    state.currentViewInstance = new ViewClass(container);
}

// PR-4: Memory View
function renderMemoryView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new MemoryView(container);
}

// Task #18: Memory Proposals View
function renderMemoryProposalsView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new MemoryProposalsView(container);
    state.currentViewInstance.render();
}

// Task #13: Memory Timeline View (audit trail)
function renderMemoryTimelineView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new MemoryTimelineView(container);
}

// Render Voice View
function renderVoiceView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new VoiceView(container);
}

// Global navigation helper (PR-2: Cross-view navigation + PR-3: Chat session binding)
window.navigateToView = function(viewName, filters = {}) {
    // Update navigation state
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        if (item.dataset.view === viewName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // PR-3: Special handling for chat with session_id
    if (viewName === 'chat' && filters.session_id) {
        const targetSession = filters.session_id;

        // Load the view first
        loadView(viewName);

        // Then switch to the target session
        setTimeout(() => {
            switchSession(targetSession);
        }, 100);

        return;
    }

    // Load the view
    loadView(viewName);

    // If the view has filters to apply, wait for it to load then apply them
    if (Object.keys(filters).length > 0) {
        setTimeout(() => {
            if (state.currentViewInstance && state.currentViewInstance.filterBar) {
                // Update filter bar state
                Object.assign(state.currentViewInstance.currentFilters, filters);

                // Trigger reload with filters
                if (state.currentViewInstance.loadTasks) {
                    state.currentViewInstance.loadTasks();
                } else if (state.currentViewInstance.loadEvents) {
                    state.currentViewInstance.loadEvents();
                } else if (state.currentViewInstance.loadLogs) {
                    state.currentViewInstance.loadLogs();
                } else if (state.currentViewInstance.loadSessions) {
                    state.currentViewInstance.loadSessions();
                }
            }
        }, 100);
    }
};

// PR-4: Config View
function renderConfigView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new ConfigView(container);
}

// PR-5: Context View
function renderContextView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new ContextView(container);
}

// PR-5: Runtime View
function renderRuntimeView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new RuntimeView(container);
}

// PR-5: Support View
function renderSupportView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new SupportView(container);
}

function renderKnowledgePlaygroundView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new KnowledgePlaygroundView(container);
}

function renderKnowledgeSourcesView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new KnowledgeSourcesView(container);
}

function renderKnowledgeJobsView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new KnowledgeJobsView(container);
}

function renderKnowledgeHealthView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new KnowledgeHealthView(container);
}

// Governance Dashboard View (Task #6: Dashboard Main View)
function renderGovernanceDashboardView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new GovernanceDashboardView();
    state.currentViewInstance.render(container);
}

// Governance Findings View (PR-4: Lead Agent)
function renderGovernanceFindingsView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new GovernanceFindingsView(container);
}

// Lead Scan History View (PR-4: Lead Agent Risk Mining)
function renderLeadScanHistoryView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new LeadScanHistoryView(container);
}

// Governance View (PR-2: WebUI Views - Task 1)
function renderGovernanceView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new GovernanceView();
    state.currentViewInstance.render(container);
}

// Quota View (PR-2: WebUI Views - Task 2)
function renderQuotaView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new QuotaView();
    state.currentViewInstance.render(container);
}

// Trust Tier View (PR-2: WebUI Views - Task 3)
function renderTrustTierView(container, highlightTier = null) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new TrustTierView();
    state.currentViewInstance.render(container, highlightTier);
}

// Provenance View (PR-2: WebUI Views - Task 4)
function renderProvenanceView(container, invocationId = null) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new ProvenanceView();
    state.currentViewInstance.render(container, invocationId);
}

// Snippets View
function renderSnippetsView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new SnippetsView(container);
}

// Health check
function startHealthCheck() {
    updateHealth();

    state.healthCheckInterval = setInterval(() => {
        updateHealth();
    }, 10000); // Every 10 seconds
}

async function updateHealth() {
    try {
        const response = await fetch('/api/health');
        const health = await response.json();

        const badge = document.getElementById('health-badge');
        if (!badge) return; // Element not in current view

        const text = badge.querySelector('span');

        // Remove old classes
        badge.classList.remove('ok', 'warn', 'down');

        // Add new class
        badge.classList.add(health.status);

        // Update text
        text.textContent = health.status.toUpperCase();

    } catch (err) {
        const badge = document.getElementById('health-badge');
        if (!badge) return; // Element not in current view

        badge.classList.remove('ok', 'warn');
        badge.classList.add('down');

        const text = badge.querySelector('span');
        text.textContent = 'DOWN';
    }
}

// Governance badge updates
function startGovernanceBadgeUpdates() {
    updateGovernanceBadge();

    // Update every 5 minutes
    setInterval(() => {
        updateGovernanceBadge();
    }, 5 * 60 * 1000);

    // Also start proposals badge updates (Task #18)
    updateProposalsBadge();
    setInterval(() => {
        updateProposalsBadge();
    }, 30 * 1000); // Update every 30 seconds
}

async function updateGovernanceBadge() {
    try {
        const response = await fetch('/api/governance/dashboard?timeframe=7d');
        if (!response.ok) return; // Silently fail if governance not available

        const data = await response.json();
        const metrics = data.metrics || {};
        const openFindings = metrics.open_findings || 0;

        const badge = document.getElementById('governance-badge');
        if (!badge) return; // Element not in current view

        if (openFindings > 0) {
            badge.textContent = openFindings;
            badge.style.display = 'inline-block';

            // Change badge color based on risk level
            const riskLevel = metrics.risk_level || 'LOW';
            badge.classList.remove('badge-warning', 'badge-error', 'badge-success');
            if (riskLevel === 'HIGH' || riskLevel === 'CRITICAL') {
                badge.classList.add('badge-error');
            } else if (riskLevel === 'MEDIUM') {
                badge.classList.add('badge-warning');
            } else {
                badge.classList.add('badge-success');
            }
        } else {
            badge.style.display = 'none';
        }
    } catch (err) {
        // Silently fail - governance is optional
        console.debug('Governance badge update failed:', err.message);
    }
}

// Task #18: Memory Proposals badge updates
async function updateProposalsBadge() {
    try {
        const response = await fetch('/api/memory/proposals/stats?agent_id=user:current');
        if (!response.ok) return; // Silently fail if proposals not available

        const stats = await response.json();
        const pending = stats.pending || 0;

        const badge = document.getElementById('proposals-badge');
        if (!badge) return; // Element not in current view

        if (pending > 0) {
            badge.textContent = pending;
            badge.style.display = 'inline-block';
        } else {
            badge.style.display = 'none';
        }
    } catch (err) {
        // Silently fail - proposals is optional
        console.debug('Proposals badge update failed:', err.message);
    }
}

// ============================================================================
// Chat Health Check - Lightweight health check for chat functionality
// ============================================================================

/**
 * Lightweight Chat Health Check
 * Uses the new /api/selfcheck/chat-health endpoint
 * Only checks minimum requirements for Chat, not full system diagnostics
 */
async function checkChatHealth() {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000); // 2 second timeout

        const response = await fetch('/api/selfcheck/chat-health', {
            method: 'GET',
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            return {
                is_healthy: false,
                issues: ['Health check API failed'],
                hints: ['Check system status']
            };
        }

        const data = await response.json();
        return data;
    } catch (err) {
        console.error('Chat health check failed:', err);
        return {
            is_healthy: false,
            issues: ['Health check failed'],
            hints: ['Check network connection']
        };
    }
}

/**
 * Display Chat Health Warning Banner
 * Shows a friendly warning at the top of the chat messages area
 */
function showChatHealthWarning(issues, hints) {
    const messagesDiv = document.getElementById('messages');
    if (!messagesDiv) return;

    // Remove any existing warning banner
    const existingWarning = document.getElementById('chat-health-warning');
    if (existingWarning) {
        existingWarning.remove();
    }

    const warningBanner = document.createElement('div');
    warningBanner.id = 'chat-health-warning';
    warningBanner.className = 'chat-health-warning';
    warningBanner.innerHTML = `
        <div style="background: #fff3cd; border: 1px solid #ffc107; padding: 12px; margin: 0 0 16px 0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <svg style="width: 20px; height: 20px; color: #ff9800;" fill="currentColor" viewBox="0 0 20 20">
                    <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                </svg>
                <strong style="color: #856404; font-size: 14px;">Chat Not Available</strong>
            </div>
            <div style="margin: 8px 0; font-size: 13px; color: #856404;">
                ${issues.map(issue => `• ${issue}`).join('<br>')}
            </div>
            ${hints.length > 0 ? `
                <div style="margin: 8px 0 12px 0; font-size: 13px; color: #856404; background: rgba(255, 193, 7, 0.1); padding: 8px; border-radius: 4px;">
                    <strong>lightbulb Suggestions:</strong><br>
                    ${hints.map(hint => `• ${hint}`).join('<br>')}
                </div>
            ` : ''}
            <div style="display: flex; gap: 8px; margin-top: 12px;">
                <button
                    onclick="navigateToView('providers')"
                    style="padding: 6px 12px; font-size: 13px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500;"
                    onmouseover="this.style.background='#0056b3'"
                    onmouseout="this.style.background='#007bff'"
                >
                    Configure Providers
                </button>
                <button
                    onclick="runSelfCheck()"
                    style="padding: 6px 12px; font-size: 13px; background: #6c757d; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 500;"
                    onmouseover="this.style.background='#5a6268'"
                    onmouseout="this.style.background='#6c757d'"
                >
                    Run Full Diagnostics
                </button>
                <button
                    onclick="document.getElementById('chat-health-warning').remove()"
                    style="padding: 6px 12px; font-size: 13px; background: transparent; color: #856404; border: 1px solid #ffc107; border-radius: 4px; cursor: pointer; font-weight: 500;"
                    onmouseover="this.style.background='rgba(255, 193, 7, 0.1)'"
                    onmouseout="this.style.background='transparent'"
                >
                    Dismiss
                </button>
            </div>
        </div>
    `;

    // Insert at the top of messages area
    messagesDiv.insertBefore(warningBanner, messagesDiv.firstChild);
}

/**
 * Initialize Chat Health Check
 * Called when Chat view is loaded to check system readiness
 */
async function initChatHealthCheck() {
    const health = await checkChatHealth();

    if (!health.is_healthy) {
        console.warn('Chat health check failed:', health);
        showChatHealthWarning(health.issues || [], health.hints || []);
    } else {
        console.log('Chat health check passed');
        // Remove any existing warning banner if health is restored
        const existingWarning = document.getElementById('chat-health-warning');
        if (existingWarning) {
            existingWarning.remove();
        }
    }
}

// Utility function
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cloud Provider Config Functions (Task #6)

// Save and test cloud provider
async function saveAndTestCloudProvider(providerId) {
    const apiKeyInput = document.getElementById(`${providerId}-api-key`);
    const baseUrlInput = document.getElementById(`${providerId}-base-url`);
    const resultDiv = document.getElementById(`${providerId}-test-result`);

    const apiKey = apiKeyInput.value.trim();
    if (!apiKey) {
        Dialog.alert('API Key is required', { title: 'Validation Error' });
        return;
    }

    // Show loading state
    resultDiv.innerHTML = '<div class="p-2 bg-blue-50 rounded text-blue-700">Saving and testing...</div>';
    resultDiv.classList.remove('hidden');

    try {
        // Save configuration
        const response = await fetch('/api/providers/cloud/config', withCsrfToken({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider_id: providerId,
                auth: {
                    type: 'api_key',
                    api_key: apiKey,
                },
                base_url: baseUrlInput.value.trim() || null,
            }),
        }));

        const data = await response.json();

        if (data.ok) {
            // Test was automatically triggered on save
            // Refresh provider status to get latest state
            setTimeout(async () => {
                await refreshCloudProviderStatus(providerId);

                // Clear sensitive input
                apiKeyInput.value = '';

                resultDiv.innerHTML = '<div class="p-2 bg-green-50 rounded text-green-700"><span class="material-icons md-18">check</span> Configuration saved and tested successfully!</div>';

                // Refresh toolbar status
                refreshProviderStatus();

                // Hide result after 3s
                setTimeout(() => {
                    resultDiv.classList.add('hidden');
                }, 3000);
            }, 500);
        } else {
            resultDiv.innerHTML = `<div class="p-2 bg-red-50 rounded text-red-700"><span class="material-icons md-18">cancel</span> ${data.message || 'Failed to save'}</div>`;
        }
    } catch (err) {
        console.error('Failed to save cloud config:', err);
        resultDiv.innerHTML = `<div class="p-2 bg-red-50 rounded text-red-700"><span class="material-icons md-18">cancel</span> Error: ${err.message}</div>`;
    }
}

// Refresh cloud provider status display
async function refreshCloudProviderStatus(providerId) {
    try {
        const response = await fetch('/api/providers/status');
        const data = await response.json();

        const providerStatus = data.providers.find(p => p.id === providerId);
        if (providerStatus) {
            updateCloudProviderStatusUI(providerId, providerStatus);
        }
    } catch (err) {
        console.error('Failed to refresh cloud provider status:', err);
    }
}

// Update cloud provider status UI
function updateCloudProviderStatusUI(providerId, status) {
    const statusDiv = document.getElementById(`${providerId}-status`);
    if (!statusDiv) return;

    const dot = statusDiv.querySelector('.w-2');
    const text = statusDiv.querySelector('span');

    // Remove old classes
    statusDiv.classList.remove('bg-gray-100', 'bg-green-50', 'bg-red-50', 'bg-yellow-50');
    dot.classList.remove('bg-gray-400', 'bg-green-500', 'bg-red-500', 'bg-yellow-500', 'animate-pulse');

    // Build tooltip with reason_code + hint (Phase C3)
    let tooltip = '';
    if (status.last_error) {
        tooltip = status.last_error;
        if (status.reason_code) {
            tooltip += `\n[${status.reason_code}]`;
        }
        if (status.hint) {
            tooltip += `\n\nlightbulb ${status.hint}`;
        }
    }

    switch (status.state) {
        case 'READY':
            statusDiv.classList.add('bg-green-50');
            dot.classList.add('bg-green-500');
            text.className = 'text-xs font-medium text-green-700';
            const latencyText = status.latency_ms ? ` (${Math.round(status.latency_ms)}ms)` : '';
            text.textContent = `Ready${latencyText}`;
            if (status.last_ok_at) {
                statusDiv.title = `Last checked: ${formatTimestamp(status.last_ok_at)}`;
            }
            break;
        case 'DISCONNECTED':
            statusDiv.classList.add('bg-gray-100');
            dot.classList.add('bg-gray-400');
            text.className = 'text-xs font-medium text-gray-600';
            text.textContent = 'Not configured';
            statusDiv.title = tooltip || 'Add API key in Settings';
            break;
        case 'ERROR':
            statusDiv.classList.add('bg-red-50');
            dot.classList.add('bg-red-500');
            // Red pulse animation for errors (Phase C3)
            dot.classList.add('animate-pulse');
            text.className = 'text-xs font-medium text-red-700';
            text.textContent = 'Error';
            statusDiv.title = tooltip || 'Connection failed';
            break;
        case 'DEGRADED':
            statusDiv.classList.add('bg-yellow-50');
            dot.classList.add('bg-yellow-500');
            text.className = 'text-xs font-medium text-yellow-700';
            text.textContent = 'Degraded';
            statusDiv.title = tooltip || 'Partial service';
            break;
    }
}

// Format timestamp for display (Phase C3)
// Task #14: Added defensive timezone validation
function formatTimestamp(isoString) {
    if (!isoString) return 'Unknown';

    try {
        // Defensive check: warn if ISO format lacks timezone marker
        if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(isoString)) {
            const hasTimezone = isoString.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(isoString);

            if (!hasTimezone) {
                // Development environment warning
                if (typeof process !== 'undefined' && process.env && process.env.NODE_ENV === 'development') {
                    console.warn(`[formatTimestamp] Timestamp without timezone: ${isoString}. Assuming UTC.`);
                } else if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                    // Simple local environment detection
                    console.warn(`[formatTimestamp] Timestamp without timezone: ${isoString}. Assuming UTC.`);
                }

                // Force add Z (treat as UTC)
                isoString = isoString + 'Z';
            }
        }

        const date = new Date(isoString);

        // Validate timestamp
        if (isNaN(date.getTime())) {
            console.error(`[formatTimestamp] Invalid timestamp: ${isoString}`);
            return 'Invalid Date';
        }

        const now = new Date();
        const diffMs = now - date;
        const diffSec = Math.floor(diffMs / 1000);

        // Relative time display (seconds, minutes, hours)
        if (diffSec < 60) return `${diffSec}s ago`;
        else if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
        else if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
        else return date.toLocaleDateString();
    } catch (e) {
        console.error(`[formatTimestamp] Error parsing timestamp: ${isoString}`, e);
        return 'Unknown';
    }
}

// Clear cloud provider config
async function clearCloudProvider(providerId) {
    const confirmed = await Dialog.confirm(`Remove configuration for ${providerId}?`, {
        title: 'Remove Configuration',
        confirmText: 'Remove',
        danger: true
    });
    if (!confirmed) {
        return;
    }

    const resultDiv = document.getElementById(`${providerId}-test-result`);
    resultDiv.innerHTML = '<div class="p-2 bg-blue-50 rounded text-blue-700">Clearing...</div>';
    resultDiv.classList.remove('hidden');

    try {
        const response = await fetch(`/api/providers/cloud/config/${providerId}`, withCsrfToken({
            method: 'DELETE',
        }));

        const data = await response.json();

        if (data.ok) {
            // Clear inputs
            document.getElementById(`${providerId}-api-key`).value = '';
            document.getElementById(`${providerId}-base-url`).value = '';

            resultDiv.innerHTML = '<div class="p-2 bg-green-50 rounded text-green-700"><span class="material-icons md-18">check</span> Configuration cleared</div>';

            // Refresh status
            setTimeout(async () => {
                await refreshCloudProviderStatus(providerId);
                refreshProviderStatus();

                setTimeout(() => {
                    resultDiv.classList.add('hidden');
                }, 2000);
            }, 500);
        } else {
            resultDiv.innerHTML = `<div class="p-2 bg-yellow-50 rounded text-yellow-700">${data.message}</div>`;
        }
    } catch (err) {
        console.error('Failed to clear cloud config:', err);
        resultDiv.innerHTML = `<div class="p-2 bg-red-50 rounded text-red-700"><span class="material-icons md-18">cancel</span> Error: ${err.message}</div>`;
    }
}

// Context Management Functions (Task #8)

// Load context status for current session
async function loadContextStatus() {
    const sessionId = state.currentSession;

    // Skip if no valid session
    if (!sessionId) {
        console.warn('Cannot load context status: No active session');
        return;
    }

    try {
        const response = await fetch(`/api/context/status?session_id=${sessionId}`);
        const data = await response.json();

        // Update context status summary
        updateContextStatusSummary(data);

        // Update form fields (only if elements exist - they're in Context view)
        const memoryEnabled = data.memory && data.memory.enabled;
        const ragEnabled = data.rag && data.rag.enabled;

        const memoryEnabledEl = document.getElementById('memory-enabled');
        const ragEnabledEl = document.getElementById('rag-enabled');
        const memoryNamespaceEl = document.getElementById('memory-namespace');
        const ragIndexEl = document.getElementById('rag-index');

        if (memoryEnabledEl) {
            memoryEnabledEl.checked = memoryEnabled;
        }
        if (ragEnabledEl) {
            ragEnabledEl.checked = ragEnabled;
        }

        if (memoryNamespaceEl) {
            if (memoryEnabled && data.memory.namespace) {
                memoryNamespaceEl.value = data.memory.namespace;
            } else {
                memoryNamespaceEl.value = sessionId;
            }
        }

        if (ragIndexEl && ragEnabled && data.rag.index) {
            ragIndexEl.value = data.rag.index;
        }

        // Update detail displays (only if functions are available)
        if (typeof updateMemoryStatusDetail === 'function') {
            updateMemoryStatusDetail(data.memory);
        }
        if (typeof updateRagStatusDetail === 'function') {
            updateRagStatusDetail(data.rag);
        }

        // Update toolbar context pill
        updateContextStatus(data.state);
    } catch (err) {
        console.error('Failed to load context status:', err);
    }
}

// Update context status summary display
function updateContextStatusSummary(data) {
    const summaryDiv = document.getElementById('context-status-summary');
    if (!summaryDiv) return;

    let stateColor = 'gray';
    let stateIcon = '<span class="material-icons md-18">fiber_manual_record</span>';

    if (data.state === 'ATTACHED') {
        stateColor = 'green';
        stateIcon = '<span class="material-icons md-18">check</span>';
    } else if (data.state === 'BUILDING') {
        stateColor = 'blue';
        stateIcon = '<span class="material-icons md-18">refresh</span>';
    } else if (data.state === 'STALE') {
        stateColor = 'yellow';
        stateIcon = '<span class="material-icons md-18">warning</span>';
    } else if (data.state === 'ERROR') {
        stateColor = 'red';
        stateIcon = '<span class="material-icons md-18">cancel</span>';
    }

    summaryDiv.innerHTML = `
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
                <span class="text-${stateColor}-600 font-bold">${stateIcon}</span>
                <span class="text-sm font-semibold text-${stateColor}-700">${data.state}</span>
            </div>
            <span class="text-xs text-gray-500">${new Date(data.updated_at).toLocaleTimeString()}</span>
        </div>
        <div class="mt-2 text-xs text-gray-600 space-y-1">
            ${data.tokens.prompt || data.tokens.completion ? `<div>Tokens: ${data.tokens.prompt} prompt, ${data.tokens.completion} completion</div>` : ''}
        </div>
    `;
}

// Update memory status detail
function updateMemoryStatusDetail(memory) {
    const detailDiv = document.getElementById('memory-status-detail');
    if (!detailDiv) return;

    if (!memory || !memory.enabled) {
        detailDiv.innerHTML = '<div class="text-gray-400">Not configured</div>';
        return;
    }

    let statusHTML = `<div class="text-${memory.status === 'OK' ? 'green' : 'red'}-600">${memory.status}</div>`;

    if (memory.last_write) {
        const lastWrite = new Date(memory.last_write);
        statusHTML += `<div>Last write: ${lastWrite.toLocaleString()}</div>`;
    }

    detailDiv.innerHTML = statusHTML;
}

// Update RAG status detail
function updateRagStatusDetail(rag) {
    const detailDiv = document.getElementById('rag-status-detail');
    if (!detailDiv) return;

    if (!rag || !rag.enabled) {
        detailDiv.innerHTML = '<div class="text-gray-400">Not configured</div>';
        return;
    }

    let statusColor = 'gray';
    if (rag.status === 'OK') statusColor = 'green';
    else if (rag.status === 'WARN') statusColor = 'yellow';
    else if (rag.status === 'ERROR') statusColor = 'red';

    let statusHTML = `<div class="text-${statusColor}-600">${rag.status}</div>`;

    if (rag.detail) {
        statusHTML += `<div class="text-gray-500">${escapeHtml(rag.detail)}</div>`;
    }

    if (rag.last_refresh) {
        const lastRefresh = new Date(rag.last_refresh);
        statusHTML += `<div>Last refresh: ${lastRefresh.toLocaleString()}</div>`;
    }

    detailDiv.innerHTML = statusHTML;
}

// Attach context
async function attachContext() {
    const sessionId = state.currentSession;

    // Validate session
    if (!sessionId) {
        Dialog.alert('Cannot attach context: No active session. Please start or select a conversation first.', {
            title: 'No Active Session'
        });
        return;
    }

    const memoryEnabled = document.getElementById('memory-enabled').checked;
    const ragEnabled = document.getElementById('rag-enabled').checked;
    const memoryNamespace = document.getElementById('memory-namespace').value.trim();
    const ragIndex = document.getElementById('rag-index').value.trim();

    if (memoryEnabled && !memoryNamespace) {
        Dialog.alert('Memory namespace is required', { title: 'Validation Error' });
        return;
    }

    try {
        const response = await fetch('/api/context/attach', withCsrfToken({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                memory: memoryEnabled ? {
                    enabled: true,
                    namespace: memoryNamespace,
                } : { enabled: false, namespace: '' },
                rag: ragEnabled && ragIndex ? {
                    enabled: true,
                    index: ragIndex,
                } : { enabled: false, index: null },
            }),
        }));

        const data = await response.json();

        if (data.ok) {
            // Reload context status
            setTimeout(() => {
                loadContextStatus();
            }, 300);
        } else {
            Dialog.alert('Failed to attach context', { title: 'Error' });
        }
    } catch (err) {
        console.error('Failed to attach context:', err);
        Dialog.alert('Error: ' + err.message, { title: 'Error' });
    }
}

// Detach context
async function detachContext() {
    const sessionId = state.currentSession;

    // Validate session
    if (!sessionId) {
        Dialog.alert('Cannot detach context: No active session. Please start or select a conversation first.', {
            title: 'No Active Session'
        });
        return;
    }

    const confirmed = await Dialog.confirm('Detach all context from this session?', {
        title: 'Detach Context',
        confirmText: 'Detach',
        danger: true
    });
    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch(`/api/context/detach?session_id=${sessionId}`, withCsrfToken({
            method: 'POST',
        }));

        const data = await response.json();

        if (data.ok) {
            // Reload context status
            setTimeout(() => {
                loadContextStatus();
            }, 300);
        } else {
            Dialog.alert('Failed to detach context', { title: 'Error' });
        }
    } catch (err) {
        console.error('Failed to detach context:', err);
        Dialog.alert('Error: ' + err.message, { title: 'Error' });
    }
}

// Refresh context
async function refreshContext() {
    const sessionId = state.currentSession;

    // Validate session
    if (!sessionId) {
        console.warn('Cannot refresh context: No active session');
        return;
    }

    try {
        const response = await fetch('/api/context/refresh', withCsrfToken({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
            }),
        }));

        const data = await response.json();

        if (data.ok) {
            // Reload context status after a short delay
            setTimeout(() => {
                loadContextStatus();
            }, 1000);
        } else {
            Dialog.alert('Failed to refresh context', { title: 'Error' });
        }
    } catch (err) {
        console.error('Failed to refresh context:', err);
        Dialog.alert('Error: ' + err.message, { title: 'Error' });
    }
}

// Start context status polling
function startContextStatusPolling() {
    // Poll every 30 seconds (slower than provider status)
    if (state.contextStatusInterval) {
        clearInterval(state.contextStatusInterval);
    }

    state.contextStatusInterval = setInterval(() => {
        loadContextStatus();
    }, 30000);
}

// Render Providers View (Sprint B+ WebUI Integration)
async function renderProvidersView(container) {
    // Render ProvidersView (loaded via script tag in index.html)
    try {
        // Use window.ProvidersView (loaded via script tag, not ES module)
        if (!window.ProvidersView) {
            throw new Error('ProvidersView not loaded');
        }

        // Clean up previous view
        if (state.currentViewInstance && state.currentViewInstance.unmount) {
            state.currentViewInstance.unmount();
        }

        // Create API client instance
        const apiClient = {
            get: async (url, options = {}) => {
                // Handle query parameters
                if (options.params) {
                    const queryString = new URLSearchParams(options.params).toString();
                    url = queryString ? `${url}?${queryString}` : url;
                }
                const response = await fetch(url);
                if (!response.ok) throw new Error(response.statusText);
                return response.json();
            },
            post: async (url, data) => {
                const response = await fetch(url, withCsrfToken({
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                }));
                if (!response.ok) throw new Error(response.statusText);
                return response.json();
            },
            put: async (url, data) => {
                const response = await fetch(url, withCsrfToken({
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                }));
                if (!response.ok) throw new Error(response.statusText);
                return response.json();
            },
            delete: async (url) => {
                const response = await fetch(url, withCsrfToken({method: 'DELETE'}));
                if (!response.ok) throw new Error(response.statusText);
                return response.json();
            }
        };

        const view = new window.ProvidersView(apiClient);
        container.innerHTML = await view.render();
        await view.mount();

        state.currentViewInstance = view;
        // Expose view instance globally for onclick handlers
        window.providersView = view;
    } catch (error) {
        console.error('Failed to load ProvidersView:', error);
        container.innerHTML = `<div class="error">Failed to load providers view: ${error.message}</div>`;
    }
}

// Render Execution Plans View (Wave4-X1)
function renderExecutionPlansView(container) {
    try {
        if (typeof window.ExecutionPlansView !== 'undefined') {
            const view = new window.ExecutionPlansView(container);
            state.currentViewInstance = view;
        } else {
            container.innerHTML = `
                <div class="p-6">
                    <div class="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
                        <h2 class="text-2xl font-bold text-blue-900 mb-3">Execution Plans</h2>
                        <p class="text-blue-700 mb-4">
                            Dry-run execution planning with proposal generation.
                            View task execution plans, analyze impact, and submit for Guardian review.
                        </p>
                        <p class="text-sm text-blue-600">
                            This view is currently under development. View module: ExecutionPlansView.js
                        </p>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load ExecutionPlansView:', error);
        container.innerHTML = `<div class="error">Failed to load execution plans view: ${error.message}</div>`;
    }
}

// Render Intent Workbench View (Wave4-X1)
function renderIntentWorkbenchView(container, params = {}) {
    try {
        if (typeof window.IntentWorkbenchView !== 'undefined') {
            const view = new window.IntentWorkbenchView(container);
            state.currentViewInstance = view;
            view.render(params);
        } else {
            container.innerHTML = `
                <div class="p-6">
                    <div class="bg-purple-50 border border-purple-200 rounded-lg p-6 text-center">
                        <h2 class="text-2xl font-bold text-purple-900 mb-3">Intent Workbench</h2>
                        <p class="text-purple-700 mb-4">
                            Intent building and merging workbench with explain + diff capabilities.
                            Build intents, compare versions, and generate merge proposals for Guardian review.
                        </p>
                        <p class="text-sm text-purple-600">
                            This view is currently under development. View module: IntentWorkbenchView.js
                        </p>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load IntentWorkbenchView:', error);
        container.innerHTML = `<div class="error">Failed to load intent workbench view: ${error.message}</div>`;
    }
}

// Render Content Registry View (Wave4-X1)
async function renderContentRegistryView(container) {
    try {
        if (typeof window.ContentRegistryView !== 'undefined') {
            const view = new window.ContentRegistryView(apiClient);
            state.currentViewInstance = view;

            // Render the view
            const html = await view.render();
            container.innerHTML = html;

            // Mount the view (attach event listeners, load data)
            await view.mount();
        } else {
            container.innerHTML = `
                <div class="p-6">
                    <div class="bg-orange-50 border border-orange-200 rounded-lg p-6 text-center">
                        <h2 class="text-2xl font-bold text-orange-900 mb-3">Content Registry</h2>
                        <p class="text-orange-700 mb-4">
                            Content asset management with versioning and lifecycle control.
                            View content versions, activate/deprecate/freeze assets, and track usage.
                        </p>
                        <p class="text-sm text-orange-600">
                            View module ContentRegistryView.js is not loaded. Please check console for errors.
                        </p>
                    </div>
                </div>
            `;
            console.warn('ContentRegistryView class not found. Ensure /static/js/views/ContentRegistryView.js is loaded.');
        }
    } catch (error) {
        console.error('Failed to load ContentRegistryView:', error);
        container.innerHTML = `
            <div class="p-6">
                <div class="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
                    <h2 class="text-xl font-bold text-red-900 mb-3">Error Loading Content Registry</h2>
                    <p class="text-red-700 text-sm">${error.message}</p>
                </div>
            </div>
        `;
    }
}

// Render Answer Packs View (Wave4-X1)
function renderAnswerPacksView(container) {
    try {
        if (typeof window.AnswerPacksView !== 'undefined') {
            const view = new window.AnswerPacksView(container);
            state.currentViewInstance = view;
        } else {
            container.innerHTML = `
                <div class="p-6">
                    <div class="bg-amber-50 border border-amber-200 rounded-lg p-6 text-center">
                        <h2 class="text-2xl font-bold text-amber-900 mb-3">Answer Packs</h2>
                        <p class="text-amber-700 mb-4">
                            Answer pack creation, validation, and application.
                            Create answer packs, validate responses, and link to tasks.
                        </p>
                        <p class="text-sm text-amber-600">
                            This view is currently under development. View module: AnswerPacksView.js
                        </p>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load AnswerPacksView:', error);
        container.innerHTML = `<div class="error">Failed to load answer packs view: ${error.message}</div>`;
    }
}

function renderAuthProfilesView(container) {
    try {
        if (typeof window.AuthProfilesView !== 'undefined') {
            const view = new window.AuthProfilesView(container);
            state.currentViewInstance = view;
        } else {
            container.innerHTML = `
                <div class="p-6">
                    <div class="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
                        <h2 class="text-2xl font-bold text-blue-900 mb-3">Authentication Profiles</h2>
                        <p class="text-blue-700 mb-4">
                            Read-only view of git authentication configurations (SSH, PAT, netrc).
                            To modify profiles, use the CLI.
                        </p>
                        <div class="bg-gray-800 text-gray-100 p-3 rounded text-left inline-block font-mono text-sm">
                            $ agentos auth add --type ssh --key ~/.ssh/id_rsa
                        </div>
                        <p class="text-sm text-blue-600 mt-4">
                            This view is currently under development. View module: AuthReadOnlyCard.js
                        </p>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to load AuthProfilesView:', error);
        container.innerHTML = `<div class="error">Failed to load auth profiles view: ${error.message}</div>`;
    }
}

// Render Mode Monitor View (Task #15: Phase 3.4)
async function renderModeMonitorView(container) {
    try {
        // Clear previous view instance
        if (state.currentViewInstance && state.currentViewInstance.destroy) {
            state.currentViewInstance.destroy();
            state.currentViewInstance = null;
        }

        // Check if ModeMonitorView is available
        if (typeof window.ModeMonitorView === 'undefined') {
            console.error('ModeMonitorView not loaded');
            container.innerHTML = `
                <div class="p-6 text-center">
                    <div class="bg-red-50 border border-red-200 rounded-lg p-6">
                        <h2 class="text-xl font-bold text-red-900 mb-2">Module Loading Error</h2>
                        <p class="text-red-700">ModeMonitorView module failed to load. Please refresh the page.</p>
                    </div>
                </div>
            `;
            return;
        }

        // Create and render the view
        const view = new window.ModeMonitorView();
        state.currentViewInstance = view;

        await view.render(container);

        console.log('Mode Monitor View rendered successfully');
    } catch (error) {
        console.error('Failed to render Mode Monitor View:', error);
        container.innerHTML = `
            <div class="p-6 text-center">
                <div class="bg-red-50 border border-red-200 rounded-lg p-6">
                    <h2 class="text-xl font-bold text-red-900 mb-2">Rendering Error</h2>
                    <p class="text-red-700 mb-2">Failed to load Mode Monitor view.</p>
                    <p class="text-sm text-red-600">Error: ${error.message}</p>
                </div>
            </div>
        `;
    }
}

// Render Extensions View (PR-C: WebUI Extensions Management)
async function renderExtensionsView(container) {
    try {
        console.log('Rendering Extensions View...');

        // Check if ExtensionsView class is available
        if (typeof window.ExtensionsView === 'undefined') {
            console.error('ExtensionsView class not found');
            container.innerHTML = `
                <div class="p-6 text-center">
                    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                        <h2 class="text-xl font-bold text-yellow-900 mb-2">Extensions View Not Available</h2>
                        <p class="text-yellow-700">The Extensions View component is not loaded. Please refresh the page.</p>
                    </div>
                </div>
            `;
            return;
        }

        // Cleanup previous view instance
        if (state.currentViewInstance && typeof state.currentViewInstance.destroy === 'function') {
            state.currentViewInstance.destroy();
        }

        // Create and render the view
        const view = new window.ExtensionsView();
        state.currentViewInstance = view;
        window.extensionsView = view; // Global reference for onclick handlers

        await view.render(container);

        console.log('Extensions View rendered successfully');
    } catch (error) {
        console.error('Failed to render Extensions View:', error);
        container.innerHTML = `
            <div class="p-6 text-center">
                <div class="bg-red-50 border border-red-200 rounded-lg p-6">
                    <h2 class="text-xl font-bold text-red-900 mb-2">Rendering Error</h2>
                    <p class="text-red-700 mb-2">Failed to load Extensions view.</p>
                    <p class="text-sm text-red-600">Error: ${error.message}</p>
                </div>
            </div>
        `;
    }
}

// Render Models View (Model Download and Management)
async function renderModelsView(container) {
    try {
        console.log('Rendering Models View...');

        // Check if ModelsView class is available
        if (typeof window.ModelsView === 'undefined') {
            console.error('ModelsView class not found');
            container.innerHTML = `
                <div class="p-6 text-center">
                    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                        <h2 class="text-xl font-bold text-yellow-900 mb-2">Models View Not Available</h2>
                        <p class="text-yellow-700">The Models View component is not loaded. Please refresh the page.</p>
                    </div>
                </div>
            `;
            return;
        }

        // Cleanup previous view instance
        if (state.currentViewInstance && typeof state.currentViewInstance.destroy === 'function') {
            state.currentViewInstance.destroy();
        }

        // Create and render the view
        const view = new window.ModelsView();
        state.currentViewInstance = view;

        await view.render(container);

        console.log('Models View rendered successfully');
    } catch (error) {
        console.error('Failed to render Models View:', error);
        container.innerHTML = `
            <div class="p-6 text-center">
                <div class="bg-red-50 border border-red-200 rounded-lg p-6">
                    <h2 class="text-xl font-bold text-red-900 mb-2">Rendering Error</h2>
                    <p class="text-red-700 mb-2">Failed to load Models view.</p>
                    <p class="text-sm text-red-600">Error: ${error.message}</p>
                </div>
            </div>
        `;
    }
}

// Render Marketplace View (MCP Marketplace - PR-C)
async function renderMarketplaceView(container) {
    try {
        console.log('Rendering Marketplace View...');

        // Check if MarketplaceView class is available
        if (typeof window.MarketplaceView === 'undefined') {
            console.error('MarketplaceView class not found');
            container.innerHTML = `
                <div class="p-6 text-center">
                    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                        <h2 class="text-xl font-bold text-yellow-900 mb-2">Marketplace View Not Available</h2>
                        <p class="text-yellow-700">The Marketplace View component is not loaded. Please refresh the page.</p>
                    </div>
                </div>
            `;
            return;
        }

        // Cleanup previous view instance
        if (state.currentViewInstance && typeof state.currentViewInstance.destroy === 'function') {
            state.currentViewInstance.destroy();
        }

        // Create and render the view
        const view = new window.MarketplaceView();
        state.currentViewInstance = view;

        await view.render(container);

        console.log('Marketplace View rendered successfully');
    } catch (error) {
        console.error('Failed to render Marketplace View:', error);
        container.innerHTML = `
            <div class="p-6 text-center">
                <div class="bg-red-50 border border-red-200 rounded-lg p-6">
                    <h2 class="text-xl font-bold text-red-900 mb-2">Rendering Error</h2>
                    <p class="text-red-700 mb-2">Failed to load Marketplace view.</p>
                    <p class="text-sm text-red-600">Error: ${error.message}</p>
                </div>
            </div>
        `;
    }
}

// Render MCP Package Detail View (MCP Marketplace - PR-C)
async function renderMCPPackageDetailView(container) {
    try {
        console.log('Rendering MCP Package Detail View...');

        // Check if MCPPackageDetailView class is available
        if (typeof window.MCPPackageDetailView === 'undefined') {
            console.error('MCPPackageDetailView class not found');
            container.innerHTML = `
                <div class="p-6 text-center">
                    <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                        <h2 class="text-xl font-bold text-yellow-900 mb-2">Package Detail View Not Available</h2>
                        <p class="text-yellow-700">The Package Detail View component is not loaded. Please refresh the page.</p>
                    </div>
                </div>
            `;
            return;
        }

        // Cleanup previous view instance
        if (state.currentViewInstance && typeof state.currentViewInstance.destroy === 'function') {
            state.currentViewInstance.destroy();
        }

        // Create and render the view
        const view = new window.MCPPackageDetailView();
        state.currentViewInstance = view;

        await view.render(container);

        console.log('MCP Package Detail View rendered successfully');
    } catch (error) {
        console.error('Failed to render MCP Package Detail View:', error);
        container.innerHTML = `
            <div class="p-6 text-center">
                <div class="bg-red-50 border border-red-200 rounded-lg p-6">
                    <h2 class="text-xl font-bold text-red-900 mb-2">Rendering Error</h2>
                    <p class="text-red-700 mb-2">Failed to load Package Detail view.</p>
                    <p class="text-sm text-red-600">Error: ${error.message}</p>
                </div>
            </div>
        `;
    }
}


// ============================================================================
// Budget Indicator Functions (Task 5: Runtime Visualization)
// ============================================================================

/**
 * Update budget indicator in chat header
 * @param {Object} budgetData - Budget data from WebSocket
 */
function updateBudgetIndicator(budgetData) {
    // Check if we have a budget indicator element (may not be on chat view)
    let indicator = document.getElementById('budget-indicator');

    if (!indicator) {
        // Create budget indicator if it doesn't exist
        const toolbar = document.getElementById('chat-toolbar');
        if (!toolbar) {
            console.log('Budget indicator: Not on chat view, skipping');
            return;
        }

        // Insert budget indicator into toolbar
        const row1 = toolbar.querySelector('.flex.items-center.justify-between.gap-4');
        if (!row1) return;

        const budgetHtml = `
            <div class="budget-indicator" id="budget-indicator" style="display: none;">
                <span class="budget-usage" id="budget-usage">
                    <span class="material-icons md-18" style="vertical-align: middle;">bar_chart</span>
                    <span id="budget-text">--</span>
                </span>
                <span class="budget-status" id="budget-status"></span>
            </div>
        `;

        // Insert after model controls
        row1.insertAdjacentHTML('beforeend', budgetHtml);
        indicator = document.getElementById('budget-indicator');

        // Add click handler for details modal
        indicator.addEventListener('click', () => {
            const currentData = indicator._budgetData;
            if (currentData) {
                showBudgetDetails(currentData);
            }
        });
    }

    // Store data for modal
    indicator._budgetData = budgetData;

    const usageEl = document.getElementById('budget-usage');
    const statusEl = document.getElementById('budget-status');

    if (!usageEl || !statusEl) return;

    const percent = (budgetData.usage_ratio * 100).toFixed(0);
    const usedK = (budgetData.total_tokens / 1000).toFixed(1);
    const totalK = (budgetData.budget_tokens / 1000).toFixed(1);

    // Update budget text (preserve icon structure)
    const budgetTextEl = document.getElementById('budget-text');
    if (budgetTextEl) {
        budgetTextEl.textContent = ` Budget: ` + usedK + `k/` + totalK + `k (` + percent + `%)`;
    } else {
        // Fallback for old HTML structure
        usageEl.innerHTML = `<span class="material-icons md-18" style="vertical-align: middle;">bar_chart</span> Budget: ` + usedK + `k/` + totalK + `k (` + percent + `%)`;
    }

    // Status configuration with Material Icons
    const statusConfig = {
        safe: {
            class: 'badge-safe',
            icon: 'check_circle',
            text: 'Safe'
        },
        warning: {
            class: 'badge-warning',
            icon: 'warning',
            text: 'Warning',
            hint: 'Context nearing limit. Consider /summary.'
        },
        critical: {
            class: 'badge-critical',
            icon: 'error',
            text: 'Critical',
            hint: percent >= 100 ? 'Context full! Oldest messages truncated.' : 'Context nearly full. Messages may be truncated soon.'
        }
    };

    const status = statusConfig[budgetData.watermark] || statusConfig.safe;
    statusEl.className = `budget-status ` + status.class;
    statusEl.innerHTML = `<span class="material-icons md-18" style="vertical-align: middle;">` + status.icon + `</span> ` + status.text + (status.hint ? `<br><small>` + status.hint + `</small>` : '');

    indicator.style.display = 'flex';

    console.log(`Budget indicator updated: ` + percent + `% used (` + budgetData.watermark + `)`);
}

/**
 * Show detailed budget breakdown modal
 * @param {Object} budgetData - Budget data
 */
function showBudgetDetails(budgetData) {
    const breakdown = budgetData.breakdown;
    const totalUsed = budgetData.total_tokens;  // 实际使用量（作为分母）
    const budget = budgetData.budget_tokens;    // 预算（仅用于顶部展示）

    // UI 保护：如果实际使用量为 0 或缺失，退化为只显示 tokens
    const showPercentages = totalUsed && totalUsed > 0;

    const bars = [
        renderBudgetBar('System Prompt', breakdown.system, totalUsed, showPercentages),
        renderBudgetBar('Conversation', breakdown.window, totalUsed, showPercentages),
        renderBudgetBar('RAG Context', breakdown.rag, totalUsed, showPercentages),
        renderBudgetBar('Memory Facts', breakdown.memory, totalUsed, showPercentages)
    ].join('');

    // 预算信息（独立展示，不作为 breakdown 的分母）
    const budgetPercent = budget > 0 ? ((totalUsed / budget) * 100).toFixed(1) : 'N/A';
    const budgetInfo = `<div style="margin-bottom: 16px; padding: 12px; background: #f3f4f6; border-radius: 6px; font-size: 13px;">
        <strong>Total Used:</strong> ${totalUsed.toLocaleString()} tokens<br>
        <strong>Budget:</strong> ${budget.toLocaleString()} tokens ${budget > 0 ? `(${budgetPercent}% used)` : '(No budget configured)'}
    </div>`;

    const html = `<div class="budget-detail-modal"><h3>Token Usage Breakdown</h3>` + budgetInfo + `<div class="budget-bars">` + bars + `</div><p class="budget-tip"><span class="material-icons md-18" style="vertical-align: middle;">lightbulb</span> Tip: Percentages show each component's share of actual usage</p></div>`;

    // Use existing modal system if available, otherwise create simple modal
    if (window.Dialog && window.Dialog.alert) {
        window.Dialog.alert(html, { title: 'Token Budget Details', isHtml: true });
    } else {
        // Fallback: simple alert
        const pct = (x) => showPercentages ? ` (${((x / totalUsed) * 100).toFixed(1)}%)` : '';
        const msg = 'Token Budget Details\n\n' +
            'Total Used: ' + totalUsed.toLocaleString() + ' / ' + budget.toLocaleString() + '\n\n' +
            'System: ' + breakdown.system.toLocaleString() + pct(breakdown.system) + '\n' +
            'Window: ' + breakdown.window.toLocaleString() + pct(breakdown.window) + '\n' +
            'RAG: ' + breakdown.rag.toLocaleString() + pct(breakdown.rag) + '\n' +
            'Memory: ' + breakdown.memory.toLocaleString() + pct(breakdown.memory);
        Dialog.alert(msg.replace(/\n/g, '<br>'), { title: 'Token Budget Breakdown' });
    }
}

/**
 * Render a single budget bar
 * @param {string} label - Component label
 * @param {number} tokens - Token count
 * @param {number} totalUsed - Total tokens used (for percentage calculation)
 * @param {boolean} showPercentages - Whether to show percentages
 * @returns {string} HTML string
 */
function renderBudgetBar(label, tokens, totalUsed, showPercentages = true) {
    // 百分比计算：占实际使用量的比例
    const percent = showPercentages && totalUsed > 0 ? ((tokens / totalUsed) * 100).toFixed(1) : 0;
    const width = Math.min(percent, 100);

    // Determine fill class based on percentage of total usage
    // 注意：这里的颜色阈值是相对于"该组件占总使用量的比例"
    let fillClass = '';
    if (percent >= 80) {
        fillClass = 'critical';
    } else if (percent >= 60) {
        fillClass = 'warning';
    }

    // Simple HTML escaping for label
    const safeLabel = label.replace(/[&<>"']/g, (m) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[m]));

    // 显示格式：如果有百分比就显示，否则只显示 tokens
    const labelText = showPercentages
        ? `${safeLabel}: ${tokens.toLocaleString()} (${percent}% of total used)`
        : `${safeLabel}: ${tokens.toLocaleString()} tokens`;

    return `<div class="budget-bar-item"><label>${labelText}</label><div class="progress-bar"><div class="progress-fill ${fillClass}" style="width: ${width}%"></div></div></div>`;
}

// ============================================================================
// Memory Badge Component (Task #9: Memory Observability UI Badge)
// ============================================================================

/**
 * Memory Badge - Shows memory context status in the top bar
 */
const MemoryBadge = {
    element: null,
    tooltip: null,
    currentSessionId: null,
    updateInterval: null,

    /**
     * Initialize Memory Badge component
     */
    init: function() {
        console.log('[MemoryBadge] Initializing...');

        const container = document.getElementById('top-bar-indicators');
        if (!container) {
            console.warn('[MemoryBadge] Top bar indicators container not found');
            return;
        }

        // Create badge HTML
        const badgeHTML = `
            <div class="memory-badge-container">
                <div class="memory-badge no-memories" id="memory-badge">
                    <span class="memory-badge-icon">🧠</span>
                    <span class="memory-badge-count">Memory: 0</span>
                </div>
                <div class="memory-tooltip" id="memory-tooltip">
                    <div class="memory-tooltip-item">
                        <span class="memory-tooltip-label">Total:</span>
                        <span class="memory-tooltip-value" id="memory-total">0</span>
                    </div>
                    <div class="memory-tooltip-item highlight" id="memory-preferred-name-row" style="display:none;">
                        <span class="memory-tooltip-label">Name:</span>
                        <span class="memory-tooltip-value" id="memory-preferred-name"></span>
                    </div>
                    <div class="memory-tooltip-divider" id="memory-types-divider" style="display:none;"></div>
                    <div class="memory-tooltip-item" id="memory-types-row">
                        <span class="memory-tooltip-label">Types:</span>
                        <span class="memory-tooltip-value" id="memory-types">-</span>
                    </div>
                </div>
            </div>
        `;

        // Insert before refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.insertAdjacentHTML('beforebegin', badgeHTML);
        } else {
            container.insertAdjacentHTML('beforeend', badgeHTML);
        }

        this.element = document.getElementById('memory-badge');
        this.tooltip = document.getElementById('memory-tooltip');

        if (!this.element || !this.tooltip) {
            console.error('[MemoryBadge] Failed to create badge elements');
            return;
        }

        // Add hover listeners
        this.element.addEventListener('mouseenter', () => this.showTooltip());
        this.element.addEventListener('mouseleave', () => this.hideTooltip());

        // Click to navigate to Memory page
        this.element.addEventListener('click', () => {
            console.log('[MemoryBadge] Clicked - navigating to Memory view');
            loadView('memory');
        });

        console.log('[MemoryBadge] Initialized successfully');
    },

    /**
     * Update badge with session data
     * @param {string} sessionId - Session ID to fetch memory status for
     */
    update: async function(sessionId) {
        if (!sessionId) {
            console.log('[MemoryBadge] No session ID provided');
            return;
        }

        if (!this.element) {
            console.warn('[MemoryBadge] Badge not initialized, initializing now...');
            this.init();
            if (!this.element) return;
        }

        this.currentSessionId = sessionId;

        try {
            console.log(`[MemoryBadge] Fetching memory status for session: ${sessionId}`);
            const response = await fetch(`/api/chat/sessions/${sessionId}/memory-status`);

            if (!response.ok) {
                console.error(`[MemoryBadge] API error: ${response.status}`);
                this.renderError();
                return;
            }

            const data = await response.json();
            console.log('[MemoryBadge] Memory status:', data);
            this.render(data);
        } catch (error) {
            console.error('[MemoryBadge] Failed to fetch status:', error);
            this.renderError();
        }
    },

    /**
     * Render badge with memory data
     * @param {Object} data - Memory status data
     */
    render: function(data) {
        if (!this.element) return;

        const count = data.memory_count || 0;
        const hasMemories = count > 0;

        // Update badge
        this.element.className = hasMemories ? 'memory-badge has-memories' : 'memory-badge no-memories';
        this.element.querySelector('.memory-badge-count').textContent = `Memory: ${count}`;

        // Update tooltip
        const totalEl = document.getElementById('memory-total');
        if (totalEl) totalEl.textContent = count;

        // Preferred name
        const nameRow = document.getElementById('memory-preferred-name-row');
        const nameValue = document.getElementById('memory-preferred-name');
        const namesDivider = document.getElementById('memory-types-divider');

        if (data.has_preferred_name && data.preferred_name) {
            if (nameRow) nameRow.style.display = 'flex';
            if (nameValue) nameValue.textContent = data.preferred_name;
            if (namesDivider) namesDivider.style.display = 'block';
        } else {
            if (nameRow) nameRow.style.display = 'none';
            if (namesDivider) namesDivider.style.display = 'none';
        }

        // Memory types
        const typesRow = document.getElementById('memory-types-row');
        const typesValue = document.getElementById('memory-types');
        const types = data.memory_types || {};

        if (Object.keys(types).length > 0) {
            const typesText = Object.entries(types)
                .map(([type, count]) => `${type}: ${count}`)
                .join(', ');
            if (typesValue) typesValue.textContent = typesText;
            if (typesRow) typesRow.style.display = 'flex';
        } else {
            if (typesValue) typesValue.textContent = '-';
            if (typesRow) typesRow.style.display = 'flex';
        }

        console.log(`[MemoryBadge] Rendered: ${count} memories (${hasMemories ? 'has memories' : 'no memories'})`);
    },

    /**
     * Render error state
     */
    renderError: function() {
        if (!this.element) return;

        this.element.className = 'memory-badge no-memories';
        this.element.querySelector('.memory-badge-count').textContent = 'Memory: Error';
        console.error('[MemoryBadge] Error state rendered');
    },

    /**
     * Show tooltip
     */
    showTooltip: function() {
        if (this.tooltip) {
            this.tooltip.classList.add('visible');
        }
    },

    /**
     * Hide tooltip
     */
    hideTooltip: function() {
        if (this.tooltip) {
            this.tooltip.classList.remove('visible');
        }
    },

    /**
     * Start auto-update interval
     * @param {number} intervalMs - Update interval in milliseconds (default: 30s)
     */
    startAutoUpdate: function(intervalMs = 30000) {
        this.stopAutoUpdate();

        this.updateInterval = setInterval(() => {
            if (this.currentSessionId) {
                console.log('[MemoryBadge] Auto-updating...');
                this.update(this.currentSessionId);
            }
        }, intervalMs);

        console.log(`[MemoryBadge] Auto-update started (interval: ${intervalMs}ms)`);
    },

    /**
     * Stop auto-update interval
     */
    stopAutoUpdate: function() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
            console.log('[MemoryBadge] Auto-update stopped');
        }
    },

    /**
     * Cleanup
     */
    destroy: function() {
        this.stopAutoUpdate();

        if (this.element) {
            this.element.remove();
            this.element = null;
        }

        if (this.tooltip) {
            this.tooltip.remove();
            this.tooltip = null;
        }

        this.currentSessionId = null;
        console.log('[MemoryBadge] Destroyed');
    }
};

// Initialize Memory Badge on page load
document.addEventListener('DOMContentLoaded', () => {
    // Wait a bit for other components to initialize
    setTimeout(() => {
        MemoryBadge.init();

        // Start auto-update with 30-second interval
        MemoryBadge.startAutoUpdate(30000);
    }, 500);
});

// Update Memory Badge when session changes
// This will be called by the chat view when a session is loaded
function updateMemoryBadge(sessionId) {
    if (sessionId && MemoryBadge) {
        MemoryBadge.update(sessionId);
    }
}

// ============================================================================
// BrainOS Dashboard View
// ============================================================================

function renderBrainDashboardView(container) {
    state.currentViewInstance = new BrainDashboardView(container);
}

// ============================================================================
// BrainOS Query Console View
// ============================================================================

function renderBrainQueryConsoleView(container) {
    state.currentViewInstance = new BrainQueryConsoleView(container);
}

// ============================================================================
// CommunicationOS Views
// ============================================================================

function renderChannelsView(container) {
    state.currentViewInstance = new ChannelsView(container);
}

function renderCommunicationView(container) {
    state.currentViewInstance = new CommunicationView(container);
}

function renderSubgraphView(container) {
    if (!window.SubgraphView) {
        container.innerHTML = '<div class="p-6 text-red-500">SubgraphView not loaded. Please check if SubgraphView.js is included.</div>';
        return;
    }
    state.currentViewInstance = new window.SubgraphView();
    state.currentViewInstance.init();
}

// Render Decision Review View (P4-C2)
function renderDecisionReviewView(container) {
    if (!window.DecisionReviewView) {
        container.innerHTML = '<div class="p-6 text-red-500">DecisionReviewView not loaded. Please check if DecisionReviewView.js is included.</div>';
        return;
    }
    state.currentViewInstance = new window.DecisionReviewView();
    state.currentViewInstance.render(container);
}

// Render InfoNeed Metrics View (Task #21)
function renderInfoNeedMetricsView(container) {
    if (!window.InfoNeedMetricsView) {
        container.innerHTML = '<div class="p-6 text-red-500">InfoNeedMetricsView not loaded. Please check if InfoNeedMetricsView.js is included.</div>';
        return;
    }
    state.currentViewInstance = new window.InfoNeedMetricsView(container);
}

// ============================================================================
// Slash Command Autocomplete
// ============================================================================

// State for autocomplete
const autocompleteState = {
    commands: [],
    filteredCommands: [],
    selectedIndex: -1,
    isVisible: false,
    currentLevel: 'main', // 'main' or 'sub'
    currentMainCommand: null // Store current main command when showing subcommands
};

// Load available slash commands
async function loadSlashCommands() {
    try {
        const response = await fetch('/api/chat/slash-commands');
        if (!response.ok) {
            throw new Error('Failed to load slash commands');
        }
        const data = await response.json();

        // Build command structure with subcommands
        autocompleteState.commands = data.commands.map(cmd => {
            const command = {
                name: cmd.name,
                summary: cmd.summary,
                description: cmd.description,
                source: cmd.source,
                examples: cmd.examples,
                subcommands: []
            };

            // Parse subcommands from examples and description
            // For commands like /context, /comm that have subcommands
            if (cmd.name === '/context') {
                command.subcommands = [
                    { name: 'show', description: 'Show current context info' },
                    { name: 'show --full', description: 'Show assembled messages summary' },
                    { name: 'pin', description: 'Pin last message to memory' },
                    { name: 'diff', description: 'Diff last two context snapshots' },
                    { name: 'diff --last N', description: 'Diff last N snapshots' }
                ];
            } else if (cmd.name === '/comm') {
                command.subcommands = [
                    { name: 'search <query>', description: 'Execute web search' },
                    { name: 'fetch <url>', description: 'Fetch URL content' },
                    { name: 'brief <topic>', description: 'Generate topic brief' },
                    { name: 'brief <topic> --today', description: 'Generate today\'s brief' }
                ];
            } else if (cmd.name === '/model') {
                command.subcommands = [
                    { name: 'local', description: 'Switch to local model' },
                    { name: 'cloud', description: 'Switch to cloud model' }
                ];
            }

            return command;
        });

        console.log(`Loaded ${autocompleteState.commands.length} slash commands`);
    } catch (err) {
        console.error('Failed to load slash commands:', err);
        autocompleteState.commands = [];
    }
}

// Setup autocomplete for input
function setupSlashCommandAutocomplete(input) {
    // Load commands on initialization
    loadSlashCommands();

    // Listen to input events
    input.addEventListener('input', (e) => {
        handleAutocompleteInput(e.target);
    });

    // Close autocomplete on blur (with delay to allow click)
    input.addEventListener('blur', () => {
        setTimeout(() => {
            hideAutocomplete();
        }, 200);
    });

    // Close autocomplete when clicking outside
    document.addEventListener('click', (e) => {
        const autocomplete = document.getElementById('slash-command-autocomplete');
        const input = document.getElementById('chat-input');
        if (autocomplete && !autocomplete.contains(e.target) && e.target !== input) {
            hideAutocomplete();
        }
    });
}

// Handle input changes
function handleAutocompleteInput(input) {
    const text = input.value;
    const cursorPos = input.selectionStart;

    // Find if cursor is in a slash command
    const beforeCursor = text.substring(0, cursorPos);

    // Try to match a complete command with subcommand
    // Pattern: /command subcommand_prefix
    const fullMatch = beforeCursor.match(/\/([\w]+)\s+(\w*)$/);

    if (fullMatch) {
        // User is typing a subcommand
        const mainCommand = fullMatch[1].toLowerCase();
        const subQuery = fullMatch[2].toLowerCase();
        showSubcommandAutocomplete(mainCommand, subQuery);
    } else {
        // Try to match just the main command
        const cmdMatch = beforeCursor.match(/\/([\w]*)$/);
        if (cmdMatch) {
            const query = cmdMatch[1].toLowerCase();
            showMainCommandAutocomplete(query);
        } else {
            hideAutocomplete();
        }
    }
}

// Show main command autocomplete
function showMainCommandAutocomplete(query) {
    const autocomplete = document.getElementById('slash-command-autocomplete');
    const listContainer = document.getElementById('autocomplete-list');
    const headerEl = autocomplete.querySelector('.autocomplete-header');

    // Filter commands
    if (query === '') {
        // Show all commands
        autocompleteState.filteredCommands = autocompleteState.commands;
    } else {
        // Filter by query
        autocompleteState.filteredCommands = autocompleteState.commands.filter(cmd => {
            const cmdName = cmd.name.toLowerCase();
            return cmdName.includes('/' + query) || cmdName.includes(query);
        });
    }

    // If no matches, hide
    if (autocompleteState.filteredCommands.length === 0) {
        hideAutocomplete();
        return;
    }

    // Update header
    headerEl.textContent = 'Slash Commands';

    // Render command list
    listContainer.innerHTML = autocompleteState.filteredCommands.map((cmd, index) => {
        const isSelected = index === autocompleteState.selectedIndex;
        const hasSubcommands = cmd.subcommands && cmd.subcommands.length > 0;

        return `
            <div class="autocomplete-item ${isSelected ? 'selected' : ''}" data-index="${index}" data-type="command" onclick="selectMainCommand(${index})">
                <div class="autocomplete-command-name">
                    ${escapeHtml(cmd.name)}
                    ${hasSubcommands ? '<span class="subcommand-indicator">▸</span>' : ''}
                </div>
                <div class="autocomplete-command-desc">${escapeHtml(cmd.summary || cmd.description)}</div>
                ${cmd.source === 'extension' ? '<span class="autocomplete-badge">Extension</span>' : '<span class="autocomplete-badge builtin">Built-in</span>'}
            </div>
        `;
    }).join('');

    // Show autocomplete
    autocomplete.style.display = 'block';
    autocompleteState.isVisible = true;
    autocompleteState.selectedIndex = -1;
    autocompleteState.currentLevel = 'main';
}

// Show subcommand autocomplete
function showSubcommandAutocomplete(mainCommand, subQuery) {
    const autocomplete = document.getElementById('slash-command-autocomplete');
    const listContainer = document.getElementById('autocomplete-list');
    const headerEl = autocomplete.querySelector('.autocomplete-header');

    // Find the main command
    const cmd = autocompleteState.commands.find(c =>
        c.name.toLowerCase() === '/' + mainCommand
    );

    if (!cmd || !cmd.subcommands || cmd.subcommands.length === 0) {
        hideAutocomplete();
        return;
    }

    // Filter subcommands
    let filteredSubcommands;
    if (subQuery === '') {
        filteredSubcommands = cmd.subcommands;
    } else {
        filteredSubcommands = cmd.subcommands.filter(sub => {
            return sub.name.toLowerCase().startsWith(subQuery);
        });
    }

    if (filteredSubcommands.length === 0) {
        hideAutocomplete();
        return;
    }

    // Store for selection
    autocompleteState.filteredCommands = filteredSubcommands.map(sub => ({
        name: sub.name,
        description: sub.description,
        mainCommand: cmd.name
    }));

    // Update header
    headerEl.textContent = `${cmd.name} - Subcommands`;

    // Render subcommand list
    listContainer.innerHTML = filteredSubcommands.map((sub, index) => {
        const isSelected = index === autocompleteState.selectedIndex;
        return `
            <div class="autocomplete-item ${isSelected ? 'selected' : ''}" data-index="${index}" data-type="subcommand" onclick="selectSubcommand(${index})">
                <div class="autocomplete-command-name autocomplete-subcommand">${escapeHtml(sub.name)}</div>
                <div class="autocomplete-command-desc">${escapeHtml(sub.description)}</div>
            </div>
        `;
    }).join('');

    // Show autocomplete
    autocomplete.style.display = 'block';
    autocompleteState.isVisible = true;
    autocompleteState.selectedIndex = -1;
    autocompleteState.currentLevel = 'sub';
    autocompleteState.currentMainCommand = cmd.name;
}

// Hide autocomplete
function hideAutocomplete() {
    const autocomplete = document.getElementById('slash-command-autocomplete');
    if (autocomplete) {
        autocomplete.style.display = 'none';
        autocompleteState.isVisible = false;
        autocompleteState.selectedIndex = -1;
    }
}

// Handle keyboard navigation
function handleAutocompleteKeydown(e) {
    if (!autocompleteState.isVisible) {
        return false;
    }

    const input = document.getElementById('chat-input');

    switch (e.key) {
        case 'ArrowDown':
            e.preventDefault();
            autocompleteState.selectedIndex = Math.min(
                autocompleteState.selectedIndex + 1,
                autocompleteState.filteredCommands.length - 1
            );
            updateAutocompleteSelection();
            return true;

        case 'ArrowUp':
            e.preventDefault();
            autocompleteState.selectedIndex = Math.max(
                autocompleteState.selectedIndex - 1,
                0
            );
            updateAutocompleteSelection();
            return true;

        case 'Enter':
        case 'Tab':
            if (autocompleteState.selectedIndex >= 0) {
                e.preventDefault();
                // Call appropriate select function based on current level
                if (autocompleteState.currentLevel === 'sub') {
                    selectSubcommand(autocompleteState.selectedIndex);
                } else {
                    selectMainCommand(autocompleteState.selectedIndex);
                }
                return true;
            }
            break;

        case 'Escape':
            e.preventDefault();
            hideAutocomplete();
            return true;
    }

    return false;
}

// Update visual selection
function updateAutocompleteSelection() {
    const items = document.querySelectorAll('.autocomplete-item');
    items.forEach((item, index) => {
        if (index === autocompleteState.selectedIndex) {
            item.classList.add('selected');
            item.scrollIntoView({ block: 'nearest' });
        } else {
            item.classList.remove('selected');
        }
    });
}

// Select a main command
function selectMainCommand(index) {
    const cmd = autocompleteState.filteredCommands[index];
    if (!cmd) return;

    const input = document.getElementById('chat-input');
    const text = input.value;
    const cursorPos = input.selectionStart;

    // Find the slash command position
    const beforeCursor = text.substring(0, cursorPos);
    const match = beforeCursor.match(/\/([\w]*)$/);

    if (match) {
        const matchStart = beforeCursor.length - match[0].length;
        const afterCursor = text.substring(cursorPos);

        // Check if command has subcommands
        const hasSubcommands = cmd.subcommands && cmd.subcommands.length > 0;

        // Replace with selected command
        const newText = text.substring(0, matchStart) + cmd.name + ' ' + afterCursor;
        input.value = newText;

        // Set cursor after command
        const newCursorPos = matchStart + cmd.name.length + 1;
        input.setSelectionRange(newCursorPos, newCursorPos);

        // If command has subcommands, keep autocomplete open and show subcommands
        if (hasSubcommands) {
            // Trigger input event to show subcommands
            setTimeout(() => {
                handleAutocompleteInput(input);
            }, 0);
        } else {
            hideAutocomplete();
        }
    }

    input.focus();
}

// Select a subcommand
function selectSubcommand(index) {
    const subcmd = autocompleteState.filteredCommands[index];
    if (!subcmd) return;

    const input = document.getElementById('chat-input');
    const text = input.value;
    const cursorPos = input.selectionStart;

    // Find the command + subcommand position
    const beforeCursor = text.substring(0, cursorPos);
    const match = beforeCursor.match(/\/([\w]+)\s+(\w*)$/);

    if (match) {
        const matchStart = beforeCursor.length - match[0].length;
        const afterCursor = text.substring(cursorPos);

        // Replace with main command + subcommand
        const newText = text.substring(0, matchStart) +
                       autocompleteState.currentMainCommand + ' ' +
                       subcmd.name + ' ' + afterCursor;
        input.value = newText;

        // Set cursor after subcommand
        const newCursorPos = matchStart +
                            autocompleteState.currentMainCommand.length + 1 +
                            subcmd.name.length + 1;
        input.setSelectionRange(newCursorPos, newCursorPos);
    }

    hideAutocomplete();
    input.focus();
}

// ============================================================================
// Capability Governance Views (Task #29)
// ============================================================================

function renderCapabilityDashboardView(container) {
    if (!window.CapabilityDashboardView) {
        container.innerHTML = '<div class="p-6 text-red-500">CapabilityDashboardView not loaded</div>';
        return;
    }
    state.currentViewInstance = new CapabilityDashboardView(container);
}

function renderDecisionTimelineView(container) {
    if (!window.DecisionTimelineView) {
        container.innerHTML = '<div class="p-6 text-red-500">DecisionTimelineView not loaded</div>';
        return;
    }
    window.currentDecisionTimelineView = new DecisionTimelineView(container);
    state.currentViewInstance = window.currentDecisionTimelineView;
}

function renderActionLogView(container) {
    if (!window.ActionExecutionLogView) {
        container.innerHTML = '<div class="p-6 text-red-500">ActionExecutionLogView not loaded</div>';
        return;
    }
    window.currentActionLogView = new ActionExecutionLogView(container);
    state.currentViewInstance = window.currentActionLogView;
}

function renderEvidenceChainView(container) {
    if (!window.EvidenceChainView) {
        container.innerHTML = '<div class="p-6 text-red-500">EvidenceChainView not loaded</div>';
        return;
    }
    state.currentViewInstance = new EvidenceChainView(container);
}

function renderGovernanceAuditView(container) {
    if (!window.GovernanceAuditView) {
        container.innerHTML = '<div class="p-6 text-red-500">GovernanceAuditView not loaded</div>';
        return;
    }
    window.currentGovernanceAuditView = new GovernanceAuditView(container);
    state.currentViewInstance = window.currentGovernanceAuditView;
}

function renderAgentMatrixView(container) {
    if (!window.AgentCapabilityMatrixView) {
        container.innerHTML = '<div class="p-6 text-red-500">AgentCapabilityMatrixView not loaded</div>';
        return;
    }
    window.currentAgentCapabilityMatrixView = new AgentCapabilityMatrixView(container);
    state.currentViewInstance = window.currentAgentCapabilityMatrixView;
}

// ===================================================================
// Chat Voice Integration
// ===================================================================

/**
 * ChatVoiceManager - Manages voice interaction in Chat
 *
 * 方案 A：完整语音对话循环
 * - handsfree 模式：录音 → 转录 → 自动发送 → AI 回复（文本+语音）→ 可继续对话
 * - hybrid 模式：录音 → 转录 → 插入输入框 → 用户编辑/发送 → AI 回复（文本+语音）
 */
class ChatVoiceManager {
    constructor() {
        this.state = 'idle'; // idle, recording, processing
        this.micCapture = null;
        this.voiceWS = null;
        this.voiceSessionId = null;
        this.partialTranscript = '';
        this.finalTranscript = '';

        // 语音对话模式
        this.mode = 'handsfree'; // 'handsfree' | 'hybrid'

        // TTS 音频播放器（复用 VoiceAudioPlayer）
        this.audioPlayer = null;

        this.button = document.getElementById('voice-input-btn');
        this.input = document.getElementById('chat-input');
        this.preview = document.getElementById('voice-transcript-preview');

        this.init();
    }

    init() {
        console.log('[ChatVoice] Initializing...');
        this.button.addEventListener('click', () => this.toggle());
        this.updateButtonUI();

        // 初始化 TTS 音频播放器
        this.initAudioPlayer();

        // 从 localStorage 恢复模式
        const savedMode = localStorage.getItem('chat_voice_mode');
        if (savedMode === 'hybrid' || savedMode === 'handsfree') {
            this.mode = savedMode;
        }
        console.log('[ChatVoice] Mode:', this.mode);
    }

    /**
     * 初始化 TTS 音频播放器
     */
    initAudioPlayer() {
        try {
            if (window.VoiceAudioPlayer) {
                this.audioPlayer = new VoiceAudioPlayer();
                console.log('[ChatVoice] Audio player initialized');
            } else {
                console.warn('[ChatVoice] VoiceAudioPlayer not available, TTS playback disabled');
            }
        } catch (error) {
            console.error('[ChatVoice] Failed to initialize audio player:', error);
        }
    }

    async toggle() {
        if (this.state === 'idle') {
            await this.startRecording();
        } else if (this.state === 'recording') {
            await this.stopRecording();
        }
    }

    async startRecording() {
        try {
            console.log('[ChatVoice] Starting recording...');
            this.setState('processing');

            // 1. Create voice session
            const sessionResponse = await fetch('/api/voice/sessions', withCsrfToken({
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    mode: 'chat_input',
                    language: 'auto'
                })
            }));

            if (!sessionResponse.ok) {
                throw new Error('Failed to create voice session');
            }

            const sessionData = await sessionResponse.json();
            this.voiceSessionId = sessionData.data.session_id;
            console.log('[ChatVoice] Voice session created:', this.voiceSessionId);

            // 2. Connect WebSocket
            this.voiceWS = new VoiceWebSocket();
            this.setupWebSocketHandlers();
            await this.voiceWS.connect(this.voiceSessionId);

            // 3. Resume audio context
            await this.voiceWS.resumeAudioContext();

            // 4. Start microphone capture
            this.micCapture = new MicCapture((pcmData) => {
                if (this.voiceWS && this.voiceWS.isOpen()) {
                    this.voiceWS.sendAudioChunk(pcmData);
                }
            });

            await this.micCapture.start();

            // Update state
            this.setState('recording');
            this.showPreview('Listening...');
            Toast.success('Recording started');

        } catch (error) {
            console.error('[ChatVoice] Failed to start recording:', error);
            this.setState('idle');
            this.hidePreview();

            if (error.name === 'NotAllowedError') {
                Toast.error('Microphone permission denied');
            } else if (error.name === 'NotFoundError') {
                Toast.error('No microphone found');
            } else {
                Toast.error('Failed to start recording: ' + error.message);
            }

            this.cleanup();
        }
    }

    async stopRecording() {
        try {
            console.log('[ChatVoice] Stopping recording...');
            this.setState('processing');

            // Stop microphone
            if (this.micCapture) {
                this.micCapture.stop();
                this.micCapture = null;
            }

            // Send audio end signal
            if (this.voiceWS && this.voiceWS.isOpen()) {
                this.voiceWS.sendAudioEnd();
            }

            // Wait for final transcript
            await new Promise(resolve => setTimeout(resolve, 1000));

            // 处理转录文本（根据模式）
            if (this.finalTranscript && this.finalTranscript.trim()) {
                if (this.mode === 'handsfree') {
                    // 方案 A：自动发送消息
                    console.log('[ChatVoice] Handsfree mode: auto-sending message');
                    await this.sendVoiceMessage(this.finalTranscript);
                    Toast.success('Voice message sent');

                    // 隐藏预览
                    this.hidePreview();

                    // 保持 WebSocket 连接，等待 assistant 回复（对话循环）
                    this.cleanup(true); // keepSession = true

                } else {
                    // Hybrid 模式：插入输入框（旧行为）
                    console.log('[ChatVoice] Hybrid mode: inserting to input');
                    this.insertTextIntoInput(this.finalTranscript);
                    Toast.success('Transcript inserted');

                    // 完全清理资源
                    this.cleanup(false); // keepSession = false
                    this.hidePreview();
                }
            } else {
                // 没有转录内容，完全清理资源
                this.cleanup(false);
                this.hidePreview();
            }

            // 更新状态
            this.setState('idle');

        } catch (error) {
            console.error('[ChatVoice] Failed to stop recording:', error);
            Toast.error('Error stopping recording');
            this.cleanup();
            this.setState('idle');
            this.hidePreview();
        }
    }

    setupWebSocketHandlers() {
        // ========== STT 事件 ==========
        // Partial transcript (real-time)
        this.voiceWS.on('stt.partial', (data) => {
            this.partialTranscript = data.text;
            this.showPreview(data.text);
        });

        // Final transcript
        this.voiceWS.on('stt.final', (data) => {
            this.finalTranscript = data.text;
            this.partialTranscript = '';
            this.showPreview(data.text);
            console.log('[ChatVoice] Final transcript:', data.text);
        });

        // ========== Assistant 文本响应 ==========
        this.voiceWS.on('assistant.text', (data) => {
            const { text, timestamp } = data;
            const isComplete = data.isComplete !== false; // 默认为 true

            console.log('[ChatVoice] Assistant text:', { text, isComplete });

            // 添加到 Chat 消息列表
            this.addAssistantMessage(text, {
                source: 'voice',
                session_id: this.voiceSessionId,
                isComplete,
                timestamp
            });
        });

        // ========== TTS 播放事件 ==========
        this.voiceWS.on('tts.start', (data) => {
            console.log('[ChatVoice] TTS started:', data.requestId);

            // 重置播放器，准备接收新的音频流
            if (this.audioPlayer) {
                this.audioPlayer.reset();
            }
        });

        this.voiceWS.on('tts.chunk', (data) => {
            console.log('[ChatVoice] TTS chunk received');
            // handleTTSChunk 在 VoiceWebSocket 中自动处理
            // 音频会自动入队并播放
        });

        this.voiceWS.on('tts.end', (data) => {
            console.log('[ChatVoice] TTS ended:', data.requestId);
            // TTS 播放完毕，可以准备下次录音（可选）
        });

        // ========== Barge-in 控制 ==========
        this.voiceWS.on('control.stop_playback', (data) => {
            console.log('[ChatVoice] Barge-in: stop playback');

            // 立即停止 TTS 播放
            if (this.audioPlayer) {
                this.audioPlayer.stopPlayback();
            }
        });

        // ========== 会话事件 ==========
        this.voiceWS.on('session.complete', (data) => {
            console.log('[ChatVoice] Session complete');
            // 会话完成，清理资源
            this.cleanup();
        });

        // ========== 错误和连接 ==========
        this.voiceWS.on('error', (data) => {
            console.error('[ChatVoice] WebSocket error:', data);
            Toast.error('Voice error: ' + data.error);
            this.stopRecording();
        });

        this.voiceWS.on('disconnected', () => {
            if (this.state === 'recording') {
                Toast.warning('Connection lost');
                this.stopRecording();
            }
        });
    }

    setState(newState) {
        this.state = newState;
        this.updateButtonUI();
    }

    updateButtonUI() {
        const icon = this.button.querySelector('.material-icons');

        // Remove all state classes
        this.button.classList.remove('voice-idle', 'voice-recording', 'voice-processing');

        switch (this.state) {
            case 'idle':
                icon.textContent = 'mic';
                this.button.classList.add('voice-idle');
                this.button.title = 'Start voice input';
                break;

            case 'recording':
                icon.textContent = 'mic';
                this.button.classList.add('voice-recording');
                this.button.title = 'Stop recording';
                break;

            case 'processing':
                icon.textContent = 'mic_off';
                this.button.classList.add('voice-processing');
                this.button.title = 'Processing...';
                break;
        }
    }

    showPreview(text) {
        if (!this.preview) return;

        const textEl = this.preview.querySelector('.transcript-text');
        if (textEl) {
            textEl.textContent = text;
        }

        this.preview.style.display = 'block';
    }

    hidePreview() {
        if (this.preview) {
            this.preview.style.display = 'none';
        }
    }

    insertTextIntoInput(text) {
        if (!this.input) return;

        const currentValue = this.input.value.trim();
        this.input.value = currentValue ? `${currentValue} ${text}` : text;

        // Focus input
        this.input.focus();

        // Trigger input event to update UI
        this.input.dispatchEvent(new Event('input'));

        // Optional: Auto-send (commented out by default)
        // sendMessage();
    }

    /**
     * 添加 Assistant 消息到 Chat 列表
     * @param {string} text - 消息文本
     * @param {object} metadata - 元数据
     */
    addAssistantMessage(text, metadata = {}) {
        const messagesDiv = document.getElementById('messages');
        if (!messagesDiv) {
            console.warn('[ChatVoice] Messages container not found');
            return;
        }

        // 创建消息元素（带语音标记）
        const msgElement = createMessageElement('assistant', text, {
            ...metadata,
            source: 'voice', // 标记为语音消息
            voice_icon: true // 显示语音图标
        });

        // 添加到消息列表
        messagesDiv.appendChild(msgElement);

        // 自动滚动到底部
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

        console.log('[ChatVoice] Assistant message added to chat');
    }

    /**
     * 发送用户消息（handsfree 模式）
     * @param {string} text - 消息文本
     */
    async sendVoiceMessage(text) {
        if (!text || !text.trim()) {
            console.warn('[ChatVoice] Empty message, skipping send');
            return;
        }

        const messagesDiv = document.getElementById('messages');
        if (!messagesDiv) return;

        // 添加用户消息到 UI（带语音标记）
        const userMsg = createMessageElement('user', text, {
            source: 'voice',
            voice_icon: true
        });
        messagesDiv.appendChild(userMsg);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

        console.log('[ChatVoice] Sending voice message:', text);

        // 获取当前 provider/model 配置
        const providerEl = document.getElementById('model-provider');
        const modelEl = document.getElementById('model-name');
        const modelTypeEl = document.getElementById('model-type');

        const metadata = {
            source: 'voice',
            voice_session_id: this.voiceSessionId
        };

        if (modelTypeEl && modelTypeEl.value) {
            metadata.model_type = modelTypeEl.value;
        }
        if (providerEl && providerEl.value) {
            metadata.provider = providerEl.value;
        }
        if (modelEl && modelEl.value) {
            metadata.model = modelEl.value;
        }

        // 通过消息队列发送（复用现有的 sendMessage 逻辑）
        const sent = await messageQueue.enqueue({
            type: 'user_message',
            content: text,
            metadata: metadata,
        });

        if (!sent) {
            console.error('[ChatVoice] Failed to send message');
            Toast.error('Failed to send voice message');

            // 显示错误消息
            const errorMsg = createMessageElement('assistant', '⚠️ Failed to send voice message. Please try again.');
            messagesDiv.appendChild(errorMsg);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
    }

    /**
     * 切换语音对话模式
     * @param {string} mode - 'handsfree' | 'hybrid'
     */
    setMode(mode) {
        if (mode !== 'handsfree' && mode !== 'hybrid') {
            console.warn('[ChatVoice] Invalid mode:', mode);
            return;
        }

        this.mode = mode;
        localStorage.setItem('chat_voice_mode', mode);
        console.log('[ChatVoice] Mode changed to:', mode);

        Toast.info(`Voice mode: ${mode === 'handsfree' ? 'Hands-free (auto-send)' : 'Hybrid (manual-send)'}`);
    }

    /**
     * 清理资源
     * @param {boolean} keepSession - 是否保留 session 和 WebSocket（用于对话循环）
     */
    cleanup(keepSession = false) {
        // 停止麦克风
        if (this.micCapture) {
            this.micCapture.stop();
            this.micCapture = null;
        }

        // 清理转录缓存
        this.partialTranscript = '';
        this.finalTranscript = '';

        // 根据模式决定是否保留 session
        if (!keepSession) {
            // 关闭 WebSocket
            if (this.voiceWS) {
                this.voiceWS.close();
                this.voiceWS = null;
            }

            // 停止 session via API
            if (this.voiceSessionId) {
                fetch(`/api/voice/sessions/${this.voiceSessionId}/stop`, withCsrfToken({
                    method: 'POST'
                })).catch(err => console.warn('[ChatVoice] Failed to stop session:', err));

                this.voiceSessionId = null;
            }

            // 停止音频播放
            if (this.audioPlayer) {
                this.audioPlayer.reset();
            }

            console.log('[ChatVoice] Full cleanup completed');
        } else {
            console.log('[ChatVoice] Partial cleanup (keeping session for next turn)');
        }
    }
}

// Global chat voice manager instance
let chatVoiceManager = null;

/**
 * Initialize Chat voice interaction
 */
function initializeChatVoice() {
    try {
        // Check if required classes are available
        if (!window.MicCapture || !window.VoiceWebSocket) {
            console.warn('[ChatVoice] MicCapture or VoiceWebSocket not available');
            // Fallback to placeholder
            document.getElementById('voice-input-btn').addEventListener('click', () => {
                Toast.warning('Voice feature requires microphone support');
            });
            return;
        }

        chatVoiceManager = new ChatVoiceManager();
        console.log('[ChatVoice] Initialized successfully');

    } catch (error) {
        console.error('[ChatVoice] Failed to initialize:', error);
        // Fallback to placeholder
        document.getElementById('voice-input-btn').addEventListener('click', () => {
            Toast.error('Voice feature unavailable');
        });
    }
}
