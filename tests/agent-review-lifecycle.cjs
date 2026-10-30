const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('static/assets/agent.html','utf8');
const start=source.indexOf('function renderRun(run)'),end=source.indexOf('function renderTools()',start);
assert(start>=0&&end>start);
const calls=[];
// A <select> answers to a value and an option list, and losing every option
// resets it to the placeholder. The review dropdown must survive re-renders,
// so the sandbox has to model that instead of swallowing the reads.
class Option { constructor(text, value) { this.text = text; this.value = value; } }
const select = {
    value: '',
    options: [],
    replaceChildren(...items) { this.options = items.slice(); this.value = this.options[0]?.value ?? ''; },
    append(...items) { this.options.push(...items); },
};
const progress = { replaceChildren() {}, append() {} };
const context = { current: null, state: { runs: [] }, $: id => id === 'knowledge-step' ? select : progress,
    node: () => ({ append() {} }), button() {}, renderReview: value => calls.push(value), Option };
vm.createContext(context);vm.runInContext(source.slice(start,end),context);
const run={id:'r',goal:'Write draft',workspace:'test',steps:[{id:'a',tool:'files.write',arguments:{},status:'pending'}]};
context.renderRun(run);assert.equal(calls.at(-1).id,'a');
context.renderRun({...run,steps:[{...run.steps[0],status:'cancelled'}]});assert.equal(calls.at(-1),null);
context.renderRun({...run,steps:[{...run.steps[0],status:'completed'}]});assert.equal(calls.at(-1),null);
assert.deepEqual(select.options.map(option=>option.value),['','a'],'a completed step is offered as an episodic memory source');
select.value='a';context.renderRun({...run,steps:[{...run.steps[0],status:'completed'}]});
assert.equal(select.value,'a','the chosen completed result stays selected across re-renders');
select.value='gone';context.renderRun({...run,steps:[{...run.steps[0],status:'completed'}]});
assert.equal(select.value,'','a result no longer in the run falls back to the placeholder');
context.renderRun(run);context.renderRun(null);assert.equal(calls.at(-1),null);
console.log('PASS: pending Agent review clears on external cancellation, completion and empty selection; the result picker keeps only live completed steps and preserves a still-valid choice.');
