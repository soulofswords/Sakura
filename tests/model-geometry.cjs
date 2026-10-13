const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('static/js/model-viewer.js', 'utf8').replace(/\r\n/g, '\n');
const body = source.match(/_sanitizeGeometry\(root\) \{([\s\S]*?)\n    \}\n\n    async loadModel/)[1];
const sanitize = new Function('root', body);
function attribute(values, stride) {
    return {
        count: values.length / stride,
        getX: i => values[i * stride],
        getY: i => values[i * stride + 1],
        getZ: i => values[i * stride + 2],
        setX: (i, x) => { values[i * stride] = x; },
        setXYZ: (i, x, y, z) => { values.splice(i * stride, 3, x, y, z); },
    };
}
const vertices = [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, -1e38];
const triangles = [0, 1, 2, 0, 1, 3];
const morphValues = vertices.slice();
let boxes = 0, spheres = 0;
const geometry = {
    attributes: { position: attribute(vertices, 3) },
    index: attribute(triangles, 1),
    morphAttributes: { position: [attribute(morphValues, 3)] },
    computeBoundingBox: () => { boxes++; },
    computeBoundingSphere: () => { spheres++; },
};
sanitize({ traverse: callback => callback({ geometry }) });
assert.deepEqual(triangles, [0, 1, 2, 0, 0, 0]);
assert.deepEqual(vertices.slice(0, 9), [0, 0, 0, 1, 0, 0, 0, 1, 0]);
assert.deepEqual(vertices.slice(9), [0, 0, 0]);
assert.deepEqual(morphValues.slice(9), [0, 0, 0]);
assert.equal(boxes, 1);
assert.equal(spheres, 1);
assert.equal(geometry.index.count, 6);
console.log('PASS: invalid vertex and morph removed, valid triangle and material offsets preserved');

// A finite outlier below the old absolute cutoff must not pull the camera away.
const finiteVertices = [0, 0, 0, 1, 0, 0, 0, 1, 0, 9000, 4000, -2000];
const finiteTriangles = [0, 1, 2, 0, 1, 3];
const finiteGeometry = {
    attributes: { position: attribute(finiteVertices, 3) },
    index: attribute(finiteTriangles, 1), morphAttributes: {},
    computeBoundingBox() {}, computeBoundingSphere() {},
};
const mesh = {geometry: finiteGeometry, boundingBox: {}, boundingSphere: {}};
const outcome = sanitize({traverse: callback => callback(mesh)});
assert.equal(outcome.invalidVertices, 1);
assert.deepEqual(finiteTriangles, [0, 1, 2, 0, 0, 0]);
assert.equal(mesh.boundingBox, null);
assert.equal(mesh.boundingSphere, null);
console.log('PASS: finite scale outlier removed and cached skinned bounds invalidated');
