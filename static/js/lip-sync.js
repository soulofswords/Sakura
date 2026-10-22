export default class LipSync {
    constructor(modelViewer) {
        this.modelViewer = modelViewer;
        this.audioContext = null;
        this.source = null;
        this.analyser = null;
        this.isPlaying = false;
        this.rafId = null;
        this.outputDeviceId = '';
        this.appliedOutputDeviceId = '';
        this.playGeneration = 0;
        this.fetchController = null;
        this.resolvePlayback = null;

        // Vowel target states and smoothed values
        this.current = { A: 0, I: 0, U: 0, E: 0, O: 0 };
        this.targets = { A: 0, I: 0, U: 0, E: 0, O: 0 };

        // Time constants in seconds, independent of rendering frame rate.
        this.attackTime = 0.025;
        this.releaseTime = 0.045;
        this.envelope = null;
        this.playbackStartTime = 0;
    }

    async _ensureAudioContext() {
        if (!this.audioContext) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioContextClass({ latencyHint: 'interactive' });
        }
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }
        if(this.outputRoutePending)await this.outputRoutePending.catch(()=>{});
        if (this.outputDeviceId !== this.appliedOutputDeviceId && typeof this.audioContext.setSinkId === 'function') {
            try {
                const deviceId=this.outputDeviceId;
                this.outputRoutePending=this.audioContext.setSinkId(deviceId);
                await this.outputRoutePending;
                this.appliedOutputDeviceId=deviceId;
            } catch (err) {
                console.warn('Failed to set sink ID:', err);
            } finally {
                this.outputRoutePending=null;
            }
        }
    }

    async setAudioOutput(deviceId) {
        this.outputDeviceId = deviceId || '';
        await this._ensureAudioContext();
    }

    async playWithLipSync(audioUrl, onPlaybackStarted = null, {volume = 1} = {}) {
        this.stop();
        const generation = this.playGeneration;
        const controller = new AbortController();
        this.fetchController = controller;
        try {
            await this._ensureAudioContext();
            if (generation !== this.playGeneration) return;
            const resp = await fetch(audioUrl, { signal: controller.signal });
            if (!resp.ok) throw new Error(`Audio request failed (${resp.status})`);
            const arrayBuf = await resp.arrayBuffer();
            if (generation !== this.playGeneration) return;
            const audioBuffer = await this.audioContext.decodeAudioData(arrayBuf);
            if (generation !== this.playGeneration) return;
            this.fetchController = null;
            this._prepareEnvelope(audioBuffer);

            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            this.source = source;
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 1024;
            this.analyser.smoothingTimeConstant = 0;
            source.connect(this.analyser);
            this.outputGain = this.audioContext.createGain();
            this.setPlaybackVolume(volume);
            this.analyser.connect(this.outputGain);
            this.outputGain.connect(this.audioContext.destination);

            const finished = new Promise(resolve => { this.resolvePlayback = resolve; });
            source.onended = () => {
                if (generation === this.playGeneration && this.source === source) this.stop();
            };
            await this.onAudioActive?.(true);
            if(generation!==this.playGeneration)return;
            this.isPlaying = true;
            this.modelViewer.audioPlaybackActive = true;
            this.modelViewer.setActivity?.('talking');
            this.playbackStartTime = this.audioContext.currentTime;
            source.start(this.playbackStartTime);
            onPlaybackStarted?.();
            this._startAnalysisLoop(generation);
            return await finished;
        } catch (err) {
            if (generation !== this.playGeneration) return;
            this.stop();
            console.error('Lip sync audio error:', err);
            throw err;
        }
    }

    stop() {
        const wasPlaying=this.isPlaying;
        ++this.playGeneration;
        this.isPlaying = false;
        if(wasPlaying)this.onAudioActive?.(false);
        this.modelViewer.audioPlaybackActive = false;
        this.modelViewer.setActivity?.('idle');
        this.modelViewer.setSpeechLevel?.(0);
        this.fetchController?.abort();
        this.fetchController = null;
        if (this.rafId !== null) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }
        if (this.source) {
            this.source.onended = null;
            try { this.source.stop(); } catch (_) {}
            this.source.disconnect();
            this.source = null;
        }
        this.analyser?.disconnect();
        this.analyser = null;
        this.outputGain?.disconnect();
        this.outputGain = null;
        this.envelope = null;
        const resolve = this.resolvePlayback;
        this.resolvePlayback = null;
        this.targets = { A: 0, I: 0, U: 0, E: 0, O: 0 };
        this.current = { A: 0, I: 0, U: 0, E: 0, O: 0 };
        this.modelViewer.resetMouth();
        this._updateHUD();
        resolve?.();
    }

    _smoothWeights(delta) {
        for (const vowel of ['A', 'I', 'U', 'E', 'O']) {
            const time = this.modelViewer.mouthOptions?.smoothing|| (this.targets[vowel] > this.current[vowel] ? this.attackTime : this.releaseTime);
            const alpha = 1 - Math.exp(-delta / time);
            this.current[vowel] += (this.targets[vowel] - this.current[vowel]) * alpha;
        }
    }

    setPlaybackVolume(value) {
        if (this.outputGain) this.outputGain.gain.value = Math.max(0, Math.min(2, Number(value) || 0));
    }

    _prepareEnvelope(buffer) {
        this.envelope = null;
        if (!buffer.getChannelData || !buffer.sampleRate) return;
        const channels = Array.from({ length: buffer.numberOfChannels || 1 }, (_, i) => buffer.getChannelData(i));
        const samples = channels[0];
        const hop = Math.max(1, Math.round(buffer.sampleRate * 0.01));
        const values = [];
        for (let start = 0; start < samples.length; start += hop) {
            const end = Math.min(samples.length, start + hop);
            let energy = 0;
            for (let i = start; i < end; i++) {
                for (const channel of channels) energy += channel[i] ** 2;
            }
            values.push(Math.sqrt(energy / ((end - start) * channels.length)));
        }
        const voiced = values.filter(value => value > 0.002).sort((a, b) => a - b);
        const reference = voiced[Math.floor(voiced.length * 0.9)] || 0.05;
        this.envelope = { values, step: hop / buffer.sampleRate,
            reference: Math.max(0.008, reference), gate: Math.max(0.001, reference * 0.08) };
    }

    _openingAt(time) {
        if (!this.envelope || time < 0) return 0;
        const { values, step, reference, gate } = this.envelope;
        const position = time / step;
        const index = Math.floor(position);
        if (index >= values.length) return 0;
        const mix = position - index;
        const rms = values[index] * (1 - mix) + (values[index + 1] || 0) * mix;
        return Math.min(0.92, Math.pow(Math.max(0, (rms - gate) / reference), 0.72) * 0.88);
    }

    _startAnalysisLoop(generation) {
        const analyser = this.analyser;
        // Time-domain analysis needs the full FFT window, including quiet samples.
        const timeData = new Float32Array(analyser.fftSize);
        let previousTime = this.audioContext.currentTime;
        const loop = () => {
            if (!this.isPlaying || generation !== this.playGeneration) return;
            const now = this.audioContext.currentTime;
            const delta = Math.max(0, now - previousTime);
            previousTime = now;
            analyser.getFloatTimeDomainData(timeData);
            let sumSquare = 0;
            for (const sample of timeData) sumSquare += sample * sample;
            const rms = Math.sqrt(sumSquare / timeData.length);
            // Audio energy reliably tells us when to open the mouth, but it
            // cannot identify vowels. Mixing guessed vowel morphs distorts lips.
            // Follow the audible playback clock rather than the analyser's
            // latest render block. Calibrate each clip so quiet RVC speech
            // gets the same natural movement as louder built-in voices.
            const outputTime = this.audioContext.getOutputTimestamp?.().contextTime;
            const audibleTime = Number.isFinite(outputTime) && outputTime > 0 && outputTime <= now && now - outputTime < 0.5
                ? outputTime : now - (this.audioContext.outputLatency || this.audioContext.baseLatency || 0);
            const opening = this.envelope
                ? this._openingAt(audibleTime - this.playbackStartTime + 0.02)
                : Math.min(0.92, Math.pow(Math.max(0, (rms - 0.003) * 8), 0.72));
            const available = this.modelViewer.resolvedVowels || {};
            const mouth = ['A', 'O', 'E', 'U', 'I'].find(v => available[v]);
            this.targets = { A: 0, I: 0, U: 0, E: 0, O: 0 };
            const options=this.modelViewer.mouthOptions;
            if (mouth) this.targets[mouth] = options?Math.min(1,Math.max(0,opening-options.cutoff)*options.gain):opening;
            this._smoothWeights(delta);
            this.modelViewer.setSpeechLevel?.(Object.values(this.current).reduce((sum, value) => sum + value, 0) / 0.9);
            this.modelViewer.setVowelWeights(this.current);
            this._updateHUD();
            this.rafId = requestAnimationFrame(loop);
        };
        this.rafId = requestAnimationFrame(loop);
    }

    _updateHUD() {
        for (const v of ['A', 'I', 'U', 'E', 'O']) {
            const bar = document.getElementById(`bar-${v.toLowerCase()}`);
            if (bar) {
                const percent = Math.round(this.current[v] * 100);
                bar.style.width = `${percent}%`;
            }
        }
    }
}
