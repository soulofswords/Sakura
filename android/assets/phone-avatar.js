import ModelViewer from '/static/js/model-viewer.js';
import LipSync from '/static/js/lip-sync.js';
import AvatarTracking from '/static/js/avatar-tracking.js';
const notice=document.getElementById('notice');
const CONTROLS_ORIGIN='https://appassets.androidplatform.net';
const announce=()=>parent.postMessage({type:'avatar-ready'},CONTROLS_ORIGIN);
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
    window.addEventListener('message',async event=>{
        if(event.origin!==CONTROLS_ORIGIN||event.source!==parent)return;
        const data=event.data;
        if(data?.type==='avatar-ping'){announce();return;}
        if(data?.type!=='avatar-call'||!['load','startTracking','stopTracking','calibrate','hands','speak','stop','pause'].includes(data.method)||!Array.isArray(data.args)||data.args.length>2)return;
        try{
            if(data.method==='load'&&(typeof data.args[0]!=='string'||!/^\/?models\//.test(data.args[0])||data.args[0].includes('..')))throw Error('Choose a saved phone model.');
            if(data.method==='speak'&&(typeof data.args[0]!=='string'||!/^\/?local-audio\//.test(data.args[0])))throw Error('Invalid phone audio.');
            const result=await window.phoneAvatar[data.method](...data.args);
            if(data.id)parent.postMessage({type:'avatar-reply',id:data.id,result},CONTROLS_ORIGIN);
        }catch(error){if(data.id)parent.postMessage({type:'avatar-reply',id:data.id,error:error.message},CONTROLS_ORIGIN);}
    });
    announce();
}catch(error){notice.textContent='3D/Live2D rendering unavailable: '+error.message;parent.postMessage({type:'avatar-error',error:error.message},CONTROLS_ORIGIN);}
