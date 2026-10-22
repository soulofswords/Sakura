const fs=require('fs'),assert=require('assert');
const source=fs.readFileSync('static/js/speech-gesture.js','utf8')
  .replace('export function classifySpeechGesture','function classifySpeechGesture')
  .replace('export function speechGestureWeights','function speechGestureWeights');
const {classifySpeechGesture,speechGestureWeights}=new Function(source+';return {classifySpeechGesture,speechGestureWeights};')();
assert.equal(classifySpeechGesture('What do you think?'),'question');
assert.equal(classifySpeechGesture('For example, this is why it works.'),'explain');
assert.equal(classifySpeechGesture("I'm sorry that happened."),'reassure');
assert.equal(classifySpeechGesture("That's amazing!"),'celebrate');
assert.equal(classifySpeechGesture('Hello, I am here.'),'casual');
const start=speechGestureWeights('casual',0,0),stroke=speechGestureWeights('casual',.4,0),end=speechGestureWeights('casual',1,0);
assert.equal(start.stroke,0,'phrase begins with a quiet preparation');
assert(stroke.left>start.left&&stroke.stroke>.9,'gesture rises on the speech stroke');
assert(end.left<stroke.left,'hand retracts at the end of a phrase');
const question=speechGestureWeights('question',.4,0);
assert(question.left>.45&&question.right>.45,'questions use a two-handed open gesture');
const explanation=speechGestureWeights('explain',.4,0);
assert(explanation.left>explanation.right,'explanations emphasize one hand');
const reassurance=speechGestureWeights('reassure',.4,0),casual=speechGestureWeights('casual',.4,0);
assert(reassurance.left<casual.left&&reassurance.right<casual.right,'reassurance stays gentle');
console.log('PASS: semantic co-speech gesture selection, stroke timing, bilateral questions, restrained reassurance');
