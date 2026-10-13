const fs = require('node:fs');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async()=>{
    const browser=await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--enable-webgl','--use-angle=d3d11']});
    try {
        const page=await browser.newPage({viewport:{width:650,height:900}});
        const errors=[];page.on('pageerror',e=>errors.push(String(e)));
        await page.goto('http://127.0.0.1:8766/static/library-audit.html');
        await page.waitForFunction(()=>typeof window.auditModel==='function');
        const result=await page.evaluate(async()=>{
            const cfg=await (await fetch('/api/settings')).json();
            const path=(cfg.settings||cfg).selected_model;
            const loaded=await window.auditModel(path);
            return {path,loaded};
        });
        assert.ok(result.loaded.visiblePixels>100,'Selected model renders');
        const motion=await page.evaluate(async()=>{
            const v=window.auditViewer;
            if(!v) throw new Error('Missing audit viewer');
            v.setEmotionFromText('How about we try this?');
            v.setActivity('talking');v.setSpeechLevel(.8);
            const poses=[];
            for(let i=0;i<300;i++) {
                if(i%30===0) poses.push(Object.fromEntries(Object.entries(v.animationBones).map(([key,e])=>[key,e.bone.rotation.toArray().slice(0,3)])));
                await new Promise(r=>requestAnimationFrame(r));
            }
            v.setActivity('idle');
            for(let i=0;i<120;i++) await new Promise(r=>requestAnimationFrame(r));
            let finite=true;v.model.traverse(e=>{if(e.isBone) finite&&=[...e.position.toArray(),...e.quaternion.toArray()].every(Number.isFinite);});
            const rigs=[];v.model.traverse(e=>{const rig=e.geometry?.userData?.MMD;if(rig) rigs.push({bodies:rig.rigidBodies?.length,joints:rig.constraints?.length,
                invalidBodies:(rig.rigidBodies||[]).flatMap((b,i)=>{
                    const fields=['width','height','depth','weight','positionDamping','rotationDamping','friction','restitution'].filter(k=>!Number.isFinite(b[k])||b[k]<0);
                    if(!Number.isInteger(b.boneIndex)||b.boneIndex < -1||b.boneIndex>=e.skeleton.bones.length) fields.push('boneIndex');
                    if(b.width<=0||(b.shapeType===1&&(b.height<=0||b.depth<=0))) fields.push('shapeDimensions');
                    return fields.length?[{i,name:b.name,shape:b.shapeType,fields,values:fields.map(k=>b[k])}]:[];
                }),
                invalidJoints:(rig.constraints||[]).flatMap((j,i)=>[j.rigidBodyIndex1,j.rigidBodyIndex2].some(n=>!Number.isInteger(n)||n<0||n>=rig.rigidBodies.length)?[{i,a:j.rigidBodyIndex1,b:j.rigidBodyIndex2}]:[]),
                dynamic:(rig.rigidBodies||[]).filter(b=>b.type===1||b.type===2).map(b=>({name:e.skeleton.bones[b.boneIndex]?.name,type:b.type,shape:b.shapeType,weight:b.weight}))});});
            return {poses,physics:v.physics.info,talkBlend:v.talkBlend,finite,fingers:v.conversationFingers.length,rigs};
        });
        assert.ok(motion.finite,'Skeleton stays finite');
        assert.ok(motion.talkBlend<.01,'Gestures settle after speech');
        assert.ok(motion.poses.some(p=>Math.abs(p.leftElbow?.[1]-motion.poses[0].leftElbow?.[1])>.04),'Elbow has visible conversational motion');
        assert.deepEqual(errors,[]);
        fs.mkdirSync('audit-results/conversation',{recursive:true});
        fs.writeFileSync('audit-results/conversation/live.json',JSON.stringify({result,motion,errors},null,2));
        await page.screenshot({path:'audit-results/conversation/taffy-idle.png'});
        await page.evaluate(()=>{const v=window.auditViewer;v.fullModelView=true;v._autoFrame(v.model);v.conversationMotion.time=0;v.conversationMotion.beat=0;v.setActivity('talking');v.setSpeechLevel(.8);});
        await page.waitForTimeout(1100);
        await page.screenshot({path:'audit-results/conversation/taffy-talking.png'});
        console.log(JSON.stringify({path:result.path,physics:motion.physics,fingers:motion.fingers,finite:motion.finite,errors}));
    } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
