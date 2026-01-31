/**
 * MicCapture - Audio capture and processing module
 *
 * Captures audio from microphone, downsamples to 16kHz, and converts to PCM s16le format.
 * Prioritizes AudioWorklet with fallback to ScriptProcessorNode for browser compatibility.
 */

class MicCapture {
    constructor(onAudioChunk) {
        this.onAudioChunk = onAudioChunk;
        this.audioContext = null;
        this.stream = null;
        this.source = null;
        this.processor = null;
        this.workletNode = null;
        this.isRecording = false;
        this.useWorklet = false; // Will be determined at runtime
    }

    /**
     * Start audio capture
     * @returns {Promise<void>}
     */
    async start() {
        if (this.isRecording) {
            console.warn('[MicCapture] Already recording');
            return;
        }

        try {
            // Request microphone permission and get stream
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    sampleRate: 48000, // Request high quality, will downsample
                }
            });

            console.log('[MicCapture] Microphone stream acquired');

            // Create AudioContext with 16kHz sample rate (required for Whisper)
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000
            });

            this.source = this.audioContext.createMediaStreamSource(this.stream);

            // Use ScriptProcessorNode for MVP (AudioWorklet can be enabled in future)
            // Note: ScriptProcessorNode is deprecated but has better compatibility
            this.setupScriptProcessor();

            this.isRecording = true;
            console.log('[MicCapture] Recording started');

        } catch (error) {
            console.error('[MicCapture] Failed to start recording:', error);
            this.cleanup();
            throw error;
        }
    }

    /**
     * Setup AudioWorklet processor (modern approach)
     */
    async setupAudioWorklet() {
        try {
            await this.audioContext.audioWorklet.addModule('/static/js/voice/audio-processor.js');

            this.workletNode = new AudioWorkletNode(this.audioContext, 'audio-processor');

            this.workletNode.port.onmessage = (event) => {
                if (event.data.type === 'audio') {
                    const pcmData = event.data.buffer;
                    this.onAudioChunk(new Int16Array(pcmData));
                }
            };

            this.source.connect(this.workletNode);
            this.workletNode.connect(this.audioContext.destination);

            this.useWorklet = true;
            console.log('[MicCapture] Using AudioWorklet');

        } catch (error) {
            console.warn('[MicCapture] AudioWorklet not available, falling back to ScriptProcessor:', error);
            this.setupScriptProcessor();
        }
    }

    /**
     * Setup ScriptProcessorNode (legacy approach, but more compatible)
     */
    setupScriptProcessor() {
        // Use 2048 buffer size (about 128ms at 16kHz)
        const bufferSize = 2048;
        this.processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

        this.processor.onaudioprocess = (e) => {
            if (!this.isRecording) return;

            const float32Data = e.inputBuffer.getChannelData(0);
            const int16Data = this.floatTo16BitPCM(float32Data);

            // Send audio chunk to callback
            this.onAudioChunk(int16Data);
        };

        // Connect the nodes
        this.source.connect(this.processor);
        this.processor.connect(this.audioContext.destination);

        console.log('[MicCapture] Using ScriptProcessorNode (buffer size: ' + bufferSize + ')');
    }

    /**
     * Convert Float32Array audio data to 16-bit PCM (Int16Array)
     * @param {Float32Array} float32Array - Audio data in float32 format (-1.0 to 1.0)
     * @returns {Int16Array} Audio data in PCM s16le format
     */
    floatTo16BitPCM(float32Array) {
        const int16 = new Int16Array(float32Array.length);

        for (let i = 0; i < float32Array.length; i++) {
            // Clamp to -1.0 to 1.0 range
            const s = Math.max(-1, Math.min(1, float32Array[i]));

            // Convert to 16-bit integer
            // Negative values: multiply by 0x8000 (32768)
            // Positive values: multiply by 0x7FFF (32767)
            int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        return int16;
    }

    /**
     * Stop audio capture and cleanup resources
     */
    stop() {
        if (!this.isRecording) {
            console.warn('[MicCapture] Not recording');
            return;
        }

        console.log('[MicCapture] Stopping recording');
        this.isRecording = false;
        this.cleanup();
    }

    /**
     * Cleanup audio resources
     */
    cleanup() {
        // Stop all tracks
        if (this.stream) {
            this.stream.getTracks().forEach(track => {
                track.stop();
                console.log('[MicCapture] Stopped track:', track.kind);
            });
            this.stream = null;
        }

        // Disconnect audio nodes
        if (this.processor) {
            this.processor.disconnect();
            this.processor = null;
        }

        if (this.workletNode) {
            this.workletNode.disconnect();
            this.workletNode = null;
        }

        if (this.source) {
            this.source.disconnect();
            this.source = null;
        }

        // Close audio context
        if (this.audioContext && this.audioContext.state !== 'closed') {
            this.audioContext.close();
            this.audioContext = null;
        }

        console.log('[MicCapture] Cleanup completed');
    }

    /**
     * Get current recording state
     * @returns {boolean}
     */
    getIsRecording() {
        return this.isRecording;
    }

    /**
     * Get audio context sample rate
     * @returns {number|null}
     */
    getSampleRate() {
        return this.audioContext ? this.audioContext.sampleRate : null;
    }
}

// Export for use in other modules
window.MicCapture = MicCapture;
