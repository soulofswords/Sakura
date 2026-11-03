/* Character presentation is selected by the user, never guessed from an image. */
export function installCharacterVoice({getModel,applyVoice,getVoice,blocked}){
 const label=document.createElement('label');label.textContent='Voice for this character';const select=document.createElement('select');select.id='character-voice-profile';
 for(const [value,text]of [['keep','Keep my selected voice'],['soft','Female · soft / Heart'],['bold','Male · deeper / Michael']])select.append(new Option(text,value));
 label.append(select);document.getElementById('voice-preset-grid')?.before(label);
 const hint=document.createElement('p');hint.textContent='Saved separately for each character. Choose once; switching back restores its voice style. Hindi/Hinglish and custom RVC selections stay in your chosen language.';label.after(hint);
 let model='';
 const key=path=>'sakura-character-voice:'+path;
 async function update(){
  model=getModel()||'';if(!model)return;
  let choice='keep';try{choice=localStorage.getItem(key(model))||'keep';}catch{}
  select.value=['keep','soft','bold'].includes(choice)?choice:'keep';
  const voice=getVoice()||'';
  if(blocked()||/hindi|hinglish|^rvc_|^system_/.test(voice))return;
  if(select.value!=='keep')await applyVoice(select.value==='soft'?'kokoro_af_heart':'kokoro_am_michael');
 }
 select.onchange=async()=>{if(!model)model=getModel()||'';if(!model)return;try{localStorage.setItem(key(model),select.value);}catch{}await update();};
 window.addEventListener('sakura-character-loaded',()=>void update());void update();
}
