/**
 * EventStreamService - Real-time task event streaming client
 *
 * Features:
 * - Real-time event streaming via SSE (Server-Sent Events)
 * - Automatic reconnection with exponential backoff
 * - Gap detection and automatic event recovery
 * - Connection state management
 * - Event buffering and deduplication
 *
 * Usage:
 * ```javascript
 * const stream = new EventStreamService('task_123', {
 *     since_seq: 0,
 *     onEvent: (event) => {
 *         console.log('Event:', event.event_type, event.seq);
 *     },
 *     onStateChange: (state) => {
 *         console.log('State:', state);
 *     },
 *     onError: (error) => {
 *         console.error('Error:', error);
 *     }
 * });
 *
 * stream.start();
 * // ... later ...
 * stream.stop();
 * ```
 */

export class EventStreamService {
    /**
     * Connection states
     */
    static States = {
        DISCONNECTED: 'disconnected',
        CONNECTING: 'connecting',
        CONNECTED: 'connected',
        RECONNECTING: 'reconnecting',
        ERROR: 'error'
    };

    /**
     * Create event stream service
     *
     * @param {string} taskId - Task ID to stream events for
     * @param {Object} options - Configuration options
     * @param {number} [options.since_seq=0] - Start from seq (exclusive)
     * @param {number} [options.batch_size=10] - Batch size for server
     * @param {number} [options.flush_interval=0.5] - Flush interval for server
     * @param {Function} [options.onEvent] - Event callback (event) => void
     * @param {Function} [options.onStateChange] - State change callback (state, prevState) => void
     * @param {Function} [options.onError] - Error callback (error) => void
     * @param {Function} [options.onReconnect] - Reconnect callback (lastSeq) => void
     * @param {number} [options.reconnectDelay=1000] - Initial reconnect delay (ms)
     * @param {number} [options.maxReconnectDelay=30000] - Max reconnect delay (ms)
     * @param {number} [options.reconnectBackoff=2] - Reconnect backoff multiplier
     * @param {number} [options.maxReconnectAttempts=Infinity] - Max reconnect attempts
     * @param {boolean} [options.autoReconnect=true] - Auto reconnect on disconnect
     * @param {boolean} [options.gapDetection=true] - Enable gap detection
     * @param {string} [options.baseUrl=''] - Base URL for SSE endpoint
     */
    constructor(taskId, options = {}) {
        this.taskId = taskId;
        this.options = {
            since_seq: 0,
            batch_size: 10,
            flush_interval: 0.5,
            onEvent: null,
            onStateChange: null,
            onError: null,
            onReconnect: null,
            reconnectDelay: 1000,
            maxReconnectDelay: 30000,
            reconnectBackoff: 2,
            maxReconnectAttempts: Infinity,
            autoReconnect: true,
            gapDetection: true,
            baseUrl: '',
            ...options
        };

        // State
        this.state = EventStreamService.States.DISCONNECTED;
        this.eventSource = null;
        this.lastSeq = this.options.since_seq;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.currentReconnectDelay = this.options.reconnectDelay;

        // Gap detection
        this.eventBuffer = new Map(); // seq -> event
        this.expectedSeq = this.options.since_seq + 1;
        this.gapRecoveryInProgress = false;

        // Stats
        this.stats = {
            eventsReceived: 0,
            reconnects: 0,
            errors: 0,
            gapsDetected: 0,
            gapsRecovered: 0
        };
    }

    /**
     * Start event stream
     */
    start() {
        if (this.state !== EventStreamService.States.DISCONNECTED) {
            console.warn('[EventStreamService] Already started');
            return;
        }

        console.log(`[EventStreamService] Starting stream for task ${this.taskId} (since_seq=${this.lastSeq})`);
        this._connect();
    }

    /**
     * Stop event stream
     */
    stop() {
        console.log('[EventStreamService] Stopping stream');
        this._disconnect();
        this._clearReconnectTimer();
        this._setState(EventStreamService.States.DISCONNECTED);
    }

    /**
     * Get current state
     */
    getState() {
        return this.state;
    }

    /**
     * Get statistics
     */
    getStats() {
        return { ...this.stats };
    }

    /**
     * Reset statistics
     */
    resetStats() {
        this.stats = {
            eventsReceived: 0,
            reconnects: 0,
            errors: 0,
            gapsDetected: 0,
            gapsRecovered: 0
        };
    }

    // ============================================
    // Private Methods
    // ============================================

    /**
     * Connect to SSE endpoint
     */
    _connect() {
        const url = this._buildUrl();

        console.log(`[EventStreamService] Connecting to ${url}`);
        this._setState(
            this.reconnectAttempts > 0
                ? EventStreamService.States.RECONNECTING
                : EventStreamService.States.CONNECTING
        );

        try {
            this.eventSource = new EventSource(url);

            this.eventSource.onopen = () => {
                console.log('[EventStreamService] Connected');
                this._setState(EventStreamService.States.CONNECTED);
                this.reconnectAttempts = 0;
                this.currentReconnectDelay = this.options.reconnectDelay;

                // Trigger reconnect callback
                if (this.reconnectAttempts > 0 && this.options.onReconnect) {
                    this.options.onReconnect(this.lastSeq);
                }
            };

            this.eventSource.onmessage = (event) => {
                this._handleMessage(event);
            };

            this.eventSource.onerror = (error) => {
                this._handleError(error);
            };

        } catch (error) {
            console.error('[EventStreamService] Connection error:', error);
            this._handleError(error);
        }
    }

    /**
     * Disconnect from SSE endpoint
     */
    _disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    /**
     * Build SSE endpoint URL
     */
    _buildUrl() {
        const params = new URLSearchParams({
            since_seq: this.lastSeq,
            batch_size: this.options.batch_size,
            flush_interval: this.options.flush_interval
        });

        return `${this.options.baseUrl}/sse/tasks/${this.taskId}/events?${params}`;
    }

    /**
     * Handle SSE message
     */
    _handleMessage(event) {
        try {
            const data = JSON.parse(event.data);

            // Handle special message types
            if (data.type === 'reconnect') {
                console.log('[EventStreamService] Server requested reconnect:', data.reason);
                this.lastSeq = data.last_seq;
                this._reconnect();
                return;
            }

            if (data.type === 'error') {
                console.error('[EventStreamService] Server error:', data.error);
                this._handleError(new Error(data.error));
                return;
            }

            // Normal event
            this._processEvent(data);

        } catch (error) {
            console.error('[EventStreamService] Failed to parse message:', error);
            this.stats.errors++;
            if (this.options.onError) {
                this.options.onError(error);
            }
        }
    }

    /**
     * Process event (with gap detection)
     */
    _processEvent(event) {
        this.stats.eventsReceived++;
        this.lastSeq = event.seq;

        // Gap detection
        if (this.options.gapDetection) {
            if (event.seq !== this.expectedSeq) {
                // Gap detected
                console.warn(`[EventStreamService] Gap detected: expected ${this.expectedSeq}, got ${event.seq}`);
                this.stats.gapsDetected++;
                this._handleGap(event.seq);
            }
        }

        // Update expected seq
        this.expectedSeq = event.seq + 1;

        // Deliver event
        if (this.options.onEvent) {
            this.options.onEvent(event);
        }
    }

    /**
     * Handle gap detection
     */
    async _handleGap(currentSeq) {
        if (this.gapRecoveryInProgress) {
            console.log('[EventStreamService] Gap recovery already in progress');
            return;
        }

        this.gapRecoveryInProgress = true;
        console.log(`[EventStreamService] Recovering gap: ${this.expectedSeq} to ${currentSeq}`);

        try {
            // Fetch missing events via REST API
            const missingEvents = await this._fetchMissingEvents(this.expectedSeq - 1, currentSeq);

            if (missingEvents.length > 0) {
                console.log(`[EventStreamService] Recovered ${missingEvents.length} missing events`);
                this.stats.gapsRecovered++;

                // Deliver missing events in order
                for (const event of missingEvents) {
                    if (this.options.onEvent) {
                        this.options.onEvent(event);
                    }
                }
            }

        } catch (error) {
            console.error('[EventStreamService] Gap recovery failed:', error);
            this.stats.errors++;
            if (this.options.onError) {
                this.options.onError(error);
            }
        } finally {
            this.gapRecoveryInProgress = false;
        }
    }

    /**
     * Fetch missing events via REST API
     */
    async _fetchMissingEvents(sinceSeq, untilSeq) {
        const url = `${this.options.baseUrl}/api/tasks/${this.taskId}/events?since_seq=${sinceSeq}&limit=1000`;

        console.log(`[EventStreamService] Fetching missing events from ${url}`);

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Failed to fetch missing events: ${response.status}`);
        }

        const data = await response.json();

        // Filter events in range (since_seq, untilSeq)
        return data.events.filter(e => e.seq > sinceSeq && e.seq < untilSeq);
    }

    /**
     * Handle connection error
     */
    _handleError(error) {
        console.error('[EventStreamService] Error:', error);
        this.stats.errors++;

        if (this.options.onError) {
            this.options.onError(error);
        }

        // Attempt reconnection
        if (this.options.autoReconnect) {
            this._scheduleReconnect();
        } else {
            this._setState(EventStreamService.States.ERROR);
        }
    }

    /**
     * Schedule reconnection
     */
    _scheduleReconnect() {
        if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            console.error('[EventStreamService] Max reconnect attempts reached');
            this._setState(EventStreamService.States.ERROR);
            return;
        }

        this._disconnect();
        this._clearReconnectTimer();

        this.reconnectAttempts++;
        this.stats.reconnects++;

        console.log(
            `[EventStreamService] Reconnecting in ${this.currentReconnectDelay}ms ` +
            `(attempt ${this.reconnectAttempts}/${this.options.maxReconnectAttempts})`
        );

        this._setState(EventStreamService.States.RECONNECTING);

        this.reconnectTimer = setTimeout(() => {
            this._connect();
        }, this.currentReconnectDelay);

        // Exponential backoff
        this.currentReconnectDelay = Math.min(
            this.currentReconnectDelay * this.options.reconnectBackoff,
            this.options.maxReconnectDelay
        );
    }

    /**
     * Reconnect immediately
     */
    _reconnect() {
        this._disconnect();
        this._clearReconnectTimer();
        this._connect();
    }

    /**
     * Clear reconnect timer
     */
    _clearReconnectTimer() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }

    /**
     * Set state and trigger callback
     */
    _setState(newState) {
        const prevState = this.state;
        if (newState === prevState) {
            return;
        }

        console.log(`[EventStreamService] State: ${prevState} -> ${newState}`);
        this.state = newState;

        if (this.options.onStateChange) {
            this.options.onStateChange(newState, prevState);
        }
    }
}

// Export as default for ES6 module imports
export default EventStreamService;

// Also expose as global variable for non-module scripts
if (typeof window !== 'undefined') {
    window.EventStreamService = EventStreamService;
}
