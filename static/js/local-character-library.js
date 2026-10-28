/* Folder-based visual browser. Existing format selectors own selection/loading. */
const formats={pmx:['model-dropdown','model-select'],vrm:['vrm-dropdown','vrm-select'],live2d:['live2d-dropdown','live2d-select']};
const pictures=new Map();
let folderNames={};
const folderLabel=(name,depth)=>depth===0?(folderNames[format+'/'+name]||name):name;
let dialog,format='',folder=[],preview,ready=false,busy='',current='',queue=[],hover=null,timer;
function send(message){preview?.contentWindow?.postMessage(message,location.origin);}
function park(){send({type:'rotate',enabled:false});if(preview)preview.style.cssText='position:fixed;left:-10000px;top:0;width:256px;height:256px;pointer-events:none';}
function showRotation(square){
 const rect=square.getBoundingClientRect();
 preview.style.cssText=`position:fixed;left:${rect.left}px;top:${rect.top}px;width:${rect.width}px;height:${rect.height}px;pointer-events:none;border-radius:7px;z-index:5`;
 send({type:'rotate',enabled:true});
}
function pump(){
 if(!ready||busy||!queue.length||!dialog.open||hover)return;
 const item=queue.shift();busy=item.path;send({type:'load',path:item.path});
 clearTimeout(timer);timer=setTimeout(()=>{busy='';pump();},30000);
}
function entries(){
 const select=document.getElementById(formats[format][1]);
 return Array.from(select?.options||[]).filter(o=>o.value&&!o.disabled).map(option=>{
  const path=option.value.replaceAll('\\','/').replace(/^\/models\//,'');
  const parts=path.split('/');if(parts[0].toLowerCase()===format)parts.shift();
  return {path,option,select,parts,name:format==='live2d'?(parts.length===2?folderLabel(parts[0],0):(parts.at(-2)||option.textContent)):option.textContent};
 });
}
async function open(kind){
 format=kind;folder=[];
 if(!dialog){
  dialog=document.createElement('dialog');dialog.id='local-character-library';
  dialog.innerHTML=`<header><h2 data-local-title></h2><button type="button" data-local-close aria-label="Close character library">×</button></header>
  <input type="search" data-local-search aria-label="Search local characters" placeholder="Search all folders by character name…">
  <nav data-local-path aria-label="Model folders"></nav><div data-local-grid></div><p data-local-status role="status"></p><div data-local-renderer></div>`;
  const style=document.createElement('style');style.textContent=`
  #local-character-library{width:min(820px,92vw);height:min(760px,88vh);box-sizing:border-box;border:1px solid var(--ui-line,#56616c);border-radius:16px;padding:20px;background:var(--ui-card,#202830);color:var(--ui-ink,#edf5fc)}
  #local-character-library::backdrop{background:#0008}
  #local-character-library header{display:flex;align-items:center;justify-content:space-between}#local-character-library h2{margin:0 0 16px}
  #local-character-library [data-local-search]{width:100%;box-sizing:border-box;margin-bottom:12px;padding:10px}
  #local-character-library [data-local-path]{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
  #local-character-library [data-local-grid]{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px;align-content:start}
  #local-character-library [data-local-grid]>button{min-width:0;padding:8px;border:1px solid var(--ui-line,#586675);border-radius:10px;background:var(--ui-button,#303c49);color:inherit;cursor:pointer;text-align:center}
  #local-character-library [data-local-grid]>button:focus-visible{outline:2px solid #55baff}
  #local-character-library .local-character-square{display:grid;place-items:center;width:100%;aspect-ratio:1;overflow:hidden;border-radius:7px;background:#8796a71a;overflow-wrap:anywhere}
  #local-character-library img,#local-character-library iframe{width:100%;height:100%;object-fit:contain;border:0}
  #local-character-library iframe{pointer-events:none}
  #local-character-library .local-character-name{display:block;overflow-wrap:anywhere;margin-top:7px}
  #local-character-library [data-local-renderer]{position:fixed;left:-10000px;top:0;width:256px;height:256px;pointer-events:none}
  #local-character-library [data-local-status]{font-size:.85rem;opacity:.8}`;
  document.head.append(style);document.body.append(dialog);
  dialog.querySelector('[data-local-close]').onclick=()=>dialog.close();
  dialog.querySelector('[data-local-search]').oninput=render;
  dialog.addEventListener('close',()=>{park();preview?.remove();preview=null;ready=false;busy='';queue=[];hover=null;clearTimeout(timer);});
 }
 dialog.querySelector('[data-local-title]').textContent=(format==='live2d'?'Live2D':format.toUpperCase())+' characters';
 dialog.querySelector('[data-local-search]').value='';
 try{const response=await fetch('/api/local-model-library/folder-names');if(response.ok)folderNames=(await response.json()).names||{};}catch{}
 dialog.showModal();render();
}
function renderer(){
 if(preview||format==='live2d')return;
 preview=document.createElement('iframe');preview.title='Rotating character preview';preview.src='/static/model-library-preview.html';
 dialog.querySelector('[data-local-renderer]').append(preview);
 park();
}
function render(){
 park();hover=null;queue=[];
 const q=dialog.querySelector('[data-local-search]').value.trim().toLocaleLowerCase(),grid=dialog.querySelector('[data-local-grid]'),nav=dialog.querySelector('[data-local-path]');
 grid.replaceChildren();nav.replaceChildren();
 const crumb=(name,depth)=>{const button=document.createElement('button');button.type='button';button.textContent=name;button.onclick=()=>{folder=folder.slice(0,depth);dialog.querySelector('[data-local-search]').value='';render();};nav.append(button);};
 crumb(format==='live2d'?'Live2D':format.toUpperCase(),0);folder.forEach((name,index)=>crumb(folderLabel(name,index),index+1));
 const all=entries(),matches=all.filter(item=>q?(item.name+' '+item.path+' '+folderLabel(item.parts[0],0)).toLocaleLowerCase().includes(q):folder.every((name,index)=>item.parts[index]===name));
 const folders=q?[]:[...new Set(matches.filter(item=>item.parts.length>folder.length+1).map(item=>item.parts[folder.length]))].sort((a,b)=>a.localeCompare(b));
 const card=(title,label)=>{const button=document.createElement('button');button.type='button';button.setAttribute('aria-label',label);const square=document.createElement('span');square.className='local-character-square';square.textContent=title;const name=document.createElement('span');name.className='local-character-name';name.textContent=title;button.append(square,name);grid.append(button);return {button,square};};
 for(const name of folders){const label=folderLabel(name,folder.length);const {button,square}=card(label,'Open folder '+label);square.textContent='📁';button.onclick=()=>{folder.push(name);render();};}
 const files=matches.filter(item=>q||item.parts.length===folder.length+1);
 for(const item of files.slice(0,60)){
  const {button,square}=card(item.name,(format==='live2d'?'Live2D':format.toUpperCase())+' · '+item.name);
  square.dataset.localModel=item.path;
  const setImage=url=>{square.textContent='';const image=document.createElement('img');image.alt=item.name;image.src=url;image.onerror=()=>{image.remove();square.textContent=item.name;};square.append(image);};
  if(format==='live2d')setImage('/api/local-model-library/preview?model='+encodeURIComponent(item.path));
  else if(pictures.has(item.path))setImage(pictures.get(item.path));
  else queue.push(item);
  button.onclick=()=>{item.select.value=item.option.value;item.select.dispatchEvent(new Event('change',{bubbles:true}));dialog.close();};
  if(format!=='live2d'){
   button.onpointerenter=()=>{
    hover={path:item.path,square};
    if(!ready)return;
    if(current===item.path&&!busy){showRotation(square);}
    else if(!busy){busy=item.path;send({type:'load',path:item.path});}
   };
   button.onpointerleave=()=>{hover=null;park();pump();};
  }
 }
 dialog.querySelector('[data-local-status]').textContent=files.length>60?'Showing the first 60 matches. Narrow your search.':
  folders.length||files.length?'Choose a folder or character. Hover a 3D preview to rotate it.':'No matching characters in this folder.';
 renderer();pump();
}
addEventListener('message',event=>{
 if(!dialog?.open||event.origin!==location.origin||event.source!==preview?.contentWindow)return;
 if(event.data?.type==='preview-ready'){
  ready=true;
  if(hover){busy=hover.path;send({type:'load',path:busy});}else pump();
  return;
 }
 if(event.data?.type!=='model-preview'||event.data.path!==busy)return;
 clearTimeout(timer);current=busy;busy='';
 if(typeof event.data.image==='string'&&event.data.image.startsWith('data:image/png;base64,')){
  pictures.set(current,event.data.image);
  for(const square of dialog.querySelectorAll('[data-local-model]'))if(square.dataset.localModel===current){
   square.textContent='';const image=document.createElement('img');image.alt=current;image.src=event.data.image;square.append(image);
  }
 }
 if(hover){
  if(hover.path===current){showRotation(hover.square);}
  else{busy=hover.path;send({type:'load',path:busy});}
 }else pump();
});
document.addEventListener('click',event=>{
 const trigger=event.target.closest?.('.dropdown-trigger');if(!trigger)return;
 const kind=Object.keys(formats).find(key=>trigger.closest('#'+formats[key][0]));if(!kind)return;
 event.preventDefault();event.stopImmediatePropagation();open(kind);
},true);
