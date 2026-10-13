const assert=require('node:assert/strict'),fs=require('node:fs');
const source=fs.readFileSync('static/js/app.js','utf8').replace(/\r\n/g,'\n');
const body=source.match(/function extractWakeCommand\(raw, phrase\) \{([\s\S]*?)\n\}\n\nasync function sendAudioForSTT/)[1];
const extract=new Function('raw','phrase',body);
assert.equal(extract('Hey, Jean! Open Chrome for me.','hey jean'),'Open Chrome for me.');
assert.equal(extract('HEY JEAN','hey jean'),'');
assert.equal(extract('Hey Jeannie open chrome','hey jean'),null);
assert.equal(extract('Something else','hey jean'),null);
console.log('PASS: updated wake phrase, punctuation, separate wake turn, no partial-name match');
