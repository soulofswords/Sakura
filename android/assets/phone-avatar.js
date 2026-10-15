import ModelViewer from '/static/js/model-viewer.js';
import LipSync from '/static/js/lip-sync.js';
const notice=document.getElementById('notice');
try{
    const viewer=new ModelViewer('model-container');viewer.setQuality('low');viewer.fullModelView=true;
    const lips=new LipSync(viewer);
    window.phoneAvatar={
        async load(url){lips.stop();notice.textContent='Loading model…';try{const result=await viewer.loadModel(url);if(!result)throw Error('Model loading did not complete.');notice.textContent='Drag to move · pinch to zoom';}catch(error){notice.textContent='Model could not load: '+error.message;throw error;}},
        speak:url=>lips.playWithLipSync(url),stop:()=>lips.stop(),
        pause(value){lips.stop();viewer.container.style.visibility=value?'hidden':'visible';},
    };
    window.dispatchEvent(new Event('avatar-ready'));
}catch(error){notice.textContent='3D/Live2D rendering unavailable: '+error.message;window.phoneAvatarError=error.message;}
