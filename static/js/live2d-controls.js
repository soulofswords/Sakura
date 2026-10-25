// Pointer events work for both Android multi-touch and desktop mouse dragging.
export function installLive2DControls(view,owner,layer){
    view.style.touchAction='none';view.style.cursor='default';
    const hover=event=>{view.style.cursor=owner.controls?.enabled===false?'':layer.hitTestPoint(event.clientX,event.clientY)?'grab':'default';};
    const pointers=new Map();let gesture=null;
    function sample(){
        const points=[...pointers.values()];if(!points.length)return null;
        if(points.length===1)return {x:points[0].x,y:points[0].y,count:1};
        const [a,b]=points;return {x:(a.x+b.x)/2,y:(a.y+b.y)/2,distance:Math.hypot(a.x-b.x,a.y-b.y),count:2};
    }
    view.addEventListener('pointerdown',event=>{
        if(event.button!==0 || (!pointers.size&&!layer.hitTestPoint(event.clientX,event.clientY))){hover(event);return;}
        view.style.cursor='grabbing';
        pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});gesture=sample();
        try{view.setPointerCapture(event.pointerId);}catch(_){}
        if(event.cancelable)event.preventDefault();
    });
    view.addEventListener('pointermove',event=>{
        if(!pointers.has(event.pointerId)){if(!pointers.size&&event.pointerType!=='touch')hover(event);return;}
        pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});const next=sample();
        if(gesture&&next&&gesture.count===next.count){
            if(next.count===2&&gesture.distance>1&&next.distance>1){
                const rect=view.getBoundingClientRect(),before=owner.camera.zoom;
                const pan={...layer.pan};owner.setDisplaySize(before*next.distance/gesture.distance*100);
                const ratio=owner.camera.zoom/before;
                // Keep the point under the fingers in place while scaling.
                layer.pan.x=next.x-rect.left-rect.width/2-(gesture.x-rect.left-rect.width/2-pan.x)*ratio;
                layer.pan.y=next.y-rect.top-rect.height/2-(gesture.y-rect.top-rect.height/2-pan.y)*ratio;
            }else if(next.count===1){layer.pan.x+=next.x-gesture.x;layer.pan.y+=next.y-gesture.y;}
            layer.fit();
        }
        gesture=next;if(event.cancelable)event.preventDefault();
    });
    for(const type of ['pointerup','pointercancel','lostpointercapture'])view.addEventListener(type,event=>{pointers.delete(event.pointerId);gesture=sample();if(!pointers.size)hover(event);});
    view.addEventListener('pointerleave',()=>{if(!pointers.size)view.style.cursor='default';});
}
