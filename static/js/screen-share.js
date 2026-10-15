export default class ScreenShare {
    constructor(onChange = () => {}) {
        this.onChange = onChange;
        this.stream = null;
        this.video = null;
        this.generation = 0;
        this.starting = false;
        this.frames = [];
        this.observationSamples = [];
        this.frameTimer = null;
        this.frameBusy = false;
        this.canvas = document.createElement('canvas');
    }

    get enabled() { return !!this.desktopEnabled || !!this.stream?.getVideoTracks().some(track => track.readyState === 'live'); }

    async toggle() {
        if (this.enabled || this.starting) { this.stop(); return; }
        if (window.pywebview?.api?.set_screen_access) {
            const generation = ++this.generation;
            this.starting = true;
            this.onChange(false, true);
            try {
                await window.pywebview.api.set_screen_access(true);
                const image = await window.pywebview.api.screen_snapshot();
                if (generation !== this.generation) return;
                if (typeof image !== 'string' || !image.startsWith('/9j/')) {
                    throw new Error('Desktop screen capture returned no image. Turn Screen on again.');
                }
                this.desktopEnabled = true;
                this._remember(image);
                this.starting = false;
                this.onChange(true, false);
                this._startCapture(generation);
            } catch (error) {
                if (generation === this.generation) this.stop();
                throw error;
            }
            return;
        }
        if (!navigator.mediaDevices?.getDisplayMedia) {
            throw new Error('Screen sharing is unavailable here. Open Sakura in Chrome or Edge on localhost.');
        }
        const generation = ++this.generation;
        this.starting = true;
        this.onChange(false, true);
        let stream;
        try {
            // This call stays directly in the click handler for browser permission.
            stream = await navigator.mediaDevices.getDisplayMedia({
                video: { frameRate: { ideal: 30, max: 30 } }, audio: false,
            });
            if (generation !== this.generation) { stream.getTracks().forEach(track => track.stop()); return; }
            this.stream = stream;
            this.video = document.createElement('video');
            this.video.muted = true;
            this.video.playsInline = true;
            this.video.srcObject = stream;
            stream.getVideoTracks().forEach(track => track.addEventListener('ended', () => {
                if (this.stream === stream) this.stop();
            }));
            await this.video.play();
            if (generation !== this.generation) return;
            this.starting = false;
            this.onChange(true, false);
            this._startCapture(generation);
        } catch (err) {
            stream?.getTracks().forEach(track => track.stop());
            if (generation !== this.generation) return;
            this.stop();
            if (err.name !== 'NotAllowedError' && err.name !== 'AbortError') throw err;
        }
    }

    _remember(image) {
        const now=Date.now();
        this.frames.push({image, time: now});
        this.frames = this.frames.filter(frame => Date.now() - frame.time < 2500).slice(-8);
        if(!this.observationSamples.length||now-this.observationSamples.at(-1).time>=6000){
            this.observationSamples.push({image,time:now});
        }
        this.observationSamples=this.observationSamples.filter(frame=>now-frame.time<22000).slice(-4);
    }

    observationFrames(){
        if(!this.enabled)return [];
        const frames=this.observationSamples.filter(frame=>Date.now()-frame.time<22000);
        return frames.length>3?[frames[0].image,frames[Math.floor(frames.length/2)].image,frames.at(-1).image]:frames.map(f=>f.image);
    }

    _startCapture(generation) {
        clearInterval(this.frameTimer);
        this.frameTimer = setInterval(async () => {
            if (!this.enabled || generation !== this.generation || this.frameBusy) return;
            this.frameBusy = true;
            try {
                const image = await this._captureFrame();
                if (image && generation === this.generation && this.enabled) this._remember(image);
            } catch (_) {
                if (generation === this.generation) this.stop();
            } finally { this.frameBusy = false; }
        }, 333);
    }

    recentFrames() {
        if (!this.enabled) return [];
        const recent = this.frames.filter(frame => Date.now() - frame.time < 2500);
        if (recent.length <= 3) return recent.map(frame => frame.image);
        return [recent[0].image, recent[Math.floor(recent.length / 2)].image, recent.at(-1).image];
    }

    async snapshot() {
        if (!this.enabled) return null;
        const generation = this.generation;
        const newest = this.frames.at(-1);
        if (newest && Date.now() - newest.time < 1500) return newest.image;
        const image = await this._captureFrame();
        if (generation !== this.generation || !this.enabled) return null;
        if (image) this._remember(image);
        return image;
    }

    async _captureFrame() {
        if (!this.enabled) return null;
        if (this.desktopEnabled) {
            const image = await window.pywebview.api.screen_snapshot();
            if (typeof image !== 'string' || !image.startsWith('/9j/')) {
                throw new Error('No screen image was captured. Turn Screen off and on again.');
            }
            return image;
        }
        if (!this.video?.videoWidth || this.video.readyState < 2) {
            throw new Error('Screen sharing is starting. Wait a moment, then send your message.');
        }
        const scale = Math.min(1, 1600 / this.video.videoWidth, 1200 / this.video.videoHeight);
        this.canvas.width = Math.max(1, Math.round(this.video.videoWidth * scale));
        this.canvas.height = Math.max(1, Math.round(this.video.videoHeight * scale));
        const context = this.canvas.getContext('2d');
        context.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        const image = this.canvas.toDataURL('image/jpeg', 0.82).split(',')[1];
        // Clear the local frame immediately after constructing the request data.
        context.clearRect(0, 0, this.canvas.width, this.canvas.height);
        return image;
    }

    stop() {
        ++this.generation;
        clearInterval(this.frameTimer);
        this.frameTimer = null;
        this.frames = [];
        this.observationSamples = [];
        this.desktopEnabled = false;
        window.pywebview?.api?.set_screen_access?.(false);
        this.stream?.getTracks().forEach(track => track.stop());
        this.stream = null;
        this.video?.pause();
        if (this.video) this.video.srcObject = null;
        this.video = null;
        this.starting = false;
        this.canvas.width = this.canvas.height = 1;
        this.onChange(false, false);
    }
}
