// Utterance-based microphone conversion. RVC is intentionally opt-in because
// conversion adds latency and sends the selected microphone audio to the local
// Sakura RVC service for processing.
export default class RvcVoiceChanger {
    constructor(lipSync, status, getVoiceId = () => '') {
        this.lipSync = lipSync;
        this.status = status;
        this.getVoiceId = getVoiceId;
        this.active = false;
        this.pending = Promise.resolve();
        this.paused = false;
    }

    async start(deviceId = '') {
        await this.stop();
        if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone capture is unavailable in this window.');
        const stream = await navigator.mediaDevices.getUserMedia({audio: {
            ...(deviceId ? {deviceId: {exact: deviceId}} : {}),
            echoCancellation: true, noiseSuppression: true, autoGainControl: true,
        }});
        this.stream = stream;
        this.context = new (window.AudioContext || window.webkitAudioContext)({latencyHint: 'interactive'});
        if (this.context.state === 'suspended') await this.context.resume();
        this.source = this.context.createMediaStreamSource(stream);
        this.processor = this.context.createScriptProcessor(2048, 1, 1);
        this.silentOutput = this.context.createGain();
        this.silentOutput.gain.value = 0;
        this.source.connect(this.processor);
        this.processor.connect(this.silentOutput);
        this.silentOutput.connect(this.context.destination);
        this.active = true;
        this.frames = [];
        this.samples = 0;
        this.silenceSeconds = 0;
        this.speaking = false;
        this.processor.onaudioprocess = event => this._capture(event);
        this.status('Microphone voice mode on · speak, then pause briefly');
    }

    _capture(event) {
        // Do not recapture speaker playback and repeatedly convert our output.
        if (!this.active || this.paused || this.lipSync?.isPlaying) {
            this.frames=[];this.samples=0;this.silenceSeconds=0;this.speaking=false;
            return;
        }
        const input = event.inputBuffer.getChannelData(0);
        let power = 0;
        for (let i = 0; i < input.length; i++) power += input[i] * input[i];
        const rms = Math.sqrt(power / input.length);
        const frameSeconds = input.length / this.context.sampleRate;
        if (!this.speaking && rms < 0.012) return;
        this.speaking = true;
        this.frames.push(new Float32Array(input));
        this.samples += input.length;
        this.silenceSeconds = rms < 0.008 ? this.silenceSeconds + frameSeconds : 0;
        if (this.silenceSeconds >= 0.72 || this.samples >= this.context.sampleRate * 9) this._flush();
    }

    _flush() {
        if (!this.frames?.length || !this.active) return;
        const frames = this.frames;
        const sampleRate = this.context.sampleRate;
        this.frames = [];
        this.samples = 0;
        this.silenceSeconds = 0;
        this.speaking = false;
        const wav = this._encodeWav(frames, sampleRate);
        this.pending = this.pending.catch(() => {}).then(() => this._convert(wav));
    }

    _encodeWav(frames, sampleRate) {
        const count = frames.reduce((sum, frame) => sum + frame.length, 0);
        const buffer = new ArrayBuffer(44 + count * 2);
        const view = new DataView(buffer);
        const write = (offset, value) => { for (let i = 0; i < value.length; i++) view.setUint8(offset + i, value.charCodeAt(i)); };
        write(0, 'RIFF'); view.setUint32(4, 36 + count * 2, true); write(8, 'WAVE');
        write(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
        view.setUint16(22, 1, true); view.setUint32(24, sampleRate, true);
        view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true);
        view.setUint16(34, 16, true); write(36, 'data'); view.setUint32(40, count * 2, true);
        let offset = 44;
        for (const frame of frames) for (const sample of frame) {
            const value = Math.max(-1, Math.min(1, sample));
            view.setInt16(offset, value < 0 ? value * 0x8000 : value * 0x7fff, true);
            offset += 2;
        }
        return new Blob([buffer], {type: 'audio/wav'});
    }

    async _convert(blob) {
        if (!this.active) return;
        const voiceId = this.getVoiceId();
        const isRvc = voiceId.startsWith('rvc_');
        const form = new FormData();
        form.append('audio', blob, 'microphone.wav');
        const controller = new AbortController();
        this.requestController = controller;
        try {
            if (!isRvc) this.status('Recognizing speech locally · preparing selected voice…');
            const endpoint = isRvc ? '/api/voice-changer/convert' : '/api/voice-changer/speak';
            const response = await fetch(endpoint, {method: 'POST', body: form, signal: controller.signal});
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.error || `Voice processing failed (${response.status})`);
            }
            const url = URL.createObjectURL(await response.blob());
            try { if (this.active) await this.lipSync.playWithLipSync(url); }
            finally { URL.revokeObjectURL(url); }
            if (this.active) this.status(isRvc ? 'RVC voice mode on · listening' : 'Built-in voice mode on · listening');
        } catch (error) {
            if (this.active && error.name !== 'AbortError') this.status(`Microphone voice mode error · ${error.message}`);
        } finally {
            if (this.requestController === controller) this.requestController = null;
        }
    }

    async stop() {
        this.active = false;
        this.paused = false;
        this.requestController?.abort();
        this.requestController = null;
        if (this.processor) {
            this.processor.onaudioprocess = null;
            this.processor.disconnect();
            this.processor = null;
        }
        this.source?.disconnect(); this.source = null;
        this.silentOutput?.disconnect(); this.silentOutput = null;
        this.stream?.getTracks().forEach(track => track.stop()); this.stream = null;
        if (this.context) { await this.context.close().catch(() => {}); this.context = null; }
        this.frames = [];
        this.samples = 0;
        this.lipSync?.stop();
    }

    pauseForVoiceSwitch() {
        this.paused = true;
        this.requestController?.abort();
        this.requestController = null;
        this.frames = [];
        this.samples = 0;
        this.silenceSeconds = 0;
        this.speaking = false;
    }

    resumeAfterVoiceSwitch() {
        this.paused = false;
    }
}
