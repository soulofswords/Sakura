import * as THREE from 'three';
import {MMDLoader} from 'three/addons/loaders/MMDLoader.js';
import {TGALoader} from 'three/addons/loaders/TGALoader.js';
import {DDSLoader} from 'three/addons/loaders/DDSLoader.js';

export function stageAssetUrl(requested,modelPath,origin=location.origin){
 const normalized=requested.replace(/\\/g,'/');
 // MMDLoader's built-in shared toon PNGs are data images, not network URLs.
 if(/^data:image\/png;base64,[a-z0-9+/=]+$/i.test(normalized))return normalized;
 const url=new URL(normalized,origin),parts=modelPath.split('/');
 const importRoot=parts.findIndex((p,i)=>i>0&&/^import-/i.test(p));
 const root=importRoot>=0?parts.slice(0,importRoot+1):['Stages','Tools & Props'].includes(parts[1])?parts.slice(0,3):parts.slice(0,-1);
 const prefix='/models/'+root.map(encodeURIComponent).join('/')+'/';
 const decoded=new URL(decodeURIComponent(url.pathname),origin);
 if(url.origin!==origin||!url.pathname.startsWith(prefix)||!decoded.pathname.startsWith(prefix))throw Error('Texture path leaves this PMX package. Keep shared textures inside the imported asset folder.');
 return url.href;
}
export function prepareStageMesh(mesh){
 mesh.traverse(object=>{
  for(const [name,targets] of Object.entries(object.geometry?.morphAttributes||{}))if(Array.isArray(targets)&&targets.length===0)delete object.geometry.morphAttributes[name];
 });
 return mesh;
}

// Scenery uses the character's actual scene, camera and capture renderer.
// No humanoid retargeting, idle pose or character physics are applied here.
export class PmxStage {
 constructor(viewer){
  this.viewer=viewer;this.records=[];this.meshes=new Map();this.loading=new Set();this.closed=false;
  try{this.enabled=localStorage.getItem('sakura_pmx_stage_enabled')==='true';this.records=JSON.parse(localStorage.getItem('sakura_pmx_stage_items')||'[]').slice(0,4);}catch{this.enabled=false;this.records=[];}
  this.card=document.createElement('section');this.card.className='studio-card';this.card.id='pmx-stage-card';
  this.card.innerHTML=`<h3>3D backgrounds & props</h3><label><input id="pmx-stage-enabled" type="checkbox" style="width:auto"> Enable PMX backgrounds and props alongside my character</label><div id="pmx-stage-options" hidden><label>Import a complete PMX background or prop folder<input id="pmx-stage-import" type="file" webkitdirectory multiple></label><label>Imported PMX assets<select id="pmx-stage-library"></select></label><button id="pmx-stage-refresh" type="button">Refresh assets</button><button id="pmx-stage-add" type="button">Add selected asset to stage</button><label>Stage objects<select id="pmx-stage-selection"></select></label><div id="pmx-stage-transform" hidden><label>Position X<input id="pmx-stage-x" type="number" step="0.5"></label><label>Position Y<input id="pmx-stage-y" type="number" step="0.5"></label><label>Position Z<input id="pmx-stage-z" type="number" step="0.5"></label><label>Scale<input id="pmx-stage-scale" type="number" min="0.01" max="100" step="0.1"></label><label>Rotation Y (degrees)<input id="pmx-stage-rotation" type="number" step="5"></label><button id="pmx-stage-remove" type="button">Remove selected object</button></div></div><p id="pmx-stage-status" role="status">Opt in to load scenery and props. Your character stays selected. Up to four static PMX objects.</p>`;
  this.$=id=>this.card.querySelector('#'+id);this.$('pmx-stage-enabled').checked=this.enabled;
  this.kind='stage';this.folder=[];
  const input=this.$('pmx-stage-import');input.closest('label').firstChild.textContent='Import one complete stage or tool package (with textures)';
  const select=this.$('pmx-stage-library');select.closest('label').firstChild.textContent='Selected local asset';
  const picker=document.createElement('div');picker.innerHTML='<label>Asset library<select id="pmx-stage-kind"><option value="stage">Stages</option><option value="prop">Tools & Props</option></select></label><label>Search this folder<input id="pmx-stage-search" type="search" placeholder="Search stage or tool name"></label><nav id="pmx-stage-folders" aria-label="Asset folders" class="cloud-library-breadcrumb"></nav><div id="pmx-stage-browser" class="cloud-character-grid"></div><div data-scenery-cloud="stage"></div><div data-scenery-cloud="prop" hidden></div>';
  input.closest('label').before(picker);
  this.$('pmx-stage-kind').onchange=e=>{this.kind=e.target.value;this.folder=[];this.$('pmx-stage-search').value='';for(const box of picker.querySelectorAll('[data-scenery-cloud]'))box.hidden=box.dataset.sceneryCloud!==this.kind;void this.library();};
  this.$('pmx-stage-search').oninput=()=>this.browse();
  window.addEventListener('sakura-scenery-installed',event=>{if(!this.closed&&event.detail.kind===this.kind)void this.library();});
  this.$('pmx-stage-enabled').onchange=()=>{this.enabled=this.$('pmx-stage-enabled').checked;this.persist();void this.sync();};
  this.$('pmx-stage-import').onchange=e=>void this.import(e.target);
  this.$('pmx-stage-refresh').onclick=()=>void this.library();
  this.$('pmx-stage-add').onclick=()=>{const s=this.$('pmx-stage-library');if(!s.value)return;if(this.records.length>=4)return this.notice('Remove an object first (limit four).');const r={id:crypto.randomUUID(),path:s.value,name:s.selectedOptions[0].textContent,x:0,y:0,z:-10,scale:1,rotation:0};this.records.push(r);this.selected=r.id;this.persist();void this.sync();};
  this.$('pmx-stage-selection').onchange=e=>{this.selected=e.target.value;this.controls();};
  for(const key of ['x','y','z','scale','rotation'])this.$('pmx-stage-'+key).onchange=e=>{const r=this.records.find(x=>x.id===this.selected);let v=Number(e.target.value);if(!r||!Number.isFinite(v))return;if(key==='scale')v=Math.max(.01,Math.min(100,v));else v=Math.max(-10000,Math.min(10000,v));r[key]=v;this.transform(r);this.persist();};
  this.$('pmx-stage-remove').onclick=()=>{const id=this.selected;this.release(id);this.records=this.records.filter(r=>r.id!==id);this.selected=this.records[0]?.id;this.persist();void this.sync();};
  const mount=()=>{const p=document.body.classList.contains('tracking-only')?document.querySelector('[data-studio-content="background"]'):document.querySelector('[data-companion-content="background"]');if(p&&this.card.parentNode!==p)p.append(this.card);};
  this.observer=new MutationObserver(mount);this.observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});mount();
  window.addEventListener('pagehide',()=>{this.closed=true;this.observer.disconnect();for(const id of this.meshes.keys())this.release(id);},{once:true});
  void this.sync();
 }
 notice(message){this.$('pmx-stage-status').textContent=message;}
 persist(){try{localStorage.setItem('sakura_pmx_stage_enabled',String(this.enabled));localStorage.setItem('sakura_pmx_stage_items',JSON.stringify(this.records));}catch{this.notice('Could not save stage settings.');}}
 async library(){try{const responses=await Promise.all(['stage','prop'].map(kind=>fetch('/api/scenery/assets?kind='+kind)));const data=await Promise.all(responses.map(async response=>{if(!response.ok)throw Error('Cannot read scenery library.');return response.json();}));this.assets=data.flatMap(d=>d.models||[]);this.validPaths=new Set(this.assets.map(m=>m.path));this.browse();}catch(e){this.validPaths=new Set();this.notice(e.message);}}
 browse(){const rows=(this.assets||[]).filter(row=>row.asset_kind===this.kind),query=this.$('pmx-stage-search').value.trim().toLocaleLowerCase();const nav=this.$('pmx-stage-folders'),grid=this.$('pmx-stage-browser'),select=this.$('pmx-stage-library');nav.replaceChildren();grid.replaceChildren();const crumb=(name,path)=>{const b=document.createElement('button');b.type='button';b.textContent=name;b.onclick=()=>{this.folder=path;this.$('pmx-stage-search').value='';this.browse();};nav.append(b);};crumb(this.kind==='stage'?'Stages':'Tools & Props',[]);this.folder.forEach((name,index)=>crumb(name,this.folder.slice(0,index+1)));const within=rows.filter(row=>this.folder.every((name,index)=>row.folders?.[index]===name));if(!query)for(const name of [...new Set(within.map(row=>row.folders?.[this.folder.length]).filter(Boolean))].sort()){const b=document.createElement('button');b.type='button';b.className='cloud-library-folder';b.textContent='📁 '+name;b.style.cssText='white-space:normal;overflow-wrap:anywhere;min-width:0';b.onclick=()=>{this.folder.push(name);this.browse();};grid.append(b);}const visible=within.filter(row=>query?[...(row.folders||[]),row.name].join(' / ').toLocaleLowerCase().includes(query):(row.folders||[]).length===this.folder.length);select.replaceChildren(new Option('Choose one stage or tool',''));for(const row of visible){select.add(new Option(row.name,row.path));const b=document.createElement('button');b.type='button';b.textContent=row.name;b.style.cssText='white-space:normal;overflow-wrap:anywhere;min-width:0';b.onclick=()=>{select.value=row.path;this.notice('Selected '+row.name+'. Click Add selected asset to stage.');};grid.append(b);}if(!grid.childElementCount){const note=document.createElement('p');note.textContent='No assets here yet. Import a package into this dedicated library, or open its cloud library.';grid.append(note);}}
 async import(input){if(!this.enabled)return;input.disabled=true;try{const files=[...input.files];if(!files.length)return;if(!files.some(f=>/\.pmx$/i.test(f.name)))throw Error('Choose one PMX asset folder including textures.');const form=new FormData();form.append('kind',this.kind);for(const f of files)form.append('files',f,f.webkitRelativePath||f.name);const r=await fetch('/api/scenery/import',{method:'POST',body:form}),data=await r.json();if(!r.ok)throw Error(data.error||'Import failed.');await this.library();const path=data.models?.find(p=>/\.pmx$/i.test(p)),row=this.assets.find(m=>m.path===path);if(row){this.folder=row.folders||[];this.browse();this.$('pmx-stage-library').value=path;}this.notice('Imported into '+(this.kind==='stage'?'Stages':'Tools & Props')+'. Click Add selected asset to stage.');}catch(e){this.notice(e.message);}finally{input.disabled=false;input.value='';}}
 async sync(){this.$('pmx-stage-options').hidden=!this.enabled;const s=this.$('pmx-stage-selection');s.replaceChildren(new Option('Choose stage object',''));for(const r of this.records)s.add(new Option(r.name,r.id));this.selected||=this.records[0]?.id;s.value=this.selected||'';this.controls();if(!this.enabled){for(const id of [...this.meshes.keys()])this.release(id);return;}await this.library();await Promise.all(this.records.map(r=>this.load(r)));}
 async load(r){if(this.meshes.has(r.id)||this.loading.has(r.id))return;this.loading.add(r.id);this.notice('Loading '+r.name+'…');let mesh;try{if(typeof r.path!=='string'||!r.path.startsWith('pmx/')||r.path.split('/').some(p=>p==='..')||!r.path.toLowerCase().endsWith('.pmx')||!this.validPaths?.has(r.path))throw Error('PMX asset is missing or invalid. Refresh the library and import a complete valid package.');const manager=new THREE.LoadingManager();manager.addHandler(/\.tga$/i,new TGALoader(manager));manager.addHandler(/\.dds$/i,new DDSLoader(manager));manager.setURLModifier(u=>stageAssetUrl(u,r.path));const url='/models/'+r.path.split('/').map(encodeURIComponent).join('/');mesh=await new MMDLoader(manager).loadAsync(url);if(this.closed||!this.enabled||!this.records.some(x=>x.id===r.id)){this.dispose(mesh);return;}mesh.updateMatrixWorld(true);this.meshes.set(r.id,mesh);this.transform(r);this.viewer.scene.add(mesh);this.notice('Scenery loaded. Use position, scale and rotation to arrange it.');}catch(e){if(mesh)this.dispose(mesh);this.notice(r.name+': '+e.message);}finally{this.loading.delete(r.id);}}
 transform(r){const mesh=this.meshes.get(r.id);if(!mesh)return;prepareStageMesh(mesh);mesh.position.set(r.x,r.y,r.z);mesh.scale.setScalar(r.scale);mesh.rotation.y=r.rotation*Math.PI/180;mesh.updateMatrixWorld(true);}
 controls(){const r=this.records.find(r=>r.id===this.selected);this.$('pmx-stage-transform').hidden=!r;if(r)for(const k of ['x','y','z','scale','rotation'])this.$('pmx-stage-'+k).value=r[k];}
 dispose(mesh){mesh.removeFromParent();const resources=new Set();mesh.traverse(o=>{if(o.geometry)resources.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:o.material?[o.material]:[]){resources.add(m);for(const v of Object.values(m))if(v?.isTexture)resources.add(v);}});for(const r of resources)r.dispose();}
 release(id){const mesh=this.meshes.get(id);if(mesh)this.dispose(mesh);this.meshes.delete(id);}
}
