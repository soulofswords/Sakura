const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const parserSource = fs.readFileSync('static/vendor/three/examples/jsm/libs/mmdparser.module.js', 'utf8')
    .replace('export { MMDParser, CharsetEncoder, Parser };', 'globalThis.ModelParser = Parser;');
const context = vm.createContext({console, TextDecoder});
vm.runInContext(parserSource, context);
function walk(folder) {
    return fs.readdirSync(folder, {withFileTypes:true}).flatMap(item => {
        const file = path.join(folder,item.name);
        return item.isDirectory() ? walk(file) : /\.pmx$/i.test(file) ? [file] : [];
    });
}
(async () => {
    const report = [];
    for (const file of walk('models')) {
        try {
            const bytes = fs.readFileSync(file);
            const model = new context.ModelParser().parsePmx(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset+bytes.byteLength), true);
            const missing = [], invalidTextures = [], texturePaths = [];
            for (const texture of model.textures) {
                const relative = path.relative('models',path.join(path.dirname(file),texture.replace(/\\/g,'/'))).replace(/\\/g,'/');
                texturePaths.push(relative);
            }
            const badVertices = model.vertices.filter(v => v.position.some(n=>!Number.isFinite(n)||Math.abs(n)>10000)).length;
            const badFaces = model.faces.filter(f=>f.indices.some(i=>i<0||i>=model.vertices.length)).length;
            report.push({file,vertices:model.vertices.length,triangles:model.faces.length,bones:model.bones.length,
                morphs:model.morphs.map(m=>m.name),textures:model.textures.length,texturePaths,missing,invalidTextures,badVertices,badFaces});
        } catch(error) { report.push({file,error:error.message}); }
    }
    fs.writeFileSync('models/model-audit.json',JSON.stringify(report,null,2));
    for (const item of report) console.log(JSON.stringify({...item,texturePaths:undefined,morphs:item.morphs?.filter(name=>/あ|い|う|え|お|まばたき|blink|mouth|jaw/i.test(name))}));
})();
