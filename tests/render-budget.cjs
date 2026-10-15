const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const context={};
vm.runInNewContext(fs.readFileSync('static/js/render-budget.js','utf8').replace('export function','function'),context);
for(const [width,height]of [[320,600],[1920,1080],[3840,2160],[7680,4320],[12000,1200]]){
    let previous=0;
    for(const requested of [.75,1,1.25,2,3]){
        const ratio=context.renderPixelRatio(width,height,requested,4096);
        assert.ok(ratio>0&&ratio<=requested);
        assert.ok(width*height*ratio*ratio<=4_000_001,'Bound framebuffer memory at all quality levels');
        assert.ok(Math.ceil(width*ratio)*Math.ceil(height*ratio)<=4_000_000,'PIXI rounding stays inside budget');
        assert.ok(Math.max(width,height)*ratio<=4096.001,'Respect GPU dimensions');
        assert.ok(ratio>=previous);previous=ratio;
    }
}
assert.equal(context.renderPixelRatio(320,600,2),2,'Small windows retain sharpness');
for(const file of ['model-viewer.js','live2d-viewer.js'])
    assert.ok(fs.readFileSync('static/js/'+file,'utf8').includes("from './render-budget.js?v=startup68'"));
console.log('PASS: shared 3D/Live2D framebuffer budget, quality ordering and GPU dimension limits');
