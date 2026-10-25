// Companion camera tracking is an add-on, not VTuber tracking: the user's face
// and hands drive the rig while AI reactions, choreography and idle life keep
// running. Pure VTuber tracking must stay muted.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const THREE=require('../static/vendor/three/build/three.cjs');
const read=file=>fs.readFileSync('static/js/'+file,'utf8');

// 1. The camera modes toggle both flags together.
const cameraCtx={};
vm.runInNewContext(read('companion-camera.js')
    .replace('export default class CompanionCamera','class CompanionCamera')
    .replace('export class CompanionCameraModes','class CompanionCameraModes')+'\nthis.Modes=CompanionCameraModes;',cameraCtx);
const calls=[];
const viewer={setVtuberTrackingMode:value=>calls.push(['vtuber',value]),setCompanionTracking:value=>calls.push(['companion',value])};
const objectCamera={start:async()=>calls.push(['objects','on']),stop:()=>calls.push(['objects','off'])};
const avatarTracking={enabled:false,setFaceSource:source=>calls.push(['source',source]),async start(){this.enabled=true;},stop(){this.enabled=false;}};
(async()=>{
    const modes=new cameraCtx.Modes({objectCamera,avatarTracking,viewer});
    await modes.start('objects','cam1');
    assert.deepEqual(calls,[['objects','off'],['objects','on']],'Object mode must not touch avatar tracking flags');
    calls.length=0;
    await modes.start('tracking','cam1','mediapipe','webcam');
    assert.deepEqual(calls,[['objects','off'],['companion',true],['vtuber',true],['source','webcam']],'Tracking add-on marks itself before preparing the VTuber rig');
    calls.length=0;
    modes.stop();
    assert.deepEqual(calls,[['objects','off'],['vtuber',false],['companion',false]],'Stopping clears both tracking flags');

    // 2. AI reactions stay available for the add-on only.
    const reactionCtx={};
    vm.runInNewContext(read('reaction-expressions.js')
        .replace(/export default class /,'class ').replace(/export function /g,'function ')+
        '\nthis.Controller=ReactionExpressions;',reactionCtx);
    const makeViewer=flags=>({model:{},activity:'talking',getMorphNames:()=>['Happy'],setMorph(){},...flags});
    const pure=new reactionCtx.Controller(makeViewer({vtuberTrackingMode:true,userTracking:true}));
    assert.equal(pure.begin('That was great!'),false,'VTuber tracking still mutes AI reactions');
    const addon=new reactionCtx.Controller(makeViewer({vtuberTrackingMode:true,userTracking:true,companionTracking:true}));
    assert.equal(addon.begin('That was great!'),true,'Companion tracking keeps AI reactions');
    // The same predicate app.js installs for automatic expression choice.
    const automatic=v=>!v.vtuberTrackingMode||!!v.companionTracking;
    assert.equal(automatic({vtuberTrackingMode:true}),false);
    assert.equal(automatic({vtuberTrackingMode:true,companionTracking:true}),true);
    assert.equal(automatic({vtuberTrackingMode:false}),true);

    // 3. Choreography may take over the bones during companion tracking.
    const danceCtx={THREE,console,ImportedGreeting:class{constructor(){this.data={duration:4.067};}async load(){}begin(){return {};}apply(){}restore(){}}};
    vm.runInNewContext(read('hand-presentation.js').replace(/import .*?;\r?\n/,'').replace('export function presentHand','function presentHand'),danceCtx);
    vm.runInNewContext(read('model-dance.js').replace(/^import .*?;\r?\n/gm,'').replace('export default class ModelDance','class ModelDance')+'\nthis.Dance=ModelDance;',danceCtx);
    const model=new THREE.Group(),rig={model,vrm:null,physics:{},animationBones:{},_avoidArmClipping(){}};
    for(const key of ['torso','chest','head','leftArm','rightArm','leftElbow','rightElbow','leftWrist','rightWrist','leftThigh','rightThigh','leftKnee','rightKnee'])
        rig.animationBones[key]={bone:new THREE.Bone(),rest:new THREE.Euler()};
    const dance=new danceCtx.Dance(rig);
    rig.userTracking=true;rig.vtuberTrackingMode=true;
    assert.equal(dance.start('groove'),false,'Pure VTuber tracking still blocks dance');
    rig.companionTracking=true;
    assert.equal(dance.start('groove'),true,'Companion tracking allows choreography');
    for(let i=0;i<90;i++)dance.update(1/60);
    for(const entry of Object.values(rig.animationBones))assert.ok(entry.bone.quaternion.toArray().every(Number.isFinite));
    dance.stop(true);
    assert.equal(dance.active,null);
    rig.companionTracking=false;assert.equal(dance.start('groove'),false,'Removing the add-on restores the tracking mute');

    // 4. Idle breathing resumes under the tracked pose.
    const breathingCtx={};
    vm.runInNewContext(read('idle-breathing.js').replace(/export function /g,'function ')+
        '\nthis.apply=applyIdleBreathing;this.restore=restoreIdleBreathing;',breathingCtx);
    const chest=new THREE.Bone(),breathRig={model:{},activity:'idle',userTracking:true,animationBones:{chest:{bone:chest}}};
    for(let i=0;i<20;i++)breathingCtx.apply(breathRig,1/60,i/60);
    assert.equal(chest.rotation.x,0,'Pure tracking has no idle breathing');
    breathRig.companionTracking=true;
    for(let i=0;i<90;i++){breathingCtx.restore(breathRig);chest.rotation.x=0;breathingCtx.apply(breathRig,1/60,i/60);}
    assert.ok(Math.abs(chest.rotation.x)>.001,'Companion tracking keeps subtle breathing');
    console.log('PASS: companion tracking keeps AI reactions, choreography and idle life while pure VTuber tracking stays muted.');
})().catch(error=>{console.error(error);process.exit(1);});
