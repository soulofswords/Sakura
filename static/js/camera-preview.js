export function drawCameraPreview(context,video,sample,hideFace=true){
    const width=context.canvas.width,height=context.canvas.height;
    context.fillStyle='#101522';context.fillRect(0,0,width,height);
    const face=sample?.face?.landmarks||[];
    // Never reveal the camera image while privacy is enabled and face
    // detection is missing. The next frame can restore the masked preview.
    const finiteFace=face.filter(p=>Number.isFinite(p.x)&&Number.isFinite(p.y));
    if(video?.readyState>=2&&(!hideFace||finiteFace.length))context.drawImage(video,0,0,width,height);
    if(hideFace&&finiteFace.length){
        const xs=finiteFace.map(p=>p.x),ys=finiteFace.map(p=>p.y),x=Math.min(...xs),y=Math.min(...ys);
        const w=Math.max(...xs)-x,h=Math.max(...ys)-y;
        context.fillStyle='#151a2b';context.fillRect((x-w*.2)*width,(y-h*.35)*height,w*1.4*width,h*1.55*height);
    }
    const dot=(p,color,r=2)=>{if(!p||!Number.isFinite(p.x)||!Number.isFinite(p.y))return;context.fillStyle=color;context.beginPath();context.arc(p.x*width,p.y*height,r,0,Math.PI*2);context.fill();};
    for(const p of finiteFace)dot(p,'#73ffe8',1.5);
    const line=(a,b,color)=>{if(!a||!b)return;context.strokeStyle=color;context.beginPath();context.moveTo(a.x*width,a.y*height);context.lineTo(b.x*width,b.y*height);context.stroke();};
    for(const hand of sample?.hands||[]){for(const p of hand.landmarks||[])dot(p,'#fc96ea');for(const chain of [[0,1,2,3,4],[0,5,6,7,8],[0,9,10,11,12],[0,13,14,15,16],[0,17,18,19,20]])for(let i=1;i<chain.length;i++)line(hand.landmarks?.[chain[i-1]],hand.landmarks?.[chain[i]],'#fc96ea');}
    const pose=sample?.pose?.landmarks||[];
    for(const [a,b]of [[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24]])if(pose[a]?.visibility>.35&&pose[b]?.visibility>.35)line(pose[a],pose[b],'#f5d76b');
}

export function installCameraPreview(getTracker,getViewer){
    const enabled=document.getElementById('camera-preview-enabled'),privacy=document.getElementById('camera-preview-hide-face'),canvas=document.getElementById('camera-preview-canvas'),status=document.getElementById('camera-preview-status');
    let frame=0,last=0;
    const render=now=>{
        if(!enabled.checked)return;
        frame=requestAnimationFrame(render);
        if(canvas.offsetParent===null||now-last<1000/24)return;last=now;
        const tracker=getTracker(),viewer=getViewer(),sample=viewer?.userTrackingSample;
        const fresh=sample&&performance.now()-sample.receivedAt<600;
        const video=tracker?.enabled?tracker.video:null;
        if(video?.videoWidth){const height=Math.round(640*video.videoHeight/video.videoWidth);if(canvas.height!==height)canvas.height=height;}
        drawCameraPreview(canvas.getContext('2d'),video,fresh?sample:null,privacy.checked);
        status.textContent=fresh?video?(privacy.checked?'Face hidden · tracking overlay':'Camera and tracking preview'):'Phone tracking points · camera video stays on phone':privacy.checked?'Waiting for tracking · camera image hidden':'Start tracking to see the camera preview';
    };
    enabled.onchange=()=>{cancelAnimationFrame(frame);canvas.hidden=!enabled.checked;if(enabled.checked)frame=requestAnimationFrame(render);else{canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);status.textContent='Camera preview off';}};
    window.addEventListener('pagehide',()=>cancelAnimationFrame(frame));
}
