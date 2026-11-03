window.installAgentExtensions=({api,perform,refresh,renderRun,selectRun,currentRun,planner,token,node,button})=>{
 const $=id=>document.getElementById(id);
 function field(parent,title,id,tag='input',type='text'){const label=node('label',title),input=node(tag);input.id=id;if(tag==='input')input.type=type;label.append(input);parent.append(label);return input;}
 function details(parent,title){const box=node('details');box.append(node('summary',title));parent.append(box);return box;}
 function requireRun(){const run=currentRun();if(!run)throw Error('Create or select a task first.');return run;}
 async function proposal(tool,args){const run=requireRun();const result=await api('tasks/'+run.id+'/propose',{tool,arguments:args});selectRun(result.id);renderRun(result);await refresh();}
 const advanced=$('agent-tool-proposal');
 const shell=details(advanced,'Terminal backends · Local / Docker / SSH cloud host');
 shell.append(node('p','Docker needs an installed image by sha256 digest and a local daemon. SSH needs an existing POSIX host, keys and verified known_hosts. Nothing is provisioned. Do not put passwords or tokens in commands; task history stores the text.'));
 const backend=field(shell,'Execution backend','execution-backend','select');for(const [id,label] of [['local','Local PowerShell'],['docker','Local Docker sandbox'],['ssh','SSH / existing cloud host']])backend.append(new Option(label,id));
 const command=field(shell,'Exact command','execution-command','textarea');command.maxLength=12000;
 const cwd=field(shell,'Local working directory (blank = task workspace)','execution-cwd');
 const docker=node('div');shell.append(docker);const image=field(docker,'Installed image digest (sha256:…)','execution-image');
 const writable=field(docker,'Allow this command to write the mounted workspace','execution-writable','input','checkbox');writable.style.width='auto';
 const ssh=node('div');shell.append(ssh);const host=field(ssh,'SSH hostname or IPv4 address','execution-host'),user=field(ssh,'SSH user','execution-user'),remote=field(ssh,'Remote POSIX directory','execution-remote');
 backend.onchange=()=>{docker.hidden=backend.value!=='docker';ssh.hidden=backend.value!=='ssh';};backend.onchange();
 shell.append(button('Review terminal command',async()=>{const args={command:command.value,backend:backend.value};if(cwd.value.trim())args.cwd=cwd.value.trim();if(backend.value==='docker')Object.assign(args,{image:image.value.trim(),writable:writable.checked});if(backend.value==='ssh')Object.assign(args,{host:host.value.trim(),user:user.value.trim(),remote_cwd:remote.value.trim()});await proposal('shell.run',args);}));
 const delegate=details(advanced,'Parallel child tasks');delegate.append(node('p','Enter 2–4 independent goals, one per line. Workers have separate task histories and share only the selected workspace and AI choice. Only workspace reads auto-run; changes pause for per-child approval. The model server may queue inference.'));
 const goals=field(delegate,'Independent goals','delegate-goals','textarea');
 async function delegateGoals(values){const run=requireRun();const result=await api('tasks/'+run.id+'/delegate',{goals:values,...planner()});selectRun(result.id);renderRun(result);await refresh();}
 delegate.append(button('Review parallel delegation',()=>delegateGoals(goals.value.split('\n').map(value=>value.trim()).filter(Boolean))));
 const browser=details(advanced,'Isolated browser tools');browser.append(node('p','Headless Edge/Chrome with fresh cookies, public websites only, no downloads or personal browser profile. Review each navigation and interaction. Use the numbered elements and snapshot from the last result with browser.click or browser.fill in the exact tool form.'));
 const url=field(browser,'Public page URL','browser-url');
 browser.append(button('Review opening page',()=>proposal('browser.open',{url:url.value.trim()})),button('Review reading page',()=>proposal('browser.read',{})),button('Review closing browser',()=>proposal('browser.close',{})));
 const imports=details($('agent-skills'),'Import procedures or archived sessions');imports.append(node('p','Choose SKILL.md with name frontmatter, a JSON {skills:[{name,instructions}]} export, or Sakura {runs:[...]} history. Review before importing. Executable plugins, configuration, credentials and approvals are excluded.'));
 const imported=field(imports,'Import file','agent-import-file','input','file');imported.accept='.md,.json';const preview=node('div');imports.append(preview);
 imported.onchange=()=>perform(async()=>{const file=imported.files?.[0];if(!file)return;try{if(file.size>1000000)throw Error('Import files must be under 1 MB.');const data=await api('imports/preview',{filename:file.name,text:await file.text()});preview.replaceChildren(node('p',data.warning),node('pre',JSON.stringify(data.items,null,2)),button('Approve this import',async()=>{const result=await api('imports/'+data.id+'/confirm',{approved:true});preview.replaceChildren(node('p','Imported '+result.imported+' '+result.kind+'.'));await refresh();}));}finally{imported.value='';}});
 const voice=details($('agent-compose'),'Transcribe a voice memo');voice.append(node('p','OGG/Opus, WAV or WebM, at most 4 MB and two minutes. Uses the already-loaded local speech recognizer and ffmpeg, never the microphone. The transcript is placed in Goal for review, not executed.'));
 const memo=field(voice,'Voice memo','agent-voice-file','input','file');memo.accept='.ogg,.oga,.opus,.wav,.webm';
 memo.onchange=()=>perform(async()=>{const file=memo.files?.[0];if(!file)return;try{if(file.size>4*1024*1024)throw Error('Voice memos must be under 4 MB.');const response=await fetch('/api/agent/voice/transcribe',{method:'POST',headers:{'X-Sakura-Agent':token,'Content-Type':'application/octet-stream'},body:file});const data=await response.json();if(!response.ok)throw Error(data.detail||'Transcription failed.');$('goal').value=data.text;}finally{memo.value='';}});
 const gateways=node('section',undefined,'card');gateways.id='agent-other-gateways';$('agent-telegram').append(gateways);gateways.append(node('h2','Discord, Slack and WhatsApp'));
 gateways.append(node('p','Each gateway gives independent AI replies only. No desktop tools, memory or approvals. Configure your own provider app; enabling authorizes replies to the exact allowed users. Credentials stay in protected local storage.'));
 const provider=field(gateways,'Messaging provider','gateway-provider','select');for(const name of ['discord','slack','whatsapp'])provider.append(new Option(name,name));
 const guidance=node('p');gateways.append(guidance);const gatewayStatus=node('p');gatewayStatus.id='gateway-status';gateways.append(gatewayStatus);
 const channels=field(gateways,'Allowed channel IDs (comma separated)','gateway-channels'),users=field(gateways,'Allowed user IDs / WhatsApp sender numbers (comma separated)','gateway-users');
 const phone=field(gateways,'WhatsApp phone-number ID','gateway-phone'),secret=field(gateways,'Bot / access token (blank keeps saved value)','gateway-token','input','password');secret.autocomplete='off';
 const appSecret=field(gateways,'WhatsApp app secret','gateway-app-secret','input','password'),verifyToken=field(gateways,'WhatsApp webhook verify token','gateway-verify-token','input','password');appSecret.autocomplete=verifyToken.autocomplete='off';
 const enabled=field(gateways,'Enable replies while Sakura is open','gateway-enabled','input','checkbox');enabled.style.width='auto';
 const explanations={discord:'Discord: invite your bot to the selected channels, grant View Channel / Read Message History / Send Messages, and enable Message Content intent if required. Checks every 5 seconds. Existing messages are skipped on startup.',slack:'Slack: install your app with chat:write plus history scopes for the selected channels, then invite the bot. Bot token required. One channel is checked each minute; existing messages are skipped on startup. Provider rate limits still apply.',whatsapp:'WhatsApp Business Cloud API: use a registered phone-number ID, access token, app secret and your own webhook verify token. Configure a public HTTPS reverse proxy for ONLY /api/messaging/whatsapp/webhook, forwarding to this local app. Sakura does not create a tunnel or expose the desktop API. Incoming deliveries require Meta signatures; replies may incur provider charges.'};
 async function loadGateway(){const all=await api('gateways');const item=all.find(item=>item.provider===provider.value);guidance.textContent=explanations[provider.value];const wa=provider.value==='whatsapp';for(const input of [phone,appSecret,verifyToken])input.parentElement.hidden=!wa;channels.parentElement.hidden=wa;secret.value=appSecret.value=verifyToken.value='';channels.value=item.channels.join(', ');users.value=item.users.join(', ');phone.value=item.phone_id;enabled.checked=item.enabled;gatewayStatus.textContent=(item.running?'Gateway running. ':'Gateway stopped. ')+(item.token_set?'Token saved. ':'No token saved. ')+(item.last_error||'');}
 provider.onchange=()=>perform(loadGateway);
 gateways.append(button('Load saved gateway settings',loadGateway),button('Save gateway',async()=>{const payload={enabled:enabled.checked,channels:provider.value==='whatsapp'?[]:channels.value.replaceAll(',',' ').split(/\s+/).filter(Boolean),users:users.value.replaceAll(',',' ').split(/\s+/).filter(Boolean),phone_id:phone.value,token:secret.value,app_secret:appSecret.value,verify_token:verifyToken.value};secret.value=appSecret.value=verifyToken.value='';await api('gateways/'+provider.value,payload);await loadGateway();}),button('Disable and remove gateway secrets',async()=>{if(!window.confirm('Disable this gateway and remove its saved credentials?'))return;await api('gateways/'+provider.value,{enabled:false,clear_token:true});await loadGateway();}));
 guidance.textContent=explanations.discord;for(const input of [phone,appSecret,verifyToken])input.parentElement.hidden=true;gatewayStatus.textContent='Load saved settings before editing an existing gateway.';
 const help=node('p','Slash commands: /help, /new, /status, /cancel, /plan, /search keywords, /model provider-id, /skill name task, /delegate goal one | goal two.');$('agent-compose').append(help);
 return {async slash(text){
  if(!text.trim().startsWith('/'))return false;
  const match=text.trim().match(/^\/(\S+)(?:\s+([\s\S]*))?$/),name=match?.[1],argument=match?.[2]||'';
  if(['brag','learn'].includes(name))return false;
  if(name==='help'){$('progress').replaceChildren(node('p',help.textContent));return true;}
  if(name==='new'){selectRun(null);renderRun(null);$('goal').value=argument;return true;}
  if(name==='status'){renderRun(await api('tasks/'+requireRun().id));return true;}
  if(name==='cancel'){renderRun(await api('tasks/'+requireRun().id+'/cancel',{}));await refresh();return true;}
  if(name==='plan'){renderRun(await api('tasks/'+requireRun().id+'/plan',planner()));await refresh();return true;}
  if(name==='search'){$('history-query').value=argument;document.querySelector('#agent-studio-nav button[aria-label="Task history"]')?.dispatchEvent(new Event('click'));await window.searchAgentHistory(argument);return true;}
  if(name==='model'){const option=[...$('planner-provider').options].find(option=>option.value===argument&&!option.disabled);if(!option)throw Error('Choose an available provider ID from Planning AI.');$('planner-provider').value=argument;$('planner-provider').dispatchEvent(new Event('change'));return true;}
  if(name==='skill'){const [skill,...rest]=argument.split(/\s+/);const option=[...$('selected-skill').options].find(item=>item.value===skill);if(!option)throw Error('Choose an installed skill.');option.selected=true;$('goal').value=rest.join(' ');return false;}
  if(name==='delegate'){await delegateGoals(argument.split('|').map(value=>value.trim()).filter(Boolean));return true;}
  throw Error('Unknown slash command. Use /help.');
 }};
};
