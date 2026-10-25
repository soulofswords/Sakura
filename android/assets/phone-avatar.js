import ModelViewer from '/static/js/model-viewer.js';
import LipSync from '/static/js/lip-sync.js';
import AvatarTracking from '/static/js/avatar-tracking.js';
const notice=document.getElementById('notice');
try{
    const viewer=new ModelViewer('model-container');viewer.setQuality('low');viewer.fullModelView=true;
    const lips=new LipSync(viewer);
    const tracker=new AvatarTracking(viewer,message=>{notice.textContent=message;});
    window.phoneAvatar={
        async load(url){tracker.stop();lips.stop();notice.textContent='Loading model…';try{const result=await viewer.loadModel(url);if(!result)throw Error('Model loading did not complete.');notice.textContent='Drag to move · pinch to zoom';}catch(error){notice.textContent='Model could not load: '+error.message;throw error;}},
        async startTracking(facing='user',hands=false){viewer.setVtuberTrackingMode(true);tracker.cameraFacingMode=facing;tracker.frameRate=30;tracker.setHandTracking(hands);await tracker.start();},
        stopTracking(){tracker.stop();viewer.setVtuberTrackingMode(false);},
        calibrate:()=>tracker.calibrate(),hands:value=>tracker.setHandTracking(value),
        speak:url=>lips.playWithLipSync(url),stop:()=>lips.stop(),
        pause(value){if(value)tracker.stop();lips.stop();window.sakuraNativeHidden=!!value;viewer.container.style.visibility=value?'hidden':'visible';},
    };
    window.dispatchEvent(new Event('avatar-ready'));
}catch(error){notice.textContent='3D/Live2D rendering unavailable: '+error.message;window.phoneAvatarError=error.message;}
