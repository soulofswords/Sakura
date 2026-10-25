const nextFrame = fn => typeof requestAnimationFrame === 'function' ? requestAnimationFrame(fn) : setTimeout(fn, 16);
const cancelFrame = id => typeof cancelAnimationFrame === 'function' ? cancelAnimationFrame(id) : clearTimeout(id);

export default class EyeTracking {
    constructor(viewer, onChange) {
        this.viewer = viewer;
        this.onChange = onChange;
        this.enabled = false;
        this.generation = 0;
        this.failures = 0;
        this.bridgeFailures = 0;
    }

    async _cursor() {
        const api = globalThis.pywebview?.api;
        if (this.bridgeFailures < 3 && typeof api?.cursor_position === 'function') {
            try {
                const point = await api.cursor_position();
                if (Number.isFinite(point?.x) && Number.isFinite(point?.y)) {
                    this.bridgeFailures = 0;
                    return point;
                }
            } catch (_) { /* fall through to the HTTP route */ }
            ++this.bridgeFailures;
        }
        try {
            const response = await fetch('/api/cursor', { cache: 'no-store' });
            if (!response.ok) return null;
            const point = await response.json();
            return Number.isFinite(point?.x) && Number.isFinite(point?.y) ? point : null;
        } catch (_) {
            return null;
        }
    }

    start() {
        if (this.enabled) return;
        this.enabled = true;
        this.viewer.eyeTrackingEnabled = true;
        ++this.generation;
        this.failures = 0;
        this.onChange(true);
        this._listenPointer();
        this._stream(this.generation);
        this._poll(this.generation);
    }

    _listenPointer() {
        if (typeof window === 'undefined') return;
        this.pointerListener = event => {
            // Browser screen coordinates and dimensions share CSS pixels, so
            // DPI scaling is preserved. Multiple monitors use native samples
            // instead, which know the complete virtual desktop bounds.
            const screen = window.screen;
            if (!this.enabled || screen?.isExtended || !(screen?.width > 0 && screen?.height > 0) ||
                !Number.isFinite(event.screenX) || !Number.isFinite(event.screenY) || event.pointerType === 'touch') return;
            this.lastPointerAt = Date.now();
            this.viewer?.setEyeTrackingTarget(event.screenX / screen.width * 2 - 1,
                event.screenY / screen.height * 2 - 1);
        };
        this.leaveListener = event => { if (event.type === 'blur' || !event.relatedTarget) this.lastPointerAt = 0; };
        window.addEventListener('pointermove', this.pointerListener, {passive:true});
        window.addEventListener('blur', this.leaveListener);
        window.addEventListener('pointerout', this.leaveListener);
    }

    _stream(generation) {
        if (typeof WebSocket !== 'function' || typeof location === 'undefined') return;
        const url = new URL('/api/cursor/stream', location.href);
        url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        try {
            const socket = this.socket = new WebSocket(url);
            socket.onmessage = event => {
                if (!this.enabled || generation !== this.generation) return;
                try {
                    const point = JSON.parse(event.data);
                    if (!Number.isFinite(point?.x) || !Number.isFinite(point?.y)) return;
                    this.lastStreamAt = Date.now();
                    this.failures = 0;
                    if (this.lastPointerAt && Date.now() - this.lastPointerAt < 25) return;
                    this.viewer?.setEyeTrackingTarget(point.x, point.y);
                } catch (_) { /* Ignore malformed samples; polling remains available. */ }
            };
            socket.onerror = () => socket.close();
            socket.onclose = () => {
                if (this.socket === socket) this.socket = null;
                if (this.enabled && generation === this.generation)
                    this.retryTimer = setTimeout(() => this._stream(generation), 1000);
            };
        } catch (_) { /* Older runtimes can keep using local polling. */ }
    }

    _poll(generation) {
        // Keep the frame chain running while a cursor read is in flight. Awaiting the
        // bridge first turns a slow reply into a dropped gaze sample and visible stutter.
        let inFlight = false;
        const step = () => {
            if (!this.enabled || generation !== this.generation) return;
            if (!inFlight && (!this.lastStreamAt || Date.now() - this.lastStreamAt > 250)) {
                inFlight = true;
                const sampledAt = Date.now();
                this._cursor().then(point => {
                    inFlight = false;
                    if (!this.enabled || generation !== this.generation) return;
                    // An older fallback reply must never overwrite a newer stream sample.
                    if (this.lastStreamAt >= sampledAt || this.lastPointerAt >= sampledAt) return;
                    if (point) {
                        this.failures = 0;
                        this.viewer?.setEyeTrackingTarget(point.x, point.y);
                    } else if (++this.failures > 10) {
                        this.viewer?.clearEyeTracking();
                    }
                });
            }
            this.timer = nextFrame(step);
        };
        step();
    }

    stop() {
        this.enabled = false;
        this.viewer.eyeTrackingEnabled = false;
        ++this.generation;
        cancelFrame(this.timer);
        clearTimeout(this.retryTimer);
        if (typeof window !== 'undefined') {
            window.removeEventListener('pointermove', this.pointerListener);
            window.removeEventListener('blur', this.leaveListener);
            window.removeEventListener('pointerout', this.leaveListener);
        }
        this.lastPointerAt = 0;
        this.socket?.close();
        this.socket = null;
        this.lastStreamAt = 0;
        this.viewer?.clearEyeTracking();
        this.onChange(false);
    }
}
