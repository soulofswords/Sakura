/* Opt-in accumulated observations. This only schedules comments, never tools. */
export function createInitiative({now=()=>Date.now(),enabled=()=>false}={}){
 let observations=[],lastSpoke=-Infinity;
 return {reset(){observations=[];},consider({reply='',event='',manual=false,busy=false}={}){
  if(manual)return true;
  if(!enabled())return true; // Ordinary reaction settings remain authoritative until opted in.
  const time=now();observations=observations.filter(o=>time-o.time<120000);
  if(busy){observations=[];return false;}
  if(!reply.trim()||reply.trim()==='[QUIET]')return false;
  const key=reply.toLowerCase().replace(/[^\p{L}\p{N}]/gu,'').slice(0,120);
  observations.push({time,key});observations=observations.slice(-12);
  if(time-lastSpoke<90000)return false;
  const notable=['victory','defeat'].includes(event);
  if(!notable&&(observations.length<3||time-observations[0].time<15000))return false;
  lastSpoke=time;observations=[];return true;
 }};
}
export function installInitiativeControls(){
 const host=document.getElementById('tab-general');if(!host)return;
 const key='sakura-initiative-v1';let enabled=false;try{enabled=localStorage.getItem(key)==='true';}catch{}
 const box=document.createElement('fieldset');box.className='setting-group';box.innerHTML='<legend>Proactive screen comments</legend><label><input type="checkbox"> Accumulate observations before commenting</label><p>Optional: wait for several screen observations or a victory/defeat, then allow at most one comment per 90 seconds. Requires screen access and reactions to be on. Your speech and replies take priority. This does not grant tools or file access.</p>';
 const toggle=box.querySelector('input');toggle.checked=enabled;const state=createInitiative({enabled:()=>enabled});toggle.onchange=()=>{enabled=toggle.checked;state.reset();try{localStorage.setItem(key,String(enabled));}catch{}};
 host.append(box);window.sakuraProactive=state;return state;
}
