export function installLiveChatControls(){
 for(const [prefix,linkId] of [['reader','reader-chat-link'],['cohost','youtube-chat-link']]){
  const service=document.getElementById(prefix+'-service'),link=document.getElementById(linkId),setup=document.getElementById(prefix+'-twitch-setup');
  if(!service||!link||!setup)continue;
  const extra=document.getElementById(prefix+'-twitch-link-group');
  const show=()=>{const both=service.value==='both',twitch=service.value==='twitch'||both;setup.hidden=!twitch;setup.open=twitch;if(extra)extra.hidden=!both;link.placeholder=service.value==='twitch'?'https://www.twitch.tv/channel':'https://www.youtube.com/watch?v=…';link.setAttribute('aria-label',both?'YouTube livestream link':'Livestream link');};
  service.addEventListener('change',show);
  link.addEventListener('input',()=>{if(service.value==='both')return;try{const host=new URL(link.value).hostname;if(['twitch.tv','www.twitch.tv'].includes(host))service.value='twitch';else if(['youtube.com','www.youtube.com','youtu.be'].includes(host))service.value='youtube';show();}catch{}});show();
 }
}
