/* Defaults are product-scoped; tracking-only editions never start capture. */
export function installCompanionDefaults({blocked,screen,screenButton,reactionButton,gameButton,status}){
 const key='sakura-companion-defaults-v1';let saved={screen:true,game:true};
 try{saved={...saved,...JSON.parse(localStorage.getItem(key)||'{}')};}catch{}
 window.sakuraCompanionScreenRequested=saved.screen!==false;
 const store=()=>{try{localStorage.setItem(key,JSON.stringify(saved));}catch{}};
 let initialized=false;
 const sync=()=>{
  if(blocked())return;
  reactionButton.hidden=true;
  screenButton.textContent='Screen & reactions';
  screenButton.title=screen.enabled?'Screen capture and reactions are on. Click to turn off.':'Screen capture is off. Click to grant screen access and turn on.';
  screenButton.setAttribute('aria-pressed',String(screen.enabled));
  if(screen.enabled&&reactionButton.getAttribute('aria-pressed')!=='true')reactionButton.click();
 };
 screenButton.addEventListener('click',()=>{if(blocked())return;saved.screen=!screen.enabled;window.sakuraCompanionScreenRequested=saved.screen;store();},{capture:true});
 gameButton.addEventListener('click',()=>{if(blocked())return;saved.game=gameButton.getAttribute('aria-pressed')==='true';store();});
 window.addEventListener('sakura-screen-state',sync);
 async function start(){
  if(initialized||blocked()||window.sakuraCompanionDefaultsReady!==true)return;initialized=true;
  if(saved.game&&gameButton.getAttribute('aria-pressed')!=='true')gameButton.click();
  sync();
  if(saved.screen&&!screen.enabled){
   if(window.pywebview?.api?.set_screen_access){try{await screen.toggle();}catch(error){status.textContent='Screen capture unavailable: '+error.message;}sync();}
   else status.textContent='Screen & reactions are ready. Click Turn on to choose a screen and grant capture access.';
  }
 }
 window.addEventListener('pywebviewready',start);
 window.addEventListener('sakura-companion-ready',start);void start();
 return {sync};
}
