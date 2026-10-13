const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/app.js','utf8');
const code=source.slice(source.indexOf('let pmxFolderPath = []'),source.indexOf('function syncCustomDropdown('));
function element(){return {children:[],classList:{add(){},remove(){}},appendChild(x){this.children.push(x)},replaceChildren(){this.children=[]},addEventListener(_,fn){this.click=()=>fn({stopPropagation(){}})}};}
const menu=element();let changed=0;
const select={value:'',dispatchEvent(){changed++}};
const ctx={document:{querySelector:()=>menu,getElementById:()=>element(),createElement:element},Event:class{},selectedPmxPath:'',allPmxModels:[
{path:'pmx/pmx/zenless zone zero/Evelyn/model.pmx',filename:'model.pmx',folders:['zenless zone zero','Evelyn']},
{path:'pmx/pmx/anime/Esdeath/model.pmx',filename:'model.pmx',folders:['anime','Esdeath']}]};
vm.createContext(ctx);vm.runInContext(code,ctx);ctx.renderPmxFolders(select);
menu.children.find(x=>x.textContent.includes('zenless')).click();
menu.children.find(x=>x.textContent.includes('Evelyn')).click();
menu.children.find(x=>x.textContent==='model.pmx').click();
assert.equal(select.value,'pmx/pmx/zenless zone zero/Evelyn/model.pmx');assert.equal(changed,1);
menu.children.find(x=>x.textContent==='← Back').click();
assert.ok(menu.children.some(x=>x.textContent.includes('Evelyn')));
console.log('PASS: category → character → PMX selection and Back navigation');
