/**
 * VoiceAudioPlayer - Web Audio API based audio player for streaming TTS
 *
 * Features:
 * - Receives and queues base64-encoded audio chunks
 * - Supports PCM s16le and Opus codecs
 * - Implements smooth playback with automatic queue management
 * - Supports barge-in (immediate stop)
 * - Handles browser autoplay policies
 *
 * Browser compatibility: Chrome, Firefox, Safari
 */

class VoiceAudioPlayer {
    constructor() {
        // Check Web Audio API support
        if (!window.AudioContext && !window.webkitAudioContext) {
            console.error('[VoiceAudioPlayer] Web Audio API not supported');
            throw new Error('Web Audio API not supported in this browser');
        }

        // Initialize Web Audio API context
        this.audioContext = null;
        this.audioQueue = [];  // Queue of AudioBuffer objects
        this.isPlaying = false;
        this.currentSource = null;
        this.sampleRate = 16000;  // Default sample rate
        this.isMuted = false;
        this.volume = 1.0;

        // Create gain node for volume control
        this.gainNode = null;

        // Statistics
        this.stats = {
            chunksReceived: 0,
            chunksPlayed: 0,
            totalBytesReceived: 0,
            lastChunkTimestamp: null
        };

        // Buffering config
        this.bufferThreshold = 2;  // Start playing after 2 chunks buffered
        this.isBuffering = true;

        // Initialize audio context lazily (autoplay policy)
        this.initAudioContext();
    }

    /**
     * Initialize AudioContext (handles suspended state)
     */
    initAudioContext() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

            // Create gain node for volume control
            this.gainNode = this.audioContext.createGain();
            this.gainNode.connect(this.audioContext.destination);
            this.gainNode.gain.value = this.volume;

            console.log('[VoiceAudioPlayer] AudioContext initialized:', {
                state: this.audioContext.state,
                sampleRate: this.audioContext.sampleRate,
                baseLatency: this.audioContext.baseLatency
            });

            // Handle autoplay policy: resume on user interaction
            if (this.audioContext.state === 'suspended') {
                console.warn('[VoiceAudioPlayer] AudioContext suspended, waiting for user interaction');
            }
        } catch (error) {
            console.error('[VoiceAudioPlayer] Failed to initialize AudioContext:', error);
            throw error;
        }
    }

    /**
     * Resume AudioContext if suspended (autoplay policy)
     * Should be called on user interaction
     */
    async resumeContext() {
        if (this.audioContext && this.audioContext.state === 'suspended') {
            try {
                await this.audioContext.resume();
                console.log('[VoiceAudioPlayer] AudioContext resumed');
                return true;
            } catch (error) {
                console.error('[VoiceAudioPlayer] Failed to resume AudioContext:', error);
                return false;
            }
        }
        return true;
    }

    /**
     * Enqueue and play TTS audio chunk
     * @param {string} base64Audio - Base64 encoded audio data
     * @param {object} format - Audio format {codec: "opus" | "pcm_s16le", sample_rate: number}
     */
    async enqueueChunk(base64Audio, format = {}) {
        try {
            // Resume context if needed
            await this.resumeContext();

            // Default format
            const audioFormat = {
                codec: format.codec || 'opus',
                sample_rate: format.sample_rate || 16000,
                channels: format.channels || 1
            };

            console.log('[VoiceAudioPlayer] Enqueuing chunk:', {
                codec: audioFormat.codec,
                sample_rate: audioFormat.sample_rate,
                size: base64Audio.length,
                queueLength: this.audioQueue.length
            });

            // 1. Decode base64 to ArrayBuffer
            const arrayBuffer = this.base64ToArrayBuffer(base64Audio);
            this.stats.totalBytesReceived += arrayBuffer.byteLength;
            this.stats.chunksReceived++;
            this.stats.lastChunkTimestamp = Date.now();

            // 2. Decode audio based on codec
            let audioBuffer;
            if (audioFormat.codec === 'opus') {
                audioBuffer = await this.decodeOpus(arrayBuffer);
            } else if (audioFormat.codec === 'pcm_s16le') {
                audioBuffer = this.decodePCM(arrayBuffer, audioFormat.sample_rate, audioFormat.channels);
            } else {
                throw new Error(`Unsupported codec: ${audioFormat.codec}`);
            }

            // 3. Add to queue
            this.audioQueue.push(audioBuffer);

            // 4. Start playing if buffering threshold met
            if (this.isBuffering && this.audioQueue.length >= this.bufferThreshold) {
                console.log('[VoiceAudioPlayer] Buffer threshold met, starting playback');
                this.isBuffering = false;
                this.playNext();
            } else if (!this.isPlaying && !this.isBuffering) {
                // Resume playback if stopped unexpectedly
                this.playNext();
            }

        } catch (error) {
            console.error('[VoiceAudioPlayer] Failed to enqueue chunk:', error);
            throw error;
        }
    }

    /**
     * Decode base64 string to ArrayBuffer
     * @param {string} base64 - Base64 encoded string
     * @returns {ArrayBuffer}
     */
    base64ToArrayBuffer(base64) {
        try {
            // Decode base64 to binary string
            const binaryString = atob(base64);
            const length = binaryString.length;

            // Convert to Uint8Array
            const arrayBuffer = new ArrayBuffer(length);
            const uint8Array = new Uint8Array(arrayBuffer);

            for (let i = 0; i < length; i++) {
                uint8Array[i] = binaryString.charCodeAt(i);
            }

            return arrayBuffer;
        } catch (error) {
            console.error('[VoiceAudioPlayer] Failed to decode base64:', error);
            throw new Error('Invalid base64 audio data');
        }
    }

    /**
     * Decode Opus audio using Web Audio API
     * @param {ArrayBuffer} arrayBuffer - Opus encoded audio
     * @returns {Promise<AudioBuffer>}
     */
    async decodeOpus(arrayBuffer) {
        try {
            const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            console.log('[VoiceAudioPlayer] Decoded Opus:', {
                duration: audioBuffer.duration,
                sampleRate: audioBuffer.sampleRate,
                channels: audioBuffer.numberOfChannels
            });
            return audioBuffer;
        } catch (error) {
            console.error('[VoiceAudioPlayer] Failed to decode Opus:', error);
            throw new Error('Failed to decode Opus audio');
        }
    }

    /**
     * Decode PCM s16le (signed 16-bit little-endian) audio
     * @param {ArrayBuffer} arrayBuffer - PCM encoded audio
     * @param {number} sampleRate - Sample rate (e.g., 16000)
     * @param {number} channels - Number of channels (1 = mono, 2 = stereo)
     * @returns {AudioBuffer}
     */
    decodePCM(arrayBuffer, sampleRate = 16000, channels = 1) {
        try {
            // Convert Int16 (little-endian) to Float32 (-1.0 to 1.0)
            const int16Array = new Int16Array(arrayBuffer);
            const samplesPerChannel = Math.floor(int16Array.length / channels);

            // Create AudioBuffer
            const audioBuffer = this.audioContext.createBuffer(
                channels,
                samplesPerChannel,
                sampleRate
            );

            // Convert and copy to each channel
            for (let channel = 0; channel < channels; channel++) {
                const channelData = audioBuffer.getChannelData(channel);

                for (let i = 0; i < samplesPerChannel; i++) {
                    // Convert Int16 (-32768 to 32767) to Float32 (-1.0 to 1.0)
                    const sampleIndex = i * channels + channel;
                    channelData[i] = int16Array[sampleIndex] / 32768.0;
                }
            }

            console.log('[VoiceAudioPlayer] Decoded PCM:', {
                duration: audioBuffer.duration,
                sampleRate: audioBuffer.sampleRate,
                channels: audioBuffer.numberOfChannels,
                samples: samplesPerChannel
            });

            return audioBuffer;
        } catch (error) {
            console.error('[VoiceAudioPlayer] Failed to decode PCM:', error);
            throw new Error('Failed to decode PCM audio');
        }
    }

    /**
     * Play next audio chunk from queue
     */
    playNext() {
        if (this.audioQueue.length === 0) {
            console.log('[VoiceAudioPlayer] Queue empty, stopping playback');
            this.isPlaying = false;
            return;
        }

        if (this.isBuffering) {
            console.log('[VoiceAudioPlayer] Still buffering, waiting...');
            return;
        }

        this.isPlaying = true;
        const audioBuffer = this.audioQueue.shift();
        this.stats.chunksPlayed++;

        console.log('[VoiceAudioPlayer] Playing chunk:', {
            duration: audioBuffer.duration,
            queueLength: this.audioQueue.length,
            chunksPlayed: this.stats.chunksPlayed
        });

        // Create buffer source
        const source = this.audioContext.createBufferSource();
        source.buffer = audioBuffer;

        // Connect to gain node (for volume control)
        source.connect(this.gainNode);

        // Play next chunk when this one ends
        source.onended = () => {
            console.log('[VoiceAudioPlayer] Chunk finished');
            this.currentSource = null;

            // Small delay to prevent clicks between chunks
            setTimeout(() => {
                this.playNext();
            }, 10);
        };

        this.currentSource = source;

        try {
            source.start(0);
        } catch (error) {
            console.error('[VoiceAudioPlayer] Failed to start playback:', error);
            this.currentSource = null;
            this.playNext();  // Try next chunk
        }
    }

    /**
     * Stop playback immediately (barge-in)
     * Clears queue and stops current playback
     */
    stopPlayback() {
        console.log('[VoiceAudioPlayer] Stopping playback (barge-in)', {
            queueLength: this.audioQueue.length,
            isPlaying: this.isPlaying
        });

        // Stop current audio source
        if (this.currentSource) {
            try {
                this.currentSource.stop();
                this.currentSource.disconnect();
            } catch (error) {
                console.warn('[VoiceAudioPlayer] Error stopping source:', error);
            }
            this.currentSource = null;
        }

        // Clear queue
        this.audioQueue = [];
        this.isPlaying = false;
        this.isBuffering = true;  // Reset buffering state

        console.log('[VoiceAudioPlayer] Playback stopped');
    }

    /**
     * Set volume (0.0 to 1.0)
     * @param {number} volume - Volume level
     */
    setVolume(volume) {
        this.volume = Math.max(0.0, Math.min(1.0, volume));
        if (this.gainNode) {
            this.gainNode.gain.value = this.volume;
        }
        console.log('[VoiceAudioPlayer] Volume set to:', this.volume);
    }

    /**
     * Mute audio
     */
    mute() {
        this.isMuted = true;
        if (this.gainNode) {
            this.gainNode.gain.value = 0;
        }
        console.log('[VoiceAudioPlayer] Muted');
    }

    /**
     * Unmute audio
     */
    unmute() {
        this.isMuted = false;
        if (this.gainNode) {
            this.gainNode.gain.value = this.volume;
        }
        console.log('[VoiceAudioPlayer] Unmuted');
    }

    /**
     * Get current playback statistics
     * @returns {object}
     */
    getStats() {
        return {
            ...this.stats,
            queueLength: this.audioQueue.length,
            isPlaying: this.isPlaying,
            isBuffering: this.isBuffering,
            audioContextState: this.audioContext ? this.audioContext.state : 'not initialized'
        };
    }

    /**
     * Reset player state
     */
    reset() {
        console.log('[VoiceAudioPlayer] Resetting player');
        this.stopPlayback();
        this.stats = {
            chunksReceived: 0,
            chunksPlayed: 0,
            totalBytesReceived: 0,
            lastChunkTimestamp: null
        };
    }

    /**
     * Clean up resources
     */
    destroy() {
        console.log('[VoiceAudioPlayer] Destroying player');
        this.stopPlayback();

        if (this.gainNode) {
            this.gainNode.disconnect();
            this.gainNode = null;
        }

        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
    }
}

// Export for use in other modules
window.VoiceAudioPlayer = VoiceAudioPlayer;
