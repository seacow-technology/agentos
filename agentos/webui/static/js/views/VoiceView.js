/**
 * VoiceView - Voice interaction panel
 *
 * Provides a UI for voice-based interaction with the assistant:
 * - Microphone capture with start/stop controls
 * - Real-time speech-to-text transcription display
 * - Assistant responses in chat bubble format
 * - Status indicators (Idle/Recording/Processing)
 */

class VoiceView {
    constructor(container) {
        this.container = container;
        this.micCapture = null;
        this.voiceWS = null;
        this.sessionId = null;
        this.status = 'idle'; // idle, recording, processing
        this.transcriptPartial = '';
        this.transcriptFinal = [];
        this.assistantMessages = [];

        this.init();
    }

    async init() {
        this.render();
        this.setupEventListeners();
        console.log('[VoiceView] Initialized');

        // Initialize provider/model selectors
        await this.initializeModelSelectors();

        // Auto-create session when entering Voice Interaction page
        await this.createSession();
    }

    /**
     * Create a new voice session
     */
    async createSession() {
        try {
            console.log('[VoiceView] Creating new voice session...');
            this.updateStatus('processing');

            const sessionResponse = await fetch('/api/voice/sessions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': getCsrfToken() || ''
                },
                body: JSON.stringify({
                    mode: 'interactive',
                    language: 'auto'
                })
            });

            if (!sessionResponse.ok) {
                throw new Error('Failed to create voice session');
            }

            const sessionData = await sessionResponse.json();
            this.sessionId = sessionData.data.session_id;

            console.log('[VoiceView] Session created:', this.sessionId);
            this.updateSessionInfo(this.sessionId, 'Session Ready');

            // Connect WebSocket
            this.voiceWS = new VoiceWebSocket();
            this.setupWebSocketHandlers();
            await this.voiceWS.connect(this.sessionId);

            this.updateStatus('idle');
            this.updateSessionInfo(this.sessionId, 'Connected');
            Toast.success('Voice session ready');

        } catch (error) {
            console.error('[VoiceView] Failed to create session:', error);
            this.updateStatus('idle');
            Toast.error('Failed to create voice session: ' + error.message);
            throw error;
        }
    }

    render() {
        this.container.innerHTML = `
            <div class="voice-view">
                <div class="view-header">
                    <div>
                        <h1>Voice Interaction</h1>
                        <p class="text-sm text-gray-600 mt-1">Talk with your assistant using voice</p>
                    </div>

                    <!-- Provider/Model Selector -->
                    <div class="flex items-center gap-3">
                        <!-- Model Type -->
                        <select id="voice-model-type" class="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                            <option value="local">Local</option>
                            <option value="cloud">Cloud</option>
                        </select>

                        <!-- Provider -->
                        <select id="voice-model-provider" class="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white min-w-32">
                            <option value="ollama">Ollama</option>
                            <option value="lmstudio">LM Studio</option>
                            <option value="llamacpp">llama.cpp</option>
                        </select>

                        <!-- Model -->
                        <select id="voice-model-name" class="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white min-w-48">
                            <option value="">Select model...</option>
                        </select>

                        <!-- Model Link Status -->
                        <div id="voice-model-status" class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-100">
                            <div class="w-2 h-2 rounded-full bg-gray-400"></div>
                            <span class="text-sm font-medium text-gray-600">Disconnected</span>
                        </div>
                    </div>
                </div>

                <div class="voice-panel">
                    <!-- Control Panel -->
                    <div class="voice-controls">
                        <button class="btn-voice-start" id="voice-start-btn">
                            <span class="material-icons">mic</span>
                            Start Recording
                        </button>
                        <button class="btn-voice-stop" id="voice-stop-btn" disabled>
                            <span class="material-icons">mic_off</span>
                            Stop Recording
                        </button>
                        <div class="voice-status-container">
                            <span class="voice-status idle" id="voice-status">
                                <span class="material-icons md-18">radio_button_unchecked</span>
                                Idle
                            </span>
                        </div>
                    </div>

                    <!-- Transcript Display -->
                    <div class="voice-section">
                        <div class="section-header">
                            <h3>Your Speech</h3>
                            <button class="btn-icon" id="clear-transcript-btn" title="Clear transcript">
                                <span class="material-icons md-18">clear_all</span>
                            </button>
                        </div>
                        <div class="voice-transcript" id="voice-transcript">
                            <div class="transcript-placeholder">
                                Your speech will appear here in real-time...
                            </div>
                        </div>
                    </div>

                    <!-- Assistant Response Display -->
                    <div class="voice-section">
                        <div class="section-header">
                            <h3>Assistant Response</h3>
                            <button class="btn-icon" id="clear-assistant-btn" title="Clear responses">
                                <span class="material-icons md-18">clear_all</span>
                            </button>
                        </div>
                        <div class="voice-assistant" id="voice-assistant">
                            <div class="assistant-placeholder">
                                Assistant responses will appear here...
                            </div>
                        </div>
                    </div>

                    <!-- Connection Info -->
                    <div class="voice-info" id="voice-info">
                        <div class="info-item">
                            <span class="info-label">Session ID:</span>
                            <span class="info-value" id="session-id-value">Not connected</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Connection:</span>
                            <span class="info-value" id="connection-status">Disconnected</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    setupEventListeners() {
        // Start button
        this.container.querySelector('#voice-start-btn').addEventListener('click', () => {
            this.onStart();
        });

        // Stop button
        this.container.querySelector('#voice-stop-btn').addEventListener('click', () => {
            this.onStop();
        });

        // Clear transcript button
        this.container.querySelector('#clear-transcript-btn').addEventListener('click', () => {
            this.clearTranscript();
        });

        // Clear assistant button
        this.container.querySelector('#clear-assistant-btn').addEventListener('click', () => {
            this.clearAssistant();
        });

        // Provider/Model selectors
        const modelTypeSelect = this.container.querySelector('#voice-model-type');
        const modelProviderSelect = this.container.querySelector('#voice-model-provider');
        const modelNameSelect = this.container.querySelector('#voice-model-name');

        modelTypeSelect.addEventListener('change', (e) => {
            this.onModelTypeChange(e.target.value);
        });

        modelProviderSelect.addEventListener('change', () => {
            this.onProviderChange(modelProviderSelect.value);
        });

        modelNameSelect.addEventListener('change', () => {
            this.onModelChange(modelNameSelect.value);
        });
    }

    /**
     * Handle model type change
     */
    onModelTypeChange(type) {
        console.log('[VoiceView] Model type changed to:', type);
        // Update provider options based on type
        const providerSelect = this.container.querySelector('#voice-model-provider');

        if (type === 'local') {
            providerSelect.innerHTML = `
                <option value="ollama">Ollama</option>
                <option value="lmstudio">LM Studio</option>
                <option value="llamacpp">llama.cpp</option>
            `;
        } else {
            providerSelect.innerHTML = `
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
            `;
        }

        // Trigger provider change
        this.onProviderChange(providerSelect.value);
    }

    /**
     * Handle provider change
     */
    async onProviderChange(provider) {
        console.log('[VoiceView] Provider changed to:', provider);
        localStorage.setItem('agentos_voice_provider', provider);

        // Load available models for this provider
        await this.loadAvailableModels(provider);
    }

    /**
     * Handle model change
     */
    onModelChange(model) {
        console.log('[VoiceView] Model changed to:', model);
        if (model) {
            localStorage.setItem('agentos_voice_model', model);
        }
    }

    /**
     * Load available models for provider
     */
    async loadAvailableModels(provider) {
        try {
            const modelSelect = this.container.querySelector('#voice-model-name');
            modelSelect.innerHTML = '<option value="">Loading...</option>';

            const response = await fetch(`/api/providers/${provider}/models`);
            if (!response.ok) {
                throw new Error('Failed to fetch models');
            }

            const data = await response.json();
            const models = data.data || [];

            if (models.length === 0) {
                modelSelect.innerHTML = '<option value="">No models available</option>';
                return;
            }

            modelSelect.innerHTML = models.map(model =>
                `<option value="${model.name}">${model.name}</option>`
            ).join('');

            // Restore saved model or select first
            const savedModel = localStorage.getItem('agentos_voice_model');
            if (savedModel && models.find(m => m.name === savedModel)) {
                modelSelect.value = savedModel;
            } else {
                modelSelect.value = models[0].name;
            }

        } catch (error) {
            console.error('[VoiceView] Failed to load models:', error);
            const modelSelect = this.container.querySelector('#voice-model-name');
            modelSelect.innerHTML = '<option value="">Error loading models</option>';
        }
    }

    /**
     * Initialize provider/model selectors
     */
    async initializeModelSelectors() {
        // Restore saved preferences
        const savedProvider = localStorage.getItem('agentos_voice_provider') || 'ollama';
        const providerSelect = this.container.querySelector('#voice-model-provider');

        if (providerSelect) {
            providerSelect.value = savedProvider;
            await this.loadAvailableModels(savedProvider);
        }
    }

    /**
     * Start voice recording (session already created in init)
     */
    async onStart() {
        try {
            console.log('[VoiceView] Starting recording...');
            this.updateStatus('processing');

            // Check if session exists
            if (!this.sessionId || !this.voiceWS || !this.voiceWS.isOpen()) {
                console.log('[VoiceView] Session not ready, creating new session...');
                await this.createSession();
            }

            // 1. Resume audio context (autoplay policy)
            await this.voiceWS.resumeAudioContext();

            // 2. Start microphone capture
            this.micCapture = new MicCapture((pcmData) => {
                // Send audio chunk to server
                if (this.voiceWS && this.voiceWS.isOpen()) {
                    this.voiceWS.sendAudioChunk(pcmData);
                }
            });

            await this.micCapture.start();

            // Update UI
            this.updateStatus('recording');
            this.container.querySelector('#voice-start-btn').disabled = true;
            this.container.querySelector('#voice-stop-btn').disabled = false;

            console.log('[VoiceView] Recording started');

        } catch (error) {
            console.error('[VoiceView] Failed to start:', error);
            this.updateStatus('idle');

            if (error.name === 'NotAllowedError') {
                Toast.error('Microphone permission denied. Please allow microphone access.');
            } else if (error.name === 'NotFoundError') {
                Toast.error('No microphone found. Please connect a microphone.');
            } else {
                Toast.error('Failed to start recording: ' + error.message);
            }

            this.cleanup();
        }
    }

    /**
     * Stop voice recording session
     */
    async onStop() {
        try {
            console.log('[VoiceView] Stopping voice session...');
            this.updateStatus('processing');

            // 1. Stop microphone
            if (this.micCapture) {
                this.micCapture.stop();
                this.micCapture = null;
            }

            // 2. Send audio end signal
            if (this.voiceWS && this.voiceWS.isOpen()) {
                this.voiceWS.sendAudioEnd();
            }

            // 3. Wait a bit for final processing
            await new Promise(resolve => setTimeout(resolve, 1000));

            // 4. Stop session via API
            if (this.sessionId) {
                await fetch(`/api/voice/sessions/${this.sessionId}/stop`, {
                    method: 'POST',
                    headers: {
                        'X-CSRF-Token': getCsrfToken() || ''
                    }
                });
            }

            // 5. Close WebSocket
            if (this.voiceWS) {
                this.voiceWS.close();
                this.voiceWS = null;
            }

            // Update UI
            this.updateStatus('idle');
            this.container.querySelector('#voice-start-btn').disabled = false;
            this.container.querySelector('#voice-stop-btn').disabled = true;
            this.updateSessionInfo(null, 'Disconnected');

            console.log('[VoiceView] Recording stopped');

        } catch (error) {
            console.error('[VoiceView] Failed to stop:', error);
            Toast.error('Error stopping voice session');
            this.cleanup();
        }
    }

    /**
     * Setup WebSocket event handlers
     */
    setupWebSocketHandlers() {
        // Partial STT result
        this.voiceWS.on('stt.partial', (data) => {
            this.transcriptPartial = data.text;
            this.renderTranscript();
        });

        // Final STT result
        this.voiceWS.on('stt.final', (data) => {
            this.transcriptFinal.push(data.text);
            this.transcriptPartial = '';
            this.renderTranscript();
        });

        // Assistant text response
        this.voiceWS.on('assistant.text', (data) => {
            this.addAssistantMessage(data.text, data.isComplete);
        });

        // TTS events
        this.voiceWS.on('tts.start', (data) => {
            console.log('[VoiceView] TTS started:', data.requestId);
        });

        this.voiceWS.on('tts.chunk', (data) => {
            console.log('[VoiceView] TTS chunk received');
        });

        this.voiceWS.on('tts.end', (data) => {
            console.log('[VoiceView] TTS ended:', data.requestId);
        });

        this.voiceWS.on('control.stop_playback', () => {
            console.log('[VoiceView] Playback stopped (barge-in)');
        });

        // Session complete
        this.voiceWS.on('session.complete', () => {
            console.log('[VoiceView] Session completed');
            this.onStop();
        });

        // Error
        this.voiceWS.on('error', (data) => {
            console.error('[VoiceView] WebSocket error:', data);
            Toast.error('Voice session error: ' + data.error);
        });

        // Connection events
        this.voiceWS.on('connected', () => {
            console.log('[VoiceView] WebSocket connected');
        });

        this.voiceWS.on('disconnected', (data) => {
            console.log('[VoiceView] WebSocket disconnected:', data);
            if (this.status === 'recording') {
                Toast.warning('Connection lost. Attempting to reconnect...');
            }
        });
    }

    /**
     * Update status indicator
     * @param {string} status - Status: idle, recording, processing
     */
    updateStatus(status) {
        this.status = status;
        const statusEl = this.container.querySelector('#voice-status');

        statusEl.className = 'voice-status ' + status;

        const statusConfig = {
            idle: {
                icon: 'radio_button_unchecked',
                text: 'Idle'
            },
            recording: {
                icon: 'fiber_manual_record',
                text: 'Recording'
            },
            processing: {
                icon: 'hourglass_empty',
                text: 'Processing'
            }
        };

        const config = statusConfig[status] || statusConfig.idle;

        statusEl.innerHTML = `
            <span class="material-icons md-18">${config.icon}</span>
            ${config.text}
        `;
    }

    /**
     * Update session info display
     */
    updateSessionInfo(sessionId, connectionStatus) {
        const sessionIdEl = this.container.querySelector('#session-id-value');
        const connectionEl = this.container.querySelector('#connection-status');

        sessionIdEl.textContent = sessionId ? sessionId.substring(0, 12) + '...' : 'Not connected';
        connectionEl.textContent = connectionStatus;
        connectionEl.className = 'info-value ' + (connectionStatus === 'Connected' ? 'status-success' : 'status-idle');
    }

    /**
     * Render transcript display
     */
    renderTranscript() {
        const transcriptEl = this.container.querySelector('#voice-transcript');

        if (this.transcriptFinal.length === 0 && !this.transcriptPartial) {
            transcriptEl.innerHTML = '<div class="transcript-placeholder">Your speech will appear here in real-time...</div>';
            return;
        }

        let html = '';

        // Render final transcripts
        this.transcriptFinal.forEach(text => {
            html += `<div class="transcript-line final">${this.escapeHtml(text)}</div>`;
        });

        // Render partial transcript
        if (this.transcriptPartial) {
            html += `<div class="transcript-line partial">${this.escapeHtml(this.transcriptPartial)}</div>`;
        }

        transcriptEl.innerHTML = html;

        // Auto-scroll to bottom
        transcriptEl.scrollTop = transcriptEl.scrollHeight;
    }

    /**
     * Add assistant message
     */
    addAssistantMessage(text, isComplete = true) {
        // If last message is incomplete, update it
        if (this.assistantMessages.length > 0 && !this.assistantMessages[this.assistantMessages.length - 1].complete) {
            this.assistantMessages[this.assistantMessages.length - 1].text = text;
            this.assistantMessages[this.assistantMessages.length - 1].complete = isComplete;
        } else {
            // Add new message
            this.assistantMessages.push({
                text,
                complete: isComplete,
                timestamp: new Date()
            });
        }

        this.renderAssistant();
    }

    /**
     * Render assistant messages
     */
    renderAssistant() {
        const assistantEl = this.container.querySelector('#voice-assistant');

        if (this.assistantMessages.length === 0) {
            assistantEl.innerHTML = '<div class="assistant-placeholder">Assistant responses will appear here...</div>';
            return;
        }

        let html = '';

        this.assistantMessages.forEach((msg, index) => {
            const className = msg.complete ? 'complete' : 'streaming';
            html += `
                <div class="assistant-message ${className}">
                    <div class="message-header">
                        <span class="material-icons md-18">smart_toy</span>
                        <span class="message-time">${msg.timestamp.toLocaleTimeString()}</span>
                    </div>
                    <div class="message-text">${this.escapeHtml(msg.text)}</div>
                </div>
            `;
        });

        assistantEl.innerHTML = html;

        // Auto-scroll to bottom
        assistantEl.scrollTop = assistantEl.scrollHeight;
    }

    /**
     * Clear transcript
     */
    clearTranscript() {
        this.transcriptFinal = [];
        this.transcriptPartial = '';
        this.renderTranscript();
        Toast.info('Transcript cleared');
    }

    /**
     * Clear assistant messages
     */
    clearAssistant() {
        this.assistantMessages = [];
        this.renderAssistant();
        Toast.info('Assistant messages cleared');
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Cleanup resources
     */
    cleanup() {
        if (this.micCapture) {
            this.micCapture.stop();
            this.micCapture = null;
        }

        if (this.voiceWS) {
            this.voiceWS.close();
            this.voiceWS = null;
        }

        this.sessionId = null;
        this.updateStatus('idle');
        this.updateSessionInfo(null, 'Disconnected');

        this.container.querySelector('#voice-start-btn').disabled = false;
        this.container.querySelector('#voice-stop-btn').disabled = true;
    }

    /**
     * Destroy view and cleanup resources
     */
    destroy() {
        console.log('[VoiceView] Destroying view');
        this.cleanup();
    }
}

// Register view
window.VoiceView = VoiceView;
