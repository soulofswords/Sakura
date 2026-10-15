const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element extends EventTarget{
 constructor(){super();this.children=[];this.value='';}
 append(...elements){this.children.push(...elements);}
 setAttribute(){}setPointerCapture(){}
 getBoundingClientRect(){return {left:0,top:0,width:240,height:240};}
 getContext(){return new Proxy({createLinearGradient:()=>({addColorStop(){}})},{get:(target,key)=>target[key]||(()=>{})});}
}
const ctx={Event,document:{createElement:()=>new Element()}};
vm.runInNewContext(fs.readFileSync('static/js/color-dial.js','utf8').replace('export function','function')+'\nthis.install=installColorDial',ctx);
const input=new Element(),host=new Element();input.value='#ff0000';let updates=0,selected;
input.addEventListener('input',()=>{updates++;selected=input.value;});ctx.install(input,host);
assert.equal(updates,0,'Initialization does not save a different color');
host.children[0].onpointerdown({clientX:224,clientY:120,pointerId:1});
assert.equal(updates,1);assert.notEqual(selected,'#ff0000','Hue drag publishes selected color');
const fields=host.children[1].children.map(label=>label.children[0]);
fields[0].value=12;fields[1].value=34;fields[2].value=56;fields[0].oninput();
assert.equal(updates,2);assert.equal(selected,'#0c2238','RGB edits publish selected color');
const css=fs.readFileSync('static/css/style.css','utf8');
assert.ok(css.includes('body.native-library:not(.transparent-mode) { background: radial-gradient'));
console.log('PASS: wheel and RGB changes emit input without recursion; native background uses theme and preserves transparency');
