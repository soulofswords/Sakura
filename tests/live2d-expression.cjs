const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync('static/js/live2d-viewer.js','utf8')
 .replace(/^import .*;\r?\n/gm,'').replace('export default class Live2DViewer','class Live2DViewer');
const context=vm.createContext({THREE:{},innerWidth:1000,innerHeight:600,PIXI:{live2d:{Cubism4ExpressionManager:class{constructor(settings){this.definitions=settings.expressions;}}}}});vm.runInContext(src+'\nthis.Live2DViewer=Live2DViewer;',context);
const viewer=Object.create(context.Live2DViewer.prototype),calls=[];
const definition={Name:'smile'};
const values=[.1,.1,.1];
const core={getParameterIndex:id=>['add','multiply','overwrite'].indexOf(id),getParameterValueByIndex:i=>values[i],setParameterValueByIndex:(i,value)=>values[i]=value};
const manager={stopAllExpressions(){calls.push('stop');},
 createExpression(data,def){return {data,def};},_setExpression(motion){calls.push(motion);}};
viewer.avatar={internalModel:{motionManager:{}}};
assert.equal(viewer.ensureExpressionManager({url:'model3.json'},[{Name:'smile',File:'expressions/smile.exp3.json'}]),true);
assert.equal(viewer.avatar.internalModel.motionManager.expressionManager.definitions[0].Name,'smile','sidecar expressions initialize Cubism manager when manifest omitted them');
viewer.avatar={internalModel:{coreModel:core,motionManager:{expressionManager:manager}}};
viewer.expressions=new Map([['smile',{Parameters:[
 {Id:'add',Value:.8,Blend:'Add'},
 {Id:'multiply',Value:.6,Blend:'Multiply'},
 {Id:'overwrite',Value:.2,Blend:'Overwrite'},
]}]]);
assert.equal(viewer.setExpression('missing',1),false);
assert.equal(viewer.setExpression('smile',.5),true);
viewer.applyManualExpressions();
for(const [i,expected]of [.5,.08,.15].entries())assert.ok(Math.abs(values[i]-expected)<1e-9,'expression blend and strength are correct');
assert.equal(viewer.expressions.get('smile').Parameters[0].Value,.8,'source expression JSON stays unchanged');
viewer.clearExpression();assert.equal(calls.at(-1),'stop');
const gazeCalls=[];viewer.owner={vtuberTrackingMode:true,physics:{mode:'normal'}};
viewer.avatar={internalModel:{physics:{},focusController:{focus(...args){gazeCalls.push(args);}}},focus(){gazeCalls.push(Array.from(arguments));},update(){}};
viewer.app={renderer:{render(){}}};viewer.gazePosition={x:0,y:0};viewer.setGazeTarget(.8,-.4);viewer.render(1/60);
assert.ok(gazeCalls.length);assert.ok(gazeCalls[0][0]>500&&gazeCalls[0][0]<900,'gaze interpolates toward the cursor instead of jumping');
viewer.clearGaze();assert.deepEqual(gazeCalls.at(-1),[0,0,true],'disabling eye tracking resets Cubism gaze to neutral');
console.log('PASS: Live2D expressions, smoothed cursor gaze, and neutral gaze reset');
