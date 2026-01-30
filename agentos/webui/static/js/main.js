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
    currentSession: 'main',
    websocket: null,
    healthCheckInterval: null,
    allSessions: [],
    providerStatusInterval: null,
    contextStatusInterval: null,
    currentProvider: null,
    currentViewInstance: null, // PR-2: Track current view instance for cleanup
    projectSelector: null, // Task #18: Project selector component
};

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

    // Setup WebSocket lifecycle hooks (Safari bfcache, visibility, focus)
    setupWebSocketLifecycle();

    // Load initial view (restore last view or default to chat)
    const lastView = localStorage.getItem('agentos_current_view') || 'chat';
    loadView(lastView);

    // Update navigation active state
    updateNavigationActive(lastView);

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
    state.currentView = viewName;

    // Save current view to localStorage for page refresh persistence
    localStorage.setItem('agentos_current_view', viewName);

    // Destroy previous view instance if exists
    if (state.currentViewInstance && typeof state.currentViewInstance.destroy === 'function') {
        state.currentViewInstance.destroy();
        state.currentViewInstance = null;
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
                </div>

                <!-- Messages -->
                <div id="messages" class="flex-1 overflow-y-auto p-6 space-y-4 bg-gray-50">
                    <div class="text-center text-gray-500 text-sm">
                        No messages yet. Start a conversation!
                    </div>
                </div>

                <!-- Input Area -->
                <div class="border-t border-gray-200 bg-white p-4">
                    <div class="flex gap-2">
                        <textarea
                            id="chat-input"
                            placeholder="Type your message... (Shift+Enter for new line)"
                            class="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                            rows="2"
                        ></textarea>
                        <button
                            id="send-btn"
                            class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                        >
                            Send
                        </button>
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
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Setup new chat button
    document.getElementById('new-chat-btn').addEventListener('click', createNewChat);

    // Setup clear all sessions button
    document.getElementById('clear-all-sessions-btn').addEventListener('click', clearAllSessions);

    // Setup search
    document.getElementById('session-search').addEventListener('input', (e) => {
        filterConversations(e.target.value);
    });

    // Setup toolbar event handlers
    setupModelToolbar();

    // Setup code block actions (Preview, Copy)
    setupCodeBlockActions();

    // Initialize chat (load sessions and messages)
    initializeChatView();
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
        const response = await fetch('/api/snippets', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

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
    const sessionId = codeblockEl.dataset.sessionId || state.currentSession || 'main';
    const messageId = codeblockEl.dataset.messageId || null;

    // Get current model
    const modelEl = document.getElementById('model-name');
    const model = modelEl?.value || 'claude-3-opus-20240229';

    // Auto-save with minimal metadata
    const now = new Date();
    const defaultTitle = `${language || 'code'} snippet ${now.toISOString().split('T')[0]}`;

    try {
        const response = await fetch('/api/snippets', {
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
        });

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
        const response = await fetch(`/api/snippets/${snippetId}/preview`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preset })
        });

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
        const response = await fetch(`/api/snippets/${snippetId}/materialize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_path: targetPath,
                description: `Write snippet to ${targetPath}`
            })
        });

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
    fetch('/api/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html: wrapped })
    })
    .then(res => res.json())
    .then(data => {
        // Delete previous session if exists
        if (refs.frame._previewSession) {
            fetch(`/api/preview/${refs.frame._previewSession}`, { method: 'DELETE' });
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
        'tomorrow': 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css',
        'okaidia': 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-okaidia.min.css',
        'dracula': 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-dracula.min.css',
        'one-dark': 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-one-dark.min.css',
        'solarized-dark': 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-solarizedlight.min.css',
        'monokai': 'https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-okaidia.min.css' // Using Okaidia as Monokai alternative
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
        fetch('/api/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ html: combined })
        })
        .then(res => res.json())
        .then(data => {
            // Delete previous session if exists
            if (refs.frame._previewSession) {
                fetch(`/api/preview/${refs.frame._previewSession}`, { method: 'DELETE' });
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
        const response = await fetch('/api/share', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ code })
        });

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
function setupWebSocketLifecycle() {
  console.log('[Lifecycle] Setting up WebSocket lifecycle hooks');

  // Safari bfcache: restore connection on pageshow.persisted
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) {
      console.log('[Lifecycle] Page restored from bfcache, reconnecting WebSocket');
      WS.connect();
    }
  });

  // Visibility API: reconnect when page becomes visible
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      console.log('[Lifecycle] Page visible, checking WebSocket');

      if (!WS.ws || WS.ws.readyState !== WebSocket.OPEN) {
        console.log('[Lifecycle] WebSocket not open, reconnecting');
        WS.connect();
      }
    }
  });

  // Focus event: reconnect on window focus
  window.addEventListener('focus', () => {
    console.log('[Lifecycle] Window focused, checking WebSocket');

    if (!WS.ws || WS.ws.readyState !== WebSocket.OPEN) {
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
    idleTime: Date.now() - WS.lastActivity
  });
};

window.wsReconnect = () => {
  console.log('[WS] Manual reconnect triggered');
  WS.connect();
};

// Setup WebSocket
function setupWebSocket() {
    console.log('[WS] setupWebSocket() called, delegating to WS.connect()');
    WS.connect(state.currentSession);
}

// Handle WebSocket message
function handleWebSocketMessage(message) {
    const messagesDiv = document.getElementById('messages');

    // If messages div doesn't exist (not on chat view), only log and return
    if (!messagesDiv) {
        console.log('[WS] Message received but not on chat view, ignoring UI update:', message.type);
        return;
    }

    if (message.type === 'message.start') {
        // Create new assistant message element (empty, will be filled by deltas)
        // Pass metadata for extension detection (Task #11)
        const assistantMsg = createMessageElement('assistant', '', message.metadata || {});
        assistantMsg.dataset.messageId = message.message_id;
        messagesDiv.appendChild(assistantMsg);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        console.log('Started receiving message:', message.message_id);

    } else if (message.type === 'message.delta') {
        // Append content to the last assistant message
        let lastMsg = messagesDiv.lastElementChild;
        if (lastMsg && lastMsg.classList.contains('assistant')) {
            const contentDiv = lastMsg.querySelector('.content');
            contentDiv.textContent += message.content;
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        } else {
            console.warn('Received delta but no assistant message element found');
        }

    } else if (message.type === 'message.end') {
        console.log('Finished receiving message:', message.message_id, message.metadata);

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
        }

    } else if (message.type === 'message.error') {
        // Show error message
        const errorMsg = createMessageElement('assistant', message.content, message.metadata || {});
        errorMsg.classList.add('error');
        messagesDiv.appendChild(errorMsg);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        console.error('Message error:', message.content);

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

    // Send via WS Manager (with auto-reconnect)
    const sent = WS.send({
        type: 'user_message',
        content: content,
        metadata: metadata,
    });

    if (!sent) {
        console.error('[WS] Failed to send message, connection lost');
        // WS.send() already handles reconnection attempt
    }

    // Clear input
    input.value = '';
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

        div.innerHTML = `
            <div class="role">${role}</div>
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

// Create session if it doesn't exist
async function createSession(sessionId) {
    try {
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: sessionId,
                title: sessionId === 'main' ? 'Main Session' : `Session ${sessionId}`
            })
        });

        if (!response.ok) {
            throw new Error(`Failed to create session: ${response.statusText}`);
        }

        console.log(`Session ${sessionId} created successfully`);
        return await response.json();
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

    state.currentSession = sessionId;

    // PR-3: Update session display in toolbar
    updateChatSessionDisplay(sessionId);

    // Reload messages
    await loadMessages();

    // Reconnect WebSocket
    setupWebSocket();

    // Update context status (Task #8)
    loadContextStatus();

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

        // Enable input (PR-3 护栏规则)
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
        // No session - disable input (PR-3 护栏规则)
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
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: `Chat ${new Date().toLocaleString()}`,
                tags: ['user-created'],
            }),
        });

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
        const response = await fetch(`/api/sessions/${sessionId}`, {
            method: 'DELETE',
        });

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
        const response = await fetch('/api/sessions', {
            method: 'DELETE',
        });

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

// Format time ago (helper function)
function formatTimeAgo(timestamp) {
    const now = new Date();
    const then = new Date(timestamp);
    const seconds = Math.floor((now - then) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;

    return then.toLocaleDateString();
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
    modelProviderSelect.addEventListener('change', () => {
        state.currentProvider = modelProviderSelect.value;
        // Save to localStorage
        localStorage.setItem('agentos_model_provider', modelProviderSelect.value);
        loadAvailableModels();
        refreshProviderStatus();
    });

    // Model change handler
    modelNameSelect.addEventListener('change', () => {
        // Model selected - status will be reflected in next status poll
        console.log('Model selected:', modelNameSelect.value);
        // Save to localStorage
        if (modelNameSelect.value) {
            localStorage.setItem('agentos_model_name', modelNameSelect.value);
        }
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
    } else {
        state.currentProvider = 'ollama';
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
    const statusEl = document.getElementById('model-link-status');
    if (!statusEl) {
        // Element doesn't exist in current view
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
            break;
        case 'CONNECTING':
            statusEl.classList.add('bg-blue-50');
            dot.classList.add('bg-blue-500', 'animate-pulse');
            text.textContent = 'Connecting...';
            text.className = 'text-sm font-medium text-blue-700';
            break;
        case 'READY':
            statusEl.classList.add('bg-green-50');
            dot.classList.add('bg-green-500');
            const latencyText = statusData?.latency_ms ? ` (${Math.round(statusData.latency_ms)}ms)` : '';
            text.textContent = `Ready${latencyText}`;
            text.className = 'text-sm font-medium text-green-700';
            break;
        case 'DEGRADED':
            statusEl.classList.add('bg-yellow-50');
            dot.classList.add('bg-yellow-500');
            text.textContent = 'Degraded';
            text.className = 'text-sm font-medium text-yellow-700';
            break;
        case 'ERROR':
            statusEl.classList.add('bg-red-50');
            dot.classList.add('bg-red-500');
            text.textContent = 'Error';
            text.className = 'text-sm font-medium text-red-700';
            break;
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
    try {
        const response = await fetch('/api/providers/status');
        const data = await response.json();

        // Find current provider status
        const providerEl = document.getElementById('model-provider');
        const modelEl = document.getElementById('model-name');
        const currentProvider = state.currentProvider || (providerEl ? providerEl.value : null);
        const currentModel = modelEl ? modelEl.value : null;

        if (!currentProvider) {
            // No provider selected or element doesn't exist
            return;
        }

        // Try exact match first
        let providerStatus = data.providers.find(p => p.id === currentProvider);

        // If no exact match, try to find instances with prefix match
        if (!providerStatus) {
            const prefix = `${currentProvider}:`;
            const matchingProviders = data.providers.filter(p => p.id.startsWith(prefix));

            if (matchingProviders.length > 0) {
                // If a model is selected, try to find the specific instance for that model
                if (currentModel) {
                    // Try to match instance by checking if model comes from this instance
                    // For now, just pick the first READY instance
                    providerStatus = matchingProviders.find(p => p.state === 'READY') || matchingProviders[0];
                } else {
                    // No model selected, pick first READY instance or first instance
                    providerStatus = matchingProviders.find(p => p.state === 'READY') || matchingProviders[0];
                }
            }
        }

        if (providerStatus) {
            updateModelLinkStatus(providerStatus.state, providerStatus);
        } else {
            // Provider not found, show disconnected
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
        const response = await fetch(`/api/providers/${providerId}/instances/start`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('admin_token') || ''}`
            },
            body: JSON.stringify({ instance_id: instanceId })
        });
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
        const response = await fetch(`/api/providers/${providerId}/instances/stop`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('admin_token') || ''}`
            },
            body: JSON.stringify({ instance_id: instanceId })
        });
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
        const response = await fetch('/api/selfcheck', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: state.currentSession,
                include_network: true,  // Actively probe all providers for accurate status
                include_context: true,
            }),
        });

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
            </div>
        `;
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

// PR-4: Skills View
function renderSkillsView(container) {
    // Clear previous view
    if (state.currentViewInstance && state.currentViewInstance.destroy) {
        state.currentViewInstance.destroy();
    }

    // Create new view instance
    state.currentViewInstance = new SkillsView(container);
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
        const response = await fetch('/api/providers/cloud/config', {
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
        });

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
function formatTimestamp(isoString) {
    if (!isoString) return 'Unknown';

    try {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffSec = Math.floor(diffMs / 1000);

        if (diffSec < 60) {
            return `${diffSec}s ago`;
        } else if (diffSec < 3600) {
            return `${Math.floor(diffSec / 60)}m ago`;
        } else if (diffSec < 86400) {
            return `${Math.floor(diffSec / 3600)}h ago`;
        } else {
            return date.toLocaleDateString();
        }
    } catch (e) {
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
        const response = await fetch(`/api/providers/cloud/config/${providerId}`, {
            method: 'DELETE',
        });

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
    const sessionId = state.currentSession || 'main';

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
    const sessionId = state.currentSession || 'main';
    const memoryEnabled = document.getElementById('memory-enabled').checked;
    const ragEnabled = document.getElementById('rag-enabled').checked;
    const memoryNamespace = document.getElementById('memory-namespace').value.trim();
    const ragIndex = document.getElementById('rag-index').value.trim();

    if (memoryEnabled && !memoryNamespace) {
        Dialog.alert('Memory namespace is required', { title: 'Validation Error' });
        return;
    }

    try {
        const response = await fetch('/api/context/attach', {
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
        });

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
    const sessionId = state.currentSession || 'main';

    const confirmed = await Dialog.confirm('Detach all context from this session?', {
        title: 'Detach Context',
        confirmText: 'Detach',
        danger: true
    });
    if (!confirmed) {
        return;
    }

    try {
        const response = await fetch(`/api/context/detach?session_id=${sessionId}`, {
            method: 'POST',
        });

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
    const sessionId = state.currentSession || 'main';

    try {
        const response = await fetch('/api/context/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
            }),
        });

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
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                if (!response.ok) throw new Error(response.statusText);
                return response.json();
            },
            put: async (url, data) => {
                const response = await fetch(url, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                if (!response.ok) throw new Error(response.statusText);
                return response.json();
            },
            delete: async (url) => {
                const response = await fetch(url, {method: 'DELETE'});
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
                <span class="budget-usage" id="budget-usage">bar_chart --</span>
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

    usageEl.textContent = `bar_chart Budget: ` + usedK + `k/` + totalK + `k (` + percent + `%)`;

    // Status configuration
    const statusConfig = {
        safe: {
            class: 'badge-safe',
            icon: 'circle',
            text: 'Safe'
        },
        warning: {
            class: 'badge-warning',
            icon: 'circle',
            text: 'Warning',
            hint: 'Context nearing limit. Consider /summary.'
        },
        critical: {
            class: 'badge-critical',
            icon: 'circle',
            text: 'Critical',
            hint: 'Context full! Oldest messages truncated.'
        }
    };

    const status = statusConfig[budgetData.watermark] || statusConfig.safe;
    statusEl.className = `budget-status ` + status.class;
    statusEl.innerHTML = status.icon + ` ` + status.text + (status.hint ? `<br><small>` + status.hint + `</small>` : '');

    indicator.style.display = 'flex';

    console.log(`Budget indicator updated: ` + percent + `% used (` + budgetData.watermark + `)`);
}

/**
 * Show detailed budget breakdown modal
 * @param {Object} budgetData - Budget data
 */
function showBudgetDetails(budgetData) {
    const breakdown = budgetData.breakdown;
    const total = budgetData.budget_tokens;

    const bars = [
        renderBudgetBar('System Prompt', breakdown.system, total),
        renderBudgetBar('Conversation', breakdown.window, total),
        renderBudgetBar('RAG Context', breakdown.rag, total),
        renderBudgetBar('Memory Facts', breakdown.memory, total)
    ].join('');

    const html = `<div class="budget-detail-modal"><h3>Token Budget Breakdown</h3><div class="budget-bars">` + bars + `</div><p class="budget-tip">lightbulb Tip: Use /context to see detailed breakdown</p></div>`;

    // Use existing modal system if available, otherwise create simple modal
    if (window.Dialog && window.Dialog.alert) {
        window.Dialog.alert(html, { title: 'Token Budget Details', isHtml: true });
    } else {
        // Fallback: simple alert
        const pct = (x, t) => ((x / t) * 100).toFixed(1);
        const msg = 'Token Budget Details\n\n' +
            'System: ' + breakdown.system.toLocaleString() + ' (' + pct(breakdown.system, total) + '%)\n' +
            'Window: ' + breakdown.window.toLocaleString() + ' (' + pct(breakdown.window, total) + '%)\n' +
            'RAG: ' + breakdown.rag.toLocaleString() + ' (' + pct(breakdown.rag, total) + '%)\n' +
            'Memory: ' + breakdown.memory.toLocaleString() + ' (' + pct(breakdown.memory, total) + '%)';
        alert(msg);
    }
}

/**
 * Render a single budget bar
 * @param {string} label - Component label
 * @param {number} tokens - Token count
 * @param {number} total - Total budget
 * @returns {string} HTML string
 */
function renderBudgetBar(label, tokens, total) {
    const percent = ((tokens / total) * 100).toFixed(1);
    const width = Math.min(percent, 100);

    // Determine fill class based on percentage
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

    return `<div class="budget-bar-item"><label>` + safeLabel + `: ` + tokens.toLocaleString() + ` (` + percent + `%)</label><div class="progress-bar"><div class="progress-fill ` + fillClass + `" style="width: ` + width + `%"></div></div></div>`;
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
