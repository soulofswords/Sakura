export default class ContinuousMic {
    constructor(onUtterance, onStatus) {
        this.onUtterance = onUtterance;
        this.onStatus = onStatus;
        this.generation = 0;
        this.enabled = false;
    }

    async start(deviceId = '') {
        this.stop();
        const generation = this.generation;
        const stream = await navigator.mediaDevices.getUserMedia({ audio: {
            ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
            echoCancellation: true, noiseSuppression: true, autoGainControl: true,
        } });
        if (generation !== this.generation) { stream.getTracks().forEach(t => t.stop()); return; }
        this.stream = stream;
        this.context = new (window.AudioContext || window.webkitAudioContext)();
        await this.context.resume();
        if (generation !== this.generation) return;
        this.input = this.context.createMediaStreamSource(stream);
        this.analyser = this.context.createAnalyser();
        this.analyser.fftSize = 1024;
        this.input.connect(this.analyser);
        this.enabled = true;
        this._record(generation);
    }

    _record(generation) {
        if (!this.enabled || generation !== this.generation) return;
        const recorder = new MediaRecorder(this.stream);
        this.recorder = recorder;
        const chunks = [];
        let speechMs = 0, lastVoice = 0;
        const started = performance.now();
        const samples = new Float32Array(this.analyser.fftSize);
        this.onStatus('Listening…');
        recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
        recorder.onstop = async () => {
            clearInterval(this.timer);
            if (!this.enabled || generation !== this.generation) return;
            if (speechMs >= 200 && chunks.length) {
                this.onStatus('Preparing reply…');
                // No recorder runs while recognizing/generating/playing a reply.
                try { await this.onUtterance(new Blob(chunks, { type: recorder.mimeType })); }
                catch (err) { this.onStatus(err.message); }
            }
            this._record(generation);
        };
        recorder.start(200);
        this.timer = setInterval(() => {
            if (generation !== this.generation || recorder.state !== 'recording') return;
            this.analyser.getFloatTimeDomainData(samples);
            const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
            const now = performance.now();
            if (rms > 0.012) {
                speechMs += 50;
                lastVoice = now;
                this.onStatus('Hearing you…');
            }
            // Wait for a full pause, not the gaps between individual words.
            if ((speechMs >= 200 && now - lastVoice > 1100) ||
                (!speechMs && now - started > 5000)) recorder.stop();
        }, 50);
    }

    stop() {
        ++this.generation;
        this.enabled = false;
        clearInterval(this.timer);
        if (this.recorder?.state === 'recording') this.recorder.stop();
        this.input?.disconnect();
        this.stream?.getTracks().forEach(t => t.stop());
        this.context?.close();
        this.stream = null;
        this.onStatus('Microphone off');
    }
}
