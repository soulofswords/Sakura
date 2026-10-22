// Full-viewport snapshots preserve framing across 3D and Live2D renderers.
// Keep the old character intact during loading, then turn its blocks into the new one.
export default class ModelBlockTransition {
    constructor(viewer){this.viewer=viewer;this.serial=0;}
    snapshot(){
        this.viewer._renderFrame();
        const source=this.viewer.live2d?.app?.view||this.viewer.renderer.domElement;
        if(!source?.width||!source?.height)return null;
        const scale=Math.min(1,720/Math.max(source.width,source.height));
        const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(source.width*scale));canvas.height=Math.max(1,Math.round(source.height*scale));
        canvas.getContext('2d',{willReadFrequently:true}).drawImage(source,0,0,canvas.width,canvas.height);
        return canvas;
    }
    begin(){
        this.cancel();
        if(!this.viewer.model||globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return false;
        let source;try{source=this.snapshot();}catch(error){console.warn('Model transition capture unavailable:',error);return false;}
        if(!source)return false;
        if(!document.getElementById('model-block-transition-style')){
            const style=document.createElement('style');style.id='model-block-transition-style';
            style.textContent='.model-block-switch>canvas:not(.model-block-transition){visibility:hidden!important}';document.head.append(style);
        }
        const canvas=document.createElement('canvas');canvas.className='model-block-transition';canvas.setAttribute('aria-hidden','true');
        canvas.width=source.width;canvas.height=source.height;
        Object.assign(canvas.style,{position:'absolute',inset:'0',width:'100%',height:'100%',zIndex:'3',pointerEvents:'none'});
        this.canvas=canvas;this.source=source;this.phase='waiting';this.tiles=[];
        canvas.getContext('2d',{willReadFrequently:true}).drawImage(source,0,0);
        this.viewer.container.append(canvas);this.viewer.container.classList.add('model-block-switch');
        this.timeout=setTimeout(()=>this.cancel(),45000);return true;
    }
    makeTiles(old,next){
        const a=old.getContext('2d',{willReadFrequently:true}).getImageData(0,0,old.width,old.height).data;
        const b=next.getContext('2d',{willReadFrequently:true}).getImageData(0,0,next.width,next.height).data;
        const size=Math.max(14,Math.ceil(old.width/30)),tiles=[];
        for(let y=0;y<old.height;y+=size)for(let x=0;x<old.width;x+=size){
            const w=Math.min(size,old.width-x),h=Math.min(size,old.height-y);let alpha=0;
            for(let sy=y;sy<y+h;sy+=3)for(let sx=x;sx<x+w;sx+=3){const i=(sy*old.width+sx)*4+3;alpha=Math.max(alpha,a[i],b[i]);}
            if(alpha<12)continue;
            tiles.push({x,y,w,h,delay:(y/old.height*.75+x/old.width*.25)*.50});
        }
        return tiles;
    }
    draw(now){
        const canvas=this.canvas,ctx=canvas.getContext('2d',{willReadFrequently:true}),age=(now-this.start)/900;
        ctx.clearRect(0,0,canvas.width,canvas.height);
        for(const tile of this.tiles){
            const t=Math.max(0,Math.min(1,(age-tile.delay)/.5));
            const p=t*t*(3-2*t),next=p>=.5,width=Math.abs(1-2*p);
            if(width<.008)continue;
            const height=1-Math.sin(p*Math.PI)*.12;
            ctx.save();ctx.translate(tile.x+tile.w/2,tile.y+tile.h/2);
            ctx.scale(width,height);
            ctx.drawImage(next?this.next:this.source,tile.x,tile.y,tile.w,tile.h,-tile.w/2,-tile.h/2,tile.w,tile.h);
            if(t>.05&&t<.95){ctx.strokeStyle='rgba(185,180,255,.7)';ctx.lineWidth=.7;ctx.strokeRect(-tile.w/2,-tile.h/2,tile.w,tile.h);}
            ctx.restore();
        }
        if(age>=1)this.cancel();
    }
    async reveal(){
        if(!this.canvas)return;
        try{
            const next=this.snapshot();if(!next){this.cancel();return;}
            // Resizing during loading must not stretch or crop the replacement.
            const normalized=document.createElement('canvas');normalized.width=this.source.width;normalized.height=this.source.height;
            normalized.getContext('2d',{willReadFrequently:true}).drawImage(next,0,0,normalized.width,normalized.height);
            this.next=normalized;this.tiles=this.makeTiles(this.source,this.next);
            if(!this.tiles.length){this.cancel();return;}
            this.phase='in';this.start=performance.now();const serial=this.serial;
            const tick=now=>{if(serial!==this.serial||!this.canvas)return;this.draw(now);if(serial===this.serial&&this.canvas)this.raf=requestAnimationFrame(tick);};
            this.draw(this.start);this.raf=requestAnimationFrame(tick);
        }catch(error){this.cancel();console.warn('Model reveal unavailable:',error);}
    }
    cancel(){
        this.serial++;cancelAnimationFrame(this.raf);clearTimeout(this.timeout);
        this.canvas?.remove();this.canvas=null;this.source=null;this.next=null;this.tiles=[];
        this.viewer.container.classList.remove('model-block-switch');
    }
}
