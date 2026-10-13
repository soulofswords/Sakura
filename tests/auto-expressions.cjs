const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const saved=new Map(),ctx={performance,localStorage:{getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value)}};
vm.runInNewContext(fs.readFileSync('static/js/auto-expressions.js','utf8').replace(/export /g,'')+'\nthis.Auto=AutoExpressions;this.mapping=autoExpressionMapping;',ctx);
for(const type of ['pmx','vrm','live2d']){
    const weights={},model={},viewer={model,live2d:type==='live2d'?{setExpression:(name,value)=>weights[name]=value,removeExpression:name=>delete weights[name]}:null,vtuberTrackingMode:true,userTracking:true,allMorphNames:['Happy','Sad','Angry','Surprised','HideClothesSmile'],manualExpressions:new Map(),setMorph:(name,value)=>weights[name]=value};
    const controller=new ctx.Auto(viewer,type);assert.equal(controller.enabled,false,'Opt-in default');assert.equal(ctx.mapping(viewer).smile,'Happy','Costume switch excluded');
    controller.enabled=true;controller.save();viewer.userTrackingSample={receivedAt:performance.now(),face:{blendshapes:[{categoryName:'mouthSmileLeft',score:.9}]}};
    for(let i=0;i<90;i++)controller.update(1/60);assert.ok(weights.Happy>.6,type+' follows smile');
    viewer.manualExpressions.set('Happy',1);weights.Happy=1;controller.update(1/60);assert.equal(weights.Happy,1,'Manual expression is not overwritten');
    viewer.manualExpressions.clear();viewer.userTrackingSample.receivedAt=performance.now()-2000;for(let i=0;i<120;i++)controller.update(1/60);assert.ok((weights.Happy||0)<.001,'Face loss releases expression');
    controller.enabled=false;controller.clear();assert.ok((weights.Happy||0)<.001);
}
console.log('PASS: PMX/VRM/Live2D opt-in expressions, semantic detection, manual priority, face loss and clear');
