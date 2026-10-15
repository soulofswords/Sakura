import HeadPoseFilter from './head-pose-filter.js?v=1';
export default class AvatarTracking {
    constructor(viewer, status) {
        this.viewer = viewer;
        this.status = status;
        this.enabled = false;
        this.handTrackingEnabled = true;
        this.session = 0;
        this.frameRate = 15;
    }
    setHandTracking(enabled) {
        this.handTrackingEnabled = Boolean(enabled);
        this.worker?.postMessage({type: 'hands-enabled', enabled: this.handTrackingEnabled});
        if (this.viewer?.userTrackingSample) {
            this.viewer.updateUserTracking({...this.viewer.userTrackingSample, hands: [], pose: null,
                handTrackingEnabled: this.handTrackingEnabled});
        }
    }
    async start(deviceId = '') {
        this.stop();
        this.headPoseFilter=new HeadPoseFilter();
        const session = ++this.session;
        this.status(this.handTrackingEnabled ? 'Loading local face, shoulder, arm and hand tracking…' : 'Loading local face tracking…');
        try {
            const stream = await navigator.mediaDevices.getUserMedia({audio: false, video: {
                ...(deviceId ? {deviceId: {exact: deviceId}} : {}),
                ...(this.cameraFacingMode ? {facingMode:{ideal:this.cameraFacingMode}} : {}),
                width: {ideal: 1280}, height: {ideal: 720}, frameRate: {ideal: 24, max: 30},
            }});
            if (session !== this.session) { stream.getTracks().forEach(t => t.stop()); return; }
            this.stream = stream;
            this.video = document.createElement('video');
            this.video.muted = true;
            this.video.playsInline = true;
            this.video.srcObject = this.stream;
            await this.video.play();
            if (session !== this.session) return;
            // MediaPipe's WASM loader calls importScripts internally, so this
            // must remain a classic worker.  The cache-busted module import in
            // the worker keeps Chromium from reusing its earlier MIME failure.
            this.worker = new Worker('/static/js/avatar-tracking-worker.js?v=distance6');
            await new Promise((resolve, reject) => {
                const timer = setTimeout(() => finish(new Error('Tracking initialization timed out. Retry your camera.')), 45000);
                const finish = error => {
                    clearTimeout(timer); this.cancelInit = null;
                    error ? reject(error) : resolve();
                };
                this.cancelInit = () => finish(new Error('Tracking cancelled.'));
                this.worker.onerror = e => finish(new Error(e.message || 'Tracking worker failed.'));
                this.worker.onmessage = ({data}) => {
                    if (data.type === 'ready') finish();
                    if (data.type === 'error') finish(new Error(data.error));
                };
                this.worker.postMessage({type: 'init', handsEnabled: this.handTrackingEnabled});
            });
            if (session !== this.session) return;
            this.enabled = true;
            this.viewer.setUserTracking(true);
            this.worker.onmessage = ({data}) => {
                if (session !== this.session) return;
                this.busy = false;
                if (data.type === 'error') {
                    this.status(`Tracking stopped: ${data.error}`);
                    this.stop();
                } else if (data.type === 'result') {
                    // A frame already in flight can arrive just after the user
                    // turns body tracking off. Honor the current toggle rather
                    // than the setting captured when that frame began.
                    const sample = this.handTrackingEnabled ? data : {...data, hands: [], pose: null};
                    sample.face=this.headPoseFilter.update(data.face,data.timestamp,data.distanceAssist);
                    sample.headPoseFiltered=true;
                    sample.handTrackingEnabled = this.handTrackingEnabled;
                    this.viewer.updateUserTracking(sample);
                    const pose = sample.pose?.landmarks;
                    const shouldersVisible = pose?.[11]?.visibility > .35 && pose?.[12]?.visibility > .35;
                    const bodyStatus = this.handTrackingEnabled
                        ? sample.hands.length ? `${shouldersVisible ? 'shoulders visible' : 'shoulders not visible'} · ${sample.hands.length} hand detections`
                            : 'No hands visible · arms returning to rest'
                        : 'shoulder, arm and hand tracking off';
                    const faceStatus=data.face.landmarks.length?(data.distanceAssist?.faceZoomed?'Face tracked · distance assist':'Face tracked'):'Face not detected · face the camera, improve lighting, or move closer';
                    this.status(`${faceStatus} · ${bodyStatus} · tracking only`);
                }
            };
            this.worker.onerror = e => { this.status(e.message || 'Tracking worker failed.'); this.stop(); };
            this.busy = false;
            this.lastFrame = 0;
            this.timer = setInterval(async () => {
                if (!this.enabled || this.busy || this.video.readyState < 2 || this.video.currentTime === this.lastFrame) return;
                this.busy = true;
                this.lastFrame = this.video.currentTime;
                try {
                    const image = await createImageBitmap(this.video);
                    if (session !== this.session) { image.close(); return; }
                    // Live2D currently consumes face signals only. Keep the
                    // user's hand preference for the next 3D model, while
                    // avoiding body inference that cannot move this avatar.
                    this.worker.postMessage({type: 'frame', image, timestamp: performance.now(),
                        bodyTracking: !this.viewer.live2d && this.handTrackingEnabled}, [image]);
                } catch (error) { this.busy = false; this.status(error.message); }
            }, Math.round(1000 / this.frameRate));
        } catch (error) {
            if (session !== this.session) return;
            this.stop();
            if (error.name === 'NotReadableError') {
                throw new Error('Camera could not start. Close other apps using it, check that it is connected, then select your camera and retry. AI remains paused.');
            }
            if (error.name === 'NotFoundError') {
                throw new Error('No webcam found. Connect a camera and retry. AI remains paused.');
            }
            throw error;
        }
    }
    calibrate() { this.viewer.calibrateUserTracking(); }
    stop() {
        ++this.session;
        this.cancelInit?.();
        this.enabled = false;
        clearInterval(this.timer);
        this.worker?.terminate();
        this.worker = null;
        this.stream?.getTracks().forEach(t => t.stop());
        this.stream = null;
        if (this.video) { this.video.pause(); this.video.srcObject = null; }
        this.video = null;
        this.viewer?.setUserTracking(false);
    }
}
