/**
 * VoiceWebSocket - WebSocket client for voice streaming
 *
 * Manages WebSocket connection for sending audio chunks and receiving
 * STT (Speech-to-Text) results and assistant responses.
 *
 * Dependencies: VoiceAudioPlayer (audio_player.js)
 */

class VoiceWebSocket {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.sequenceNumber = 0;
        this.eventHandlers = {};
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
        this.reconnectDelay = 1000;
        this.isConnected = false;

        // Initialize audio player for TTS playback
        this.audioPlayer = null;
        this.initAudioPlayer();
    }

    /**
     * Initialize audio player
     */
    initAudioPlayer() {
        try {
            if (window.VoiceAudioPlayer) {
                this.audioPlayer = new VoiceAudioPlayer();
                console.log('[VoiceWS] Audio player initialized');
            } else {
                console.warn('[VoiceWS] VoiceAudioPlayer not available, TTS playback disabled');
            }
        } catch (error) {
            console.error('[VoiceWS] Failed to initialize audio player:', error);
        }
    }

    /**
     * Connect to WebSocket endpoint
     * @param {string} sessionId - Voice session ID
     * @returns {Promise<void>}
     */
    connect(sessionId) {
        return new Promise((resolve, reject) => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                console.warn('[VoiceWS] Already connected');
                resolve();
                return;
            }

            this.sessionId = sessionId;
            this.sequenceNumber = 0;

            // Determine WebSocket URL
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            const wsUrl = `${protocol}//${host}/api/voice/sessions/${sessionId}/events`;

            console.log('[VoiceWS] Connecting to:', wsUrl);

            this.ws = new WebSocket(wsUrl);

            // Connection opened
            this.ws.onopen = () => {
                console.log('[VoiceWS] Connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.emit('connected', { sessionId });
                resolve();
            };

            // Message received
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('[VoiceWS] Failed to parse message:', error, event.data);
                }
            };

            // Connection closed
            this.ws.onclose = (event) => {
                console.log('[VoiceWS] Disconnected:', event.code, event.reason);
                this.isConnected = false;
                this.emit('disconnected', { code: event.code, reason: event.reason });

                // Attempt reconnection if not a clean close
                if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.attemptReconnect();
                }
            };

            // Connection error
            this.ws.onerror = (error) => {
                console.error('[VoiceWS] WebSocket error:', error);
                this.emit('error', { error: 'WebSocket connection error' });
                reject(error);
            };

            // Timeout if connection takes too long
            setTimeout(() => {
                if (this.ws && this.ws.readyState !== WebSocket.OPEN) {
                    console.error('[VoiceWS] Connection timeout');
                    this.ws.close();
                    reject(new Error('WebSocket connection timeout'));
                }
            }, 10000); // 10 second timeout
        });
    }

    /**
     * Handle incoming WebSocket message
     * @param {Object} data - Parsed message data
     */
    handleMessage(data) {
        const { type } = data;

        console.log('[VoiceWS] Received:', type, data);

        switch (type) {
            case 'voice.session.ready':
                // Session is ready to receive audio
                console.log('[VoiceWS] Session ready:', data.session_id);
                this.emit('session.ready', {
                    sessionId: data.session_id,
                    timestamp: data.timestamp
                });
                break;

            case 'stt.partial':
            case 'voice.stt.partial':  // 支持两种格式
                this.emit('stt.partial', { text: data.text, timestamp: data.timestamp });
                break;

            case 'stt.final':
            case 'voice.stt.final':  // 支持两种格式
                this.emit('stt.final', { text: data.text, timestamp: data.timestamp });
                break;

            case 'assistant.text':
                this.emit('assistant.text', {
                    text: data.text,
                    timestamp: data.timestamp,
                    isComplete: data.is_complete
                });
                break;

            case 'assistant.audio':
                this.emit('assistant.audio', {
                    audio: data.audio,
                    format: data.format,
                    timestamp: data.timestamp
                });
                break;

            // TTS events
            case 'tts.start':
                console.log('[VoiceWS] TTS started:', data.request_id);
                this.emit('tts.start', {
                    requestId: data.request_id,
                    timestamp: data.timestamp
                });
                break;

            case 'tts.chunk':
                // Play TTS audio chunk
                this.handleTTSChunk(data);
                this.emit('tts.chunk', {
                    requestId: data.request_id,
                    format: data.format,
                    timestamp: data.timestamp
                });
                break;

            case 'tts.end':
                console.log('[VoiceWS] TTS ended:', data.request_id);
                this.emit('tts.end', {
                    requestId: data.request_id,
                    timestamp: data.timestamp
                });
                break;

            // Control events
            case 'control.stop_playback':
                console.log('[VoiceWS] Stop playback command received');
                this.handleStopPlayback();
                this.emit('control.stop_playback', { timestamp: data.timestamp });
                break;

            case 'session.complete':
                this.emit('session.complete', { timestamp: data.timestamp });
                break;

            case 'error':
            case 'voice.error':  // 添加后端发送的 voice.error 类型支持
                this.emit('error', {
                    error: data.error,
                    message: data.message || data.error,  // fallback to error if message not present
                    timestamp: data.timestamp
                });
                break;

            default:
                console.warn('[VoiceWS] Unknown message type:', type);
        }
    }

    /**
     * Handle TTS audio chunk
     * @param {Object} data - TTS chunk data
     */
    async handleTTSChunk(data) {
        if (!this.audioPlayer) {
            console.warn('[VoiceWS] Audio player not available, skipping TTS chunk');
            return;
        }

        try {
            const { payload_b64, format } = data;

            if (!payload_b64) {
                console.warn('[VoiceWS] TTS chunk missing payload_b64');
                return;
            }

            // Default format if not provided
            const audioFormat = format || {
                codec: 'opus',
                sample_rate: 16000,
                channels: 1
            };

            await this.audioPlayer.enqueueChunk(payload_b64, audioFormat);
        } catch (error) {
            console.error('[VoiceWS] Failed to handle TTS chunk:', error);
            this.emit('error', {
                error: 'tts_playback_error',
                message: error.message
            });
        }
    }

    /**
     * Handle stop playback command (barge-in)
     */
    handleStopPlayback() {
        if (this.audioPlayer) {
            this.audioPlayer.stopPlayback();
        }
    }

    /**
     * Send audio chunk to server
     * @param {Int16Array} pcmData - PCM audio data (16-bit signed integers)
     * @param {number} seq - Sequence number (optional, auto-increments if not provided)
     */
    sendAudioChunk(pcmData, seq = null) {
        if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('[VoiceWS] Cannot send audio chunk: not connected');
            return;
        }

        // Auto-increment sequence number if not provided
        if (seq === null) {
            seq = this.sequenceNumber++;
        }

        // Convert Int16Array to base64
        const base64Audio = this.int16ArrayToBase64(pcmData);

        // Match backend expected format (voice.py AudioChunkEvent)
        const message = {
            type: 'voice.audio.chunk',
            session_id: this.sessionId,
            seq: seq,                    // 修正: sequence → seq
            payload_b64: base64Audio,    // 修正: audio → payload_b64
            format: {                    // 修正: 字符串 → 对象
                codec: 'pcm_s16le',
                sample_rate: 16000,
                channels: 1
            },
            t_ms: Date.now()             // 修正: timestamp → t_ms
        };

        this.ws.send(JSON.stringify(message));
    }

    /**
     * Send audio end signal
     */
    sendAudioEnd() {
        if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('[VoiceWS] Cannot send audio end: not connected');
            return;
        }

        const message = {
            type: 'voice.audio.end',
            session_id: this.sessionId,
            timestamp: Date.now()
        };

        console.log('[VoiceWS] Sending audio end');
        this.ws.send(JSON.stringify(message));
    }

    /**
     * Convert Int16Array to base64 string
     * @param {Int16Array} int16Array
     * @returns {string} Base64 encoded string
     */
    int16ArrayToBase64(int16Array) {
        // Convert Int16Array to Uint8Array (little-endian byte order)
        const uint8Array = new Uint8Array(int16Array.buffer);

        // Convert to base64
        let binary = '';
        for (let i = 0; i < uint8Array.length; i++) {
            binary += String.fromCharCode(uint8Array[i]);
        }

        return btoa(binary);
    }

    /**
     * Register event handler
     * @param {string} eventType - Event type
     * @param {Function} callback - Callback function
     */
    on(eventType, callback) {
        if (!this.eventHandlers[eventType]) {
            this.eventHandlers[eventType] = [];
        }
        this.eventHandlers[eventType].push(callback);
    }

    /**
     * Unregister event handler
     * @param {string} eventType - Event type
     * @param {Function} callback - Callback function
     */
    off(eventType, callback) {
        if (!this.eventHandlers[eventType]) return;

        this.eventHandlers[eventType] = this.eventHandlers[eventType].filter(
            handler => handler !== callback
        );
    }

    /**
     * Emit event to registered handlers
     * @param {string} eventType - Event type
     * @param {Object} data - Event data
     */
    emit(eventType, data) {
        if (!this.eventHandlers[eventType]) return;

        this.eventHandlers[eventType].forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error('[VoiceWS] Error in event handler:', error);
            }
        });
    }

    /**
     * Attempt to reconnect
     */
    attemptReconnect() {
        this.reconnectAttempts++;
        console.log(`[VoiceWS] Attempting reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

        setTimeout(() => {
            if (this.sessionId) {
                this.connect(this.sessionId).catch(error => {
                    console.error('[VoiceWS] Reconnection failed:', error);
                });
            }
        }, this.reconnectDelay * this.reconnectAttempts);
    }

    /**
     * Close WebSocket connection
     */
    close() {
        if (this.ws) {
            console.log('[VoiceWS] Closing connection');
            this.isConnected = false;
            this.ws.close(1000, 'Client closing connection');
            this.ws = null;
        }

        // Stop audio playback and reset player
        if (this.audioPlayer) {
            this.audioPlayer.reset();
        }
    }

    /**
     * Get connection state
     * @returns {boolean}
     */
    isOpen() {
        return this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    /**
     * Get audio player statistics
     * @returns {object}
     */
    getAudioStats() {
        if (this.audioPlayer) {
            return this.audioPlayer.getStats();
        }
        return null;
    }

    /**
     * Set audio volume (0.0 to 1.0)
     * @param {number} volume
     */
    setVolume(volume) {
        if (this.audioPlayer) {
            this.audioPlayer.setVolume(volume);
        }
    }

    /**
     * Mute audio
     */
    mute() {
        if (this.audioPlayer) {
            this.audioPlayer.mute();
        }
    }

    /**
     * Unmute audio
     */
    unmute() {
        if (this.audioPlayer) {
            this.audioPlayer.unmute();
        }
    }

    /**
     * Resume audio context (call on user interaction)
     * @returns {Promise<boolean>}
     */
    async resumeAudioContext() {
        if (this.audioPlayer) {
            return await this.audioPlayer.resumeContext();
        }
        return false;
    }
}

// Export for use in other modules
window.VoiceWebSocket = VoiceWebSocket;
