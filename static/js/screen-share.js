export default class ScreenShare {
    constructor(onChange = () => {}) {
        this.onChange = onChange;
        this.stream = null;
        this.video = null;
        this.generation = 0;
        this.starting = false;
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
                this.starting = false;
                this.onChange(true, false);
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
                video: { frameRate: { ideal: 1, max: 5 } }, audio: false,
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
        } catch (err) {
            stream?.getTracks().forEach(track => track.stop());
            if (generation !== this.generation) return;
            this.stop();
            if (err.name !== 'NotAllowedError' && err.name !== 'AbortError') throw err;
        }
    }

    async snapshot() {
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
