export default class EyeTracking {
    constructor(viewer, onChange) {
        this.viewer = viewer;
        this.onChange = onChange;
        this.enabled = false;
        this.generation = 0;
        this.pointer = event => {
            if (this.enabled) this.viewer?.setEyeTrackingTarget(event.clientX / Math.max(1, window.innerWidth) * 2 - 1,
                event.clientY / Math.max(1, window.innerHeight) * 2 - 1);
        };
        this.leave = () => this.viewer?.clearEyeTracking();
    }

    start() {
        if (this.enabled) return;
        this.enabled = true;
        this.viewer.eyeTrackingEnabled = true;
        const generation = ++this.generation;
        this.onChange(true);
        if (window.pywebview?.api?.cursor_position) {
            const poll = async () => {
                if (!this.enabled || generation !== this.generation) return;
                try {
                    const point = await window.pywebview.api.cursor_position();
                    if (generation !== this.generation) return;
                    if (point && Number.isFinite(point.x) && Number.isFinite(point.y)) this.viewer?.setEyeTrackingTarget(point.x, point.y);
                } catch (_) { this.viewer?.clearEyeTracking(); }
                if (this.enabled && generation === this.generation) this.timer = setTimeout(poll, 80);
            };
            poll();
        } else {
            window.addEventListener('pointermove', this.pointer);
            document.addEventListener('pointerleave', this.leave);
        }
    }

    stop() {
        this.enabled = false;
        this.viewer.eyeTrackingEnabled = false;
        ++this.generation;
        clearTimeout(this.timer);
        window.removeEventListener('pointermove', this.pointer);
        document.removeEventListener('pointerleave', this.leave);
        this.viewer?.clearEyeTracking();
        this.onChange(false);
    }
}
