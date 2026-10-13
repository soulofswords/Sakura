const fs = require('node:fs');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
(async () => {
    const browser = await chromium.launch({headless: true, executablePath: process.env.AUDIT_CHROMIUM,
        args: ['--enable-webgl', '--use-angle=d3d11']});
    try {
        const page = await browser.newPage({viewport: {width: 640, height: 760}});
        const errors = [];
        page.on('pageerror', e => errors.push(String(e)));
        await page.goto('http://127.0.0.1:8766/static/physics-check.html');
        await page.waitForFunction(() => window.viewer?.physics);
        await page.click('#load');
        await page.waitForFunction(() => window.physicsReport, {timeout: 60000});
        await page.click('#wiggle');
        await page.waitForFunction(() => window.wiggleResult);
        await page.click('#stability');
        await page.waitForFunction(() => window.stabilityResult);
        const result = await page.evaluate(() => {
            const physics = window.viewer.physics;
            window.viewer.model.updateMatrixWorld(true);
            let worstTailError = 0;
            for (const node of physics.bullet ? [] : physics.nodes) {
                const actual = node.tailLocal.clone().applyMatrix4(node.bone.matrixWorld);
                worstTailError = Math.max(worstTailError, actual.distanceTo(node.pos));
            }
            return {physicsReport, wiggleResult, stabilityResult, worstTailError};
        });
        result.errors = errors;
        assert.ok(result.worstTailError < 1e-6, 'Rendered tails must match simulated particles');
        result.vrm = await page.evaluate(async () => {
            const models = (await (await fetch('/api/models')).json()).models.filter(m => /\.vrm$/i.test(m.path));
            const reports = [];
            for (const model of models) {
                await window.viewer.loadModel('/models/' + model.path.split('/').map(encodeURIComponent).join('/'));
                const joints = [...(window.viewer.vrm.springBoneManager?.joints || [])];
                window.viewer.setPhysicsMode('normal');
                const original = joints.map(j => ({...j.settings}));
                let bounded = true;
                for (const mode of ['subtle', 'lively', 'off', 'normal']) {
                    window.viewer.setPhysicsMode(mode);
                    for (let i = 0; i < 20; i++) window.viewer.vrm.update(1/60);
                    bounded &&= joints.every(j => Number.isFinite(j.bone.quaternion.x + j.bone.quaternion.y + j.bone.quaternion.z + j.bone.quaternion.w)
                        && j.settings.dragForce >= 0 && j.settings.dragForce <= 1);
                }
                const restored = joints.every((j, i) => ['stiffness', 'gravityPower', 'dragForce'].every(k => j.settings[k] === original[i][k]));
                reports.push({path: model.path, joints: joints.length, bounded, restored});
            }
            return reports;
        });
        assert.ok(result.vrm.every(r => r.bounded && r.restored));
        fs.mkdirSync('audit-results/physics-review', {recursive: true});
        fs.writeFileSync('audit-results/physics-review/live.json', JSON.stringify(result, null, 2));
        assert.equal(errors.length, 0);
        assert.ok(result.physicsReport.physics.bones > 0);
        assert.equal(result.physicsReport.physics.engine, 'Bullet');
        assert.ok(result.physicsReport.physics.rigidBodies > 0 && result.physicsReport.physics.joints > 0);
        assert.ok(result.wiggleResult.moved && result.wiggleResult.finite);
        assert.ok(result.stabilityResult.stable);
        console.log(JSON.stringify(result));
    } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
