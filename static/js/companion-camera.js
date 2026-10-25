// Explicit Companion vision permission. Never persisted or enabled on startup.
export default class CompanionCamera {
    constructor(onChange=()=>{}) { this.onChange=onChange;this.enabled=false;this.generation=0; }
    async start(deviceId='') {
        this.stop();const generation=this.generation;
        if(!navigator.mediaDevices?.getUserMedia)throw new Error('Camera access is unavailable.');
        const stream=await navigator.mediaDevices.getUserMedia({audio:false,video:{...(deviceId?{deviceId:{exact:deviceId}}:{}),width:{ideal:640},height:{ideal:480},frameRate:{ideal:15}}});
        if(generation!==this.generation){stream.getTracks().forEach(t=>t.stop());return;}
        this.stream=stream;this.video=document.createElement('video');
        this.video.muted=true;this.video.playsInline=true;this.video.srcObject=stream;
        try { await this.video.play(); }
        catch(error){if(generation===this.generation)this.stop();throw error;}
        if(generation!==this.generation)return;
        this.enabled=true;stream.getVideoTracks().forEach(t=>t.addEventListener('ended',()=>{if(generation===this.generation)this.stop();}));
        this.onChange(true);
    }
    snapshot() {
        if(this.remote)return this.enabled&&Date.now()-this.remoteAt<4000?this.remoteImage:null;
        if(!this.enabled||this.video?.readyState<2||!this.video?.videoWidth)return null;
        const canvas=document.createElement('canvas');const scale=Math.min(1,640/this.video.videoWidth);
        canvas.width=Math.round(this.video.videoWidth*scale);canvas.height=Math.round(this.video.videoHeight*scale);
        const context=canvas.getContext('2d');context.drawImage(this.video,0,0,canvas.width,canvas.height);
        const image=canvas.toDataURL('image/jpeg',.75).split(',')[1];
        context.clearRect(0,0,canvas.width,canvas.height);return image;
    }
    startRemote(){this.stop();this.remote=true;this.enabled=true;this.remoteImage=null;this.remoteAt=0;this.onChange(true);}
    remoteFrame(image){if(this.remote&&this.enabled&&typeof image==='string'&&image.startsWith('/9j/')){this.remoteImage=image;this.remoteAt=Date.now();}}
    stop(){this.generation++;this.enabled=false;this.remote=false;this.remoteImage=null;this.remoteAt=0;this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;if(this.video){this.video.pause();this.video.srcObject=null;}this.video=null;this.onChange(false);}
}

// Companion mode offers either image perception or local avatar tracking.
// Keep the paths mutually exclusive so tracking frames are never uploaded to
// the assistant and object images never start the tracking worker.
export class CompanionCameraModes {
    constructor({objectCamera, avatarTracking, viewer}) {
        this.objectCamera=objectCamera;
        this.avatarTracking=avatarTracking;
        this.viewer=viewer;
        this.mode='';
    }
    async start(mode, deviceId='', backend='mediapipe', faceSource='webcam') {
        if(!['objects','tracking'].includes(mode))throw new Error('Choose object recognition or face tracking.');
        this.stop();
        this.mode=mode;
        try {
            if(mode==='objects') await this.objectCamera.start(deviceId);
            else {
                // The tracking add-on keeps the companion's AI layers running:
                // setVtuberTrackingMode only prepares the rig for tracked drive.
                this.viewer?.setCompanionTracking(true);
                this.viewer?.setVtuberTrackingMode(true);
                this.avatarTracking.setFaceSource(faceSource);
                await this.avatarTracking.start(deviceId, backend);
            }
        } catch(error) {
            this.stop();
            throw error;
        }
    }
    stop() {
        const wasTracking=this.mode==='tracking'||!!this.avatarTracking?.enabled;
        this.objectCamera.stop();
        if(wasTracking){
            this.avatarTracking.stop();
            this.viewer?.setVtuberTrackingMode(false);
            this.viewer?.setCompanionTracking(false);
        }
        this.mode='';
    }
}
