const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync('static/js/model-viewer.js', 'utf8').replace(/\r\n/g, '\n');
const body = source.match(/_indexVrmExpressions\(\) \{([\s\S]*?)\n    \}\n\n    _indexMorphTargets/)[1];
const index = new Function(body);
for (const names of [['aa', 'ih', 'ou', 'ee', 'oh', 'blink'], ['a', 'i', 'u', 'e', 'o', 'blink']]) {
    const viewer = { vrm: { expressionManager: { getExpression: name => names.includes(name) } } };
    index.call(viewer);
    assert.equal(viewer.resolvedVowels.A, names[0]);
    assert.equal(Object.keys(viewer.resolvedVowels).length, 6);
}
const empty = { vrm: { expressionManager: { getExpression: () => null } } };
index.call(empty);
assert.deepEqual(empty.resolvedVowels, {});
console.log('PASS: VRM vowels discovered, legacy names supported, absent expressions skipped');
