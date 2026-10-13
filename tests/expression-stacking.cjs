const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const src=fs.readFileSync('static/js/live2d-viewer.js','utf8').replace(/^import .*;\r?\n/gm,'').replace('export default class Live2DViewer','class Live2DViewer');
const context={};vm.runInNewContext(src+'\nthis.Viewer=Live2DViewer;',context);
const values=[.25,1];const core={getParameterIndex:id=>({face:0,accessory:1}[id]??-1),getParameterValueByIndex:i=>values[i],setParameterValueByIndex:(i,v)=>values[i]=v};
const view=Object.create(context.Viewer.prototype);view.expressions=new Map([
 ['smile',{Parameters:[{Id:'face',Value:.4,Blend:'Add'}]}],['accessory',{Parameters:[{Id:'accessory',Value:0,Blend:'Overwrite'}]}]
]);view.avatar={internalModel:{coreModel:core,motionManager:{expressionManager:{stopAllExpressions(){}}}}};
assert.equal(view.setExpression('smile',1),true);assert.equal(view.setExpression('accessory',1),true);assert.equal(view.activeExpressions.size,2);
for(let frame=0;frame<120;frame++){values[0]=.25;values[1]=1;view.applyManualExpressions();assert.ok(Math.abs(values[0]-.65)<1e-9);assert.equal(values[1],0);}
view.removeExpression('smile');values[0]=.25;values[1]=1;view.applyManualExpressions();assert.equal(values[0],.25);assert.equal(values[1],0);
view.clearExpression();assert.equal(view.activeExpressions.size,0);assert.equal(view.setExpression('missing'),false);
console.log('PASS: overlapping Live2D expressions, independent off, reset, absent expression, and 120 frames without accumulated drift');
const maskCore={getDrawableCount:()=>3,getDrawableMasks:()=>[new Int32Array([0]),new Int32Array([0,1]),new Int32Array(0)],getDrawableDynamicFlagVertexPositionsDidChange:()=>false};
view.avatar={internalModel:{coreModel:maskCore}};view.installMaskRefresh();
assert.equal(maskCore.getDrawableDynamicFlagVertexPositionsDidChange(0),true);
assert.equal(maskCore.getDrawableDynamicFlagVertexPositionsDidChange(1),true);
assert.equal(maskCore.getDrawableDynamicFlagVertexPositionsDidChange(2),false);
console.log('PASS: static mask sources redraw; non-mask drawable flags remain intact');
