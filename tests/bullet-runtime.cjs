const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
(async () => {
    const browser = await chromium.launch({headless:true,executablePath:process.env.AUDIT_CHROMIUM,args:['--enable-webgl','--use-angle=d3d11']});
    try {
        const page = await browser.newPage();
        const errors = []; page.on('pageerror',e => errors.push(String(e)));
        await page.goto('http://127.0.0.1:8766/static/physics-check.html');
        await page.waitForFunction(() => window.viewer?.physics);
        const result = await page.evaluate(async () => {
            const THREE = await import('three');
            const {default:Bullet,initializeBullet,validBulletRig} = await import('/static/js/bullet-physics.js?v=bullet1');
            await initializeBullet();
            function fixture(withJoint) {
                const mesh = new THREE.SkinnedMesh(new THREE.BufferGeometry(),new THREE.MeshBasicMaterial());
                const bone = new THREE.Bone(); mesh.add(bone); mesh.bind(new THREE.Skeleton([bone]));
                const defaults = {rotation:[0,0,0],groupIndex:0,groupTarget:-1,positionDamping:.1,rotationDamping:.1,friction:.5,restitution:0,width:.5,height:1,depth:1,weight:1};
                const rigidBodies = [
                    {...defaults,boneIndex:-1,type:0,shapeType:1,position:[0,-3,0],width:10,height:1,depth:10},
                    {...defaults,boneIndex:0,type:1,shapeType:0,position:[0,3,0]},
                ];
                const constraints = withJoint ? [{rigidBodyIndex1:0,rigidBodyIndex2:1,position:[0,3,0],rotation:[0,0,0],
                    translationLimitation1:[0,0,0],translationLimitation2:[0,0,0],rotationLimitation1:[0,0,0],rotationLimitation2:[0,0,0],springPosition:[0,0,0],springRotation:[0,0,0]}] : [];
                mesh.geometry.userData.MMD = {rigidBodies,constraints};
                return mesh;
            }
            const check = mesh => {
                if (!validBulletRig(mesh)) throw Error('Valid fixture rejected');
                const engine = new Bullet(mesh); engine.setMode('normal');
                for (let i=0;i<650;i++) engine.update(1/65);
                const y = engine.engine.bodies[1].body.getWorldTransform().getOrigin().y();
                const contacts = engine.engine.world.getDispatcher().getNumManifolds();
                const joints = engine.engine.constraints.length;
                const allocated = engine.allocations.length;
                engine.dispose();
                return {y,contacts,joints,allocated,remaining:engine.allocations.length};
            };
            const collision = check(fixture(false)), constrained = check(fixture(true));
            const gl = window.viewer.renderer.getContext(), ext = gl.getExtension('WEBGL_debug_renderer_info');
            const renderer = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
            const cycles = Array.from({length:5},()=>check(fixture(false)));
            const timing = [];
            for (const hz of [30,60,120]) {
                const engine = new Bullet(fixture(false)); engine.setMode('normal');
                let steps = 0; engine.engine.update = () => steps++;
                for (let i=0;i<hz;i++) engine.update(1/hz);
                timing.push({hz,steps}); engine.dispose();
            }
            const bad = fixture(false); bad.geometry.userData.MMD.constraints.push({rigidBodyIndex1:5,rigidBodyIndex2:1});
            const pointAnchor = fixture(false);
            Object.assign(pointAnchor.geometry.userData.MMD.rigidBodies[0], {shapeType:2,width:0});
            const pointValid = validBulletRig(pointAnchor);
            const pointEngine = new Bullet(pointAnchor); pointEngine.setMode('normal');
            for(let i=0;i<130;i++) pointEngine.update(1/65);
            const anchorRadius = pointEngine.engine.bodies[0].params.width;
            const anchorFinite = Number.isFinite(pointEngine.engine.bodies[1].body.getWorldTransform().getOrigin().y());
            pointEngine.dispose();
            const zeroDynamic = fixture(false); zeroDynamic.geometry.userData.MMD.rigidBodies[1].width = 0;
            const windPositions = [];
            for (const wind of [0,1]) {
                const engine = new Bullet(fixture(false)); engine.setStrength(.75); engine.windStrength=wind;
                if(Math.abs(engine.engine.world.getGravity().y()+98)>.001)throw Error('Low strength changed gravity');
                for(let i=0;i<30;i++) engine.update(1/65);
                windPositions.push(engine.engine.bodies[1].body.getWorldTransform().getOrigin().x());
                engine.setStrength(0);
                const parked=engine.mesh.skeleton.bones[0].position.clone();
                engine.update(1); if(!parked.equals(engine.mesh.skeleton.bones[0].position))throw Error('Off moved the bone');
                engine.setStrength(1); engine.update(1/65);
                if(!Number.isFinite(engine.engine.bodies[1].body.getWorldTransform().getOrigin().y()))throw Error('Resume unstable');
                engine.dispose(); if(engine.allocations.length)throw Error('Wind resources leaked');
            }
            return {collision,constrained,cycles,timing,renderer,windPositions,brokenRejected:!validBulletRig(bad),
                pointValid,anchorRadius,anchorFinite,sourceRadius:pointAnchor.geometry.userData.MMD.rigidBodies[0].width,
                zeroDynamicRejected:!validBulletRig(zeroDynamic)};
        });
        result.errors = errors;
        fs.mkdirSync('audit-results/bullet',{recursive:true});
        fs.writeFileSync('audit-results/bullet/runtime.json',JSON.stringify(result,null,2));
        assert.equal(errors.length,0);
        assert.ok(result.collision.y > -1.6 && result.collision.y < -1.4);
        assert.ok(result.collision.contacts > 0);
        assert.ok(Math.abs(result.constrained.y-3) < .1);
        assert.equal(result.constrained.joints,1);
        assert.ok(result.cycles.every(c => c.remaining === 0 && c.allocated === result.collision.allocated));
        assert.ok(result.brokenRejected);
        assert.ok(Math.abs(result.windPositions[0]) < .001 && result.windPositions[1] > .1, 'Wind slider applies real force');
        assert.ok(result.pointValid && result.anchorFinite && result.zeroDynamicRejected);
        assert.equal(result.sourceRadius,0); assert.equal(result.anchorRadius,.001);
        assert.ok(Math.max(...result.timing.map(t=>t.steps))-Math.min(...result.timing.map(t=>t.steps)) <= 1);
        assert.ok(result.renderer.includes('Direct3D11'));
        console.log(JSON.stringify(result));
    } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exitCode=1});
