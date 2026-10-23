import HeadPoseFilter from './head-pose-filter.js?v=1';
export default class AvatarTracking {
    constructor(viewer, status) {
        this.viewer = viewer;
        this.status = status;
        this.enabled = false;
        this.handTrackingEnabled = true;
        this.poseTrackingEnabled = true;
        this.backend = 'mediapipe';
        this.faceSource = 'webcam';
        this.vbridgerBlendshapes = [];
        this.nvidiaArBlendshapes = [];
        this.expressionAppBlendshapes = [];
        this.nvidiaArActive = false;
        this.expressionAppActive = false;
        this.nvidiaPollToken = 0;
        this.nvidiaFrameUploading = false;
        this.nvidiaCanvas = null;
        this.session = 0;
        this.frameRate = 15;
    }
    setHandTracking(enabled) {
        this.handTrackingEnabled = Boolean(enabled);
        this.worker?.postMessage({type: 'hands-enabled', enabled: this.handTrackingEnabled});
        if (this.viewer?.userTrackingSample) {
            this.viewer.updateUserTracking({...this.viewer.userTrackingSample, hands: [],
                handTrackingEnabled: this.handTrackingEnabled});
        }
    }
    setPoseTracking(enabled) {
        this.poseTrackingEnabled=Boolean(enabled);
        this.worker?.postMessage({type:'pose-enabled',enabled:this.poseTrackingEnabled});
    }
    async start(deviceId = '', backend = this.backend) {
        this.stop();
        this.backend = ['mediapipe','leap_motion','nvidia_gpu'].includes(backend) ? backend : 'mediapipe';
        this.headPoseFilter=new HeadPoseFilter();
        const session = ++this.session;
        this.status(this.backend === 'leap_motion' ? 'Connecting to Leap Motion and loading webcam face/arm tracking…'
            : this.backend === 'nvidia_gpu' ? 'Starting GPU-accelerated face, arm and finger tracking…'
            : this.handTrackingEnabled ? 'Loading local face, shoulder, arm and hand tracking…' : 'Loading local face tracking…');
        try {
            const stream = await navigator.mediaDevices.getUserMedia({audio: false, video: {
                ...(deviceId ? {deviceId: {exact: deviceId}} : {}),
                ...(this.cameraFacingMode ? {facingMode:{ideal:this.cameraFacingMode}} : {}),
                width: {ideal: 1280}, height: {ideal: 720}, frameRate: {ideal: this.frameRate, max: 60},
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
            this.worker = new Worker('/static/js/avatar-tracking-worker.js?v=presence128');
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
                this.worker.postMessage({type: 'init', handsEnabled: this.handTrackingEnabled, poseEnabled:this.poseTrackingEnabled, backend: this.backend, preferGPU: this.preferGPU === true});
            });
            if (session !== this.session) return;
            if (this.faceSource === 'nvidia_ar') await this.startNvidiaAR(session);
            if (this.faceSource === 'nvidia_expressionapp') await this.startExpressionApp(session);
            if (session !== this.session) return;
            this.cameraFrameRate = Number(stream.getVideoTracks()[0]?.getSettings?.().frameRate) || 0;
            this.measuredFps = 0; this.fpsSamples = 0; this.fpsStarted = performance.now();
            this.enabled = true;
            this.viewer.setUserTracking(true);
            if (['vbridger','nvidia_vts'].includes(this.faceSource)) this.pollVBridger(session);
            if (this.faceSource === 'nvidia_ar') this.pollNvidiaAR(session);
            if (this.faceSource === 'nvidia_expressionapp') this.pollExpressionApp(session);
            this.worker.onmessage = ({data}) => {
                if (session !== this.session) return;
                this.busy = false;
                if (data.type === 'error') {
                    this.status(`Tracking stopped: ${data.error}`);
                    this.stop();
                } else if (data.type === 'result') {
                    this.fpsSamples++;
                    const elapsed = performance.now() - this.fpsStarted;
                    if (elapsed >= 1000) { this.measuredFps = Math.round(this.fpsSamples * 1000 / elapsed); this.fpsSamples = 0; this.fpsStarted = performance.now(); }

                    // A frame already in flight can arrive just after the user
                    // turns body tracking off. Honor the current toggle rather
                    // than the setting captured when that frame began.
                    const sample = {...data, hands:this.handTrackingEnabled ? data.hands : [], pose:this.poseTrackingEnabled ? data.pose : null};
                    const incomingFace = this.faceSource === 'nvidia_expressionapp' && this.expressionAppBlendshapes.length
                        ? {...data.face, blendshapes:this.expressionAppBlendshapes}
                        : this.faceSource === 'nvidia_ar' && this.nvidiaArBlendshapes.length
                        ? {...data.face, blendshapes:this.nvidiaArBlendshapes}
                        : ['vbridger','nvidia_vts'].includes(this.faceSource) && this.vbridgerBlendshapes.length
                            ? {...data.face, blendshapes:this.vbridgerBlendshapes} : data.face;
                    sample.face=this.headPoseFilter.update(incomingFace,data.timestamp,data.distanceAssist);
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
                    this.status(`${faceStatus} · ${bodyStatus} · ${this.measuredFps} processed FPS${Number.isFinite(data.processingMs) ? ` · inference ${Math.round(data.processingMs)} ms` : ''} / target ${this.frameRate}${this.cameraFrameRate ? ` · camera ${Math.round(this.cameraFrameRate)} FPS` : ''}`);
                }
            };
            this.worker.onerror = e => { this.status(e.message || 'Tracking worker failed.'); this.stop(); };
            this.busy = false;
            this.lastFrame = 0;
            this.timer = setInterval(async () => {
                if (!this.enabled || this.video.readyState < 2 || this.video.currentTime === this.lastFrame) return;
                this.lastFrame = this.video.currentTime;
                if (this.faceSource === 'nvidia_ar') this.uploadNvidiaFrame(session);
                if (this.busy) return;
                this.busy = true;
                try {
                    // Resize before transferring pixels to the worker, rather than
                    // copying a 720p/1080p frame only to immediately shrink it.
                    const width=Math.min(this.inferenceWidth||640,this.video.videoWidth);
                    const height=Math.max(1,Math.round(width*this.video.videoHeight/this.video.videoWidth));
                    this.captureCanvas ||= document.createElement('canvas');
                    if(this.captureCanvas.width!==width||this.captureCanvas.height!==height){this.captureCanvas.width=width;this.captureCanvas.height=height;}
                    this.captureCanvas.getContext('2d',{alpha:false}).drawImage(this.video,0,0,width,height);
                    const image = await createImageBitmap(this.captureCanvas);
                    if (session !== this.session) { image.close(); return; }
                    // Live2D currently consumes face signals only. Keep the
                    // user's hand preference for the next 3D model, while
                    // avoiding body inference that cannot move this avatar.
                    this.worker.postMessage({type: 'frame', image, timestamp: performance.now(),
                        bodyTracking: !this.viewer.live2d && this.poseTrackingEnabled,
                        inferenceWidth:this.inferenceWidth||640,poseStride:this.poseStride||2}, [image]);
                } catch (error) { this.busy = false; this.status(error.message); }
            }, Math.max(4, Math.floor(1000 / this.frameRate)));
        } catch (error) {
            if (session !== this.session) return;
            this.stop();
            if (error.name === 'NotReadableError') {
                throw new Error('Camera could not start. Close other apps using it, check that it is connected, then select your camera and retry. AI remains paused.');
            }
            if (error.name === 'NotFoundError') {
                throw new Error('No webcam found. Connect a camera and retry. AI remains paused.');
            }
            if (this.backend === 'nvidia_gpu') {
                throw new Error(`GPU tracking could not start: ${error.message}. Check browser hardware acceleration and set Sakura to use the NVIDIA GPU in Windows Graphics settings, or switch to MediaPipe.`);
            }
            throw error;
        }
    }
    calibrate() { this.viewer.calibrateUserTracking(); }
    setFaceSource(source) {
        const next = ['webcam','nvidia_broadcast','nvidia_ar','nvidia_expressionapp','nvidia_vts','vbridger'].includes(source) ? source : 'webcam';
        const wasNvidiaAr = this.faceSource === 'nvidia_ar';
        const wasExpressionApp = this.faceSource === 'nvidia_expressionapp';
        this.faceSource = next;
        this.vbridgerBlendshapes = [];
        this.nvidiaArBlendshapes = [];
        if (this.enabled && next === 'nvidia_ar' && !wasNvidiaAr) {
            this.startNvidiaAR(this.session).then(() => this.pollNvidiaAR(this.session)).catch(error => this.status(error.message));
        } else if (wasNvidiaAr && next !== 'nvidia_ar') {
            this.nvidiaPollToken++;
            this.nvidiaArActive = false;
            fetch('/api/tracking/nvidia-ar/stop', {method:'POST'}).catch(()=>{});
        }
        if (this.enabled && next === 'nvidia_expressionapp' && !wasExpressionApp) {
            this.startExpressionApp(this.session).then(() => this.pollExpressionApp(this.session)).catch(error => this.status(error.message));
        } else if (wasExpressionApp && next !== 'nvidia_expressionapp') {
            this.expressionAppPollToken++;
            this.expressionAppActive = false;
            fetch('/api/tracking/nvidia-expressionapp/stop', {method:'POST'}).catch(()=>{});
        }
        if (this.enabled && ['vbridger','nvidia_vts'].includes(this.faceSource)) this.pollVBridger(this.session);
    }
    async startNvidiaAR(session) {
        if (this.nvidiaArActive) return;
        this.status('Loading NVIDIA AR SDK face-expression model on the RTX GPU…');
        const response = await fetch('/api/tracking/nvidia-ar/start', {method:'POST'});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Could not start Sakura’s native NVIDIA RTX tracker.');
        if (session !== this.session || this.faceSource !== 'nvidia_ar') {
            fetch('/api/tracking/nvidia-ar/stop', {method:'POST'}).catch(()=>{});
            return;
        }
        this.nvidiaArActive = true;
        this.status('NVIDIA AR SDK is ready · sending selected camera frames to Sakura’s local RTX tracker.');
    }
    async uploadNvidiaFrame(session) {
        if (this.nvidiaFrameUploading || !this.video?.videoWidth || session !== this.session) return;
        this.nvidiaFrameUploading = true;
        try {
            const scale = Math.min(1, 960 / this.video.videoWidth, 720 / this.video.videoHeight);
            const width = Math.max(1, Math.round(this.video.videoWidth * scale));
            const height = Math.max(1, Math.round(this.video.videoHeight * scale));
            this.nvidiaCanvas ||= document.createElement('canvas');
            this.nvidiaCanvas.width = width; this.nvidiaCanvas.height = height;
            this.nvidiaCanvas.getContext('2d', {alpha:false}).drawImage(this.video, 0, 0, width, height);
            const blob = await new Promise(resolve => this.nvidiaCanvas.toBlob(resolve, 'image/jpeg', .78));
            if (!blob || session !== this.session || this.faceSource !== 'nvidia_ar') return;
            const response = await fetch(`/api/tracking/nvidia-ar/frame?width=${width}&height=${height}`, {
                method:'POST', headers:{'Content-Type':'image/jpeg'}, body:blob,
            });
            if (!response.ok) {
                const data = await response.json().catch(()=>({}));
                throw new Error(data.error || 'NVIDIA RTX tracker rejected a camera frame.');
            }
        } catch (error) {
            if (session === this.session) this.status(`NVIDIA RTX tracker: ${error.message}`);
        } finally { this.nvidiaFrameUploading = false; }
    }
    async pollNvidiaAR(session) {
        const token = ++this.nvidiaPollToken;
        while (this.enabled && session === this.session && token === this.nvidiaPollToken && this.faceSource === 'nvidia_ar') {
            try {
                const response = await fetch('/api/tracking/nvidia-ar', {cache:'no-store'});
                const data = await response.json();
                if (!response.ok || data.error) throw new Error(data.error || 'NVIDIA AR tracker is not running.');
                this.nvidiaArBlendshapes = data.connected
                    ? Object.entries(data.blendshapes || {}).map(([categoryName, score]) => ({categoryName, score})) : [];
                if (!data.connected) this.status(data.running
                    ? 'NVIDIA RTX tracker ready · waiting for a camera frame.'
                    : 'NVIDIA RTX tracker is not running. Enable it again in Camera settings.');
            } catch (error) { this.status(`NVIDIA RTX tracker unavailable: ${error.message}`); }
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    }
    async startExpressionApp(session) {
        if (this.expressionAppActive) return;
        this.status('Starting the VTube Studio NVIDIA tracker engine inside Sakura…');
        const response=await fetch('/api/tracking/nvidia-expressionapp/start',{method:'POST'});
        const data=await response.json();
        if(!response.ok)throw new Error(data.error||'Could not start the NVIDIA ExpressionApp tracker.');
        if(session!==this.session||this.faceSource!=='nvidia_expressionapp'){
            fetch('/api/tracking/nvidia-expressionapp/stop',{method:'POST'}).catch(()=>{});return;
        }
        this.expressionAppActive=true;
        this.status('NVIDIA Broadcast Tracker is running directly in Sakura · waiting for camera output.');
    }
    async pollExpressionApp(session) {
        const token=this.expressionAppPollToken=(this.expressionAppPollToken||0)+1;
        while(this.enabled&&session===this.session&&token===this.expressionAppPollToken&&this.faceSource==='nvidia_expressionapp'){
            try{
                const response=await fetch('/api/tracking/nvidia-expressionapp',{cache:'no-store'});
                const data=await response.json();
                if(!response.ok||data.error)throw new Error(data.error||'ExpressionApp tracker stopped.');
                this.expressionAppBlendshapes=data.connected
                    ?Object.entries(data.blendshapes||{}).map(([categoryName,score])=>({categoryName,score})):[];
                if(!data.connected)this.status(data.running
                    ?'NVIDIA tracker launched · waiting for its selected webcam.'
                    :'NVIDIA tracker is not running. Check the Steam DLC folder and camera index.');
            }catch(error){this.status(`NVIDIA tracker unavailable: ${error.message}`);}
            await new Promise(resolve=>setTimeout(resolve,100));
        }
    }
    async pollVBridger(session) {
        while (this.enabled && session === this.session && ['vbridger','nvidia_vts'].includes(this.faceSource)) {
            try {
                const response = await fetch('/api/tracking/vbridger', {cache:'no-store'});
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'VBridger receiver could not start.');
                this.vbridgerBlendshapes = data.connected
                    ? Object.entries(data.blendshapes || {}).map(([categoryName, score]) => ({categoryName, score})) : [];
                if (!data.connected) this.status(`Webcam tracking active · waiting for ${this.faceSource === 'nvidia_vts' ? 'VTube Studio → VBridger' : 'VBridger'} VMC on 127.0.0.1:39539`);
            } catch (error) {
                this.status(`Webcam tracking active · VBridger unavailable: ${error.message}`);
            }
            await new Promise(resolve => setTimeout(resolve, 150));
        }
    }
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
        this.captureCanvas = null;
        this.vbridgerBlendshapes = [];
        this.nvidiaArBlendshapes = [];
        this.expressionAppBlendshapes = [];
        this.nvidiaPollToken++;
        if (this.nvidiaArActive) fetch('/api/tracking/nvidia-ar/stop', {method:'POST'}).catch(()=>{});
        this.expressionAppPollToken++;
        if (this.expressionAppActive) fetch('/api/tracking/nvidia-expressionapp/stop', {method:'POST'}).catch(()=>{});
        this.nvidiaArActive = false;
        this.nvidiaFrameUploading = false;
        this.viewer?.setUserTracking(false);
    }
}
