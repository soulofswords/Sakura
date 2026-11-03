export function installVrmSpringControls(viewer,getModel){
 const host=document.getElementById('physics-strength')?.closest('.setting-group');if(!host)return;
 const box=document.createElement('fieldset');box.className='setting-group';box.hidden=true;const title=document.createElement('legend');title.textContent='VRM spring bones';box.append(title);host.after(box);
 const controls={};
 for(const [name,text]of [['stiffness','Stiffness'],['gravity','Gravity'],['drag','Damping']]){const label=document.createElement('label'),output=document.createElement('output'),input=document.createElement('input');input.type='range';input.min='0';input.max='200';input.value='100';input.id='vrm-spring-'+name;label.htmlFor=input.id;label.append(text+': ',output);box.append(label,input);controls[name]={input,output};input.oninput=()=>apply(true);}
 const reset=document.createElement('button');reset.type='button';reset.textContent='Restore authored springs';reset.onclick=()=>{for(const c of Object.values(controls))c.input.value='100';apply(true);};box.append(reset);
 function apply(save){const values={};for(const [name,c]of Object.entries(controls)){values[name]=Number(c.input.value)/100;c.output.textContent=c.input.value+'%';}viewer.setVrmSpringTuning(values);if(save)try{localStorage.setItem('sakura-vrm-springs:'+getModel(),JSON.stringify(values));}catch{}}
 function refresh(){box.hidden=!viewer.vrm;if(!viewer.vrm){viewer.vrmSpringTuning=null;return;}let values={};try{values=JSON.parse(localStorage.getItem('sakura-vrm-springs:'+getModel())||'{}');}catch{}for(const [name,c]of Object.entries(controls))c.input.value=String(Math.round((typeof values[name]==='number'&&Number.isFinite(values[name])?Math.min(2,Math.max(0,values[name])):1)*100));apply(false);}
 window.addEventListener('sakura-character-loaded',refresh);refresh();
}
