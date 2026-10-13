// Shared with the classic worker and geometry tests. No camera data is saved.
(function(scope){
    function box(points,aspect,padding=1.6,minSize=.08){
        const valid=points.filter(p=>p&&Number.isFinite(p.x)&&Number.isFinite(p.y)&&p.x>=0&&p.x<=1&&p.y>=0&&p.y<=1);
        if(valid.length<2)return null;
        const xs=valid.map(p=>p.x),ys=valid.map(p=>p.y),x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
        const size=Math.min(1,Math.max(minSize,Math.max(x1-x0,(y1-y0)/aspect)*padding));
        const height=Math.min(1,size*aspect),width=Math.min(1,height/aspect);
        return {x:Math.max(0,Math.min(1-width,(x0+x1)/2-width/2)),y:Math.max(0,Math.min(1-height,(y0+y1)/2-height/2)),width,height};
    }
    function faceRegion(face,pose,aspect){
        if(face?.length>10){const roi=box(face,aspect,1.8,.10);return roi&&roi.width<.48?roi:null;}
        // A visible head from body tracking helps reacquire a small face.
        const head=(pose||[]).slice(0,11).filter(p=>(p?.visibility??0)>.6);
        return head.length>=3?box(head,aspect,2.6,.14):null;
    }
    function handRegion(pose,aspect){
        if(![11,12,15,16].every(i=>pose?.[i]&&(pose[i].visibility??0)>.6))return null;
        const roi=box([pose[11],pose[12],pose[13],pose[14],pose[15],pose[16]].filter(p=>(p?.visibility??0)>.6),aspect,1.4,.18);
        return roi&&roi.width<.7?roi:null;
    }
    function remap(points,roi){return points.map(p=>({...p,x:roi.x+p.x*roi.width,y:roi.y+p.y*roi.height,z:(p.z||0)*roi.width}));}
    scope.TrackingDistance={box,faceRegion,handRegion,remap};
})(globalThis);
