/* Presentation shell: all tools continue through the authenticated Agent API. */
window.installAgentStudio=({newTask=()=>{},api,perform}={})=>{
 if(document.getElementById('agent-studio-nav'))return;
 const $=id=>document.getElementById(id),main=document.querySelector('main'),tabs=$('agent-workspace-tabs');
 const nav=document.createElement('nav');nav.id='agent-studio-nav';nav.setAttribute('aria-label','Agent studio');
 const brand=document.createElement('div');brand.className='agent-nav-brand';brand.textContent='✿';brand.setAttribute('aria-hidden','true');nav.append(brand);
 const heading=document.createElement('p');heading.id='agent-view-heading';$('status').after(heading);
 const dock=document.createElement('div');dock.id='agent-review-dock';dock.hidden=true;document.querySelector('.grid').before(dock);
 const review=$('review');dock.append(review);
 const panels={tasks:[$('agent-compose'),$('agent-task-progress'),$('agent-tool-proposal')],local:[$('agent-local-ai')],automations:[$('agent-automations')],connections:[$('service-connections'),$('agent-integrations'),$('connected-calendar-schedule'),$('agent-telegram')],skills:[$('agent-skills')],memory:[$('agent-memory')],history:[$('agent-history'),$('agent-metrics')]};
 const compose=$('agent-compose'),progress=$('agent-task-progress');
 const options=document.createElement('details');options.id='agent-task-options';options.innerHTML='<summary>Task settings <span>Workspace, model & skills</span></summary>';
 const goalLabel=$('goal').closest('label'),actions=$('create').closest('.row');
 for(const child of [...compose.children])if(child!==goalLabel&&child!==actions&&child.tagName!=='H2')options.append(child);
 compose.insertBefore(options,actions);compose.querySelector('h2').textContent='Message Sakura';
 $('goal').placeholder='What would you like to work on?';$('goal').setAttribute('aria-label','Message Sakura');
 $('create').textContent='Send';$('create').title='Create a task and start planning';
 const notice=options.querySelector('.notice');if(notice)notice.textContent='Tools follow the approval mode selected below. Commands and MCP processes run with your Windows permissions; the workspace is not a sandbox. Cloud AI receives the results it reads. Broad access requires Windows confirmation and resets when Sakura restarts.';
 const controls=document.createElement('div');controls.className='agent-task-controls';
 for(const id of ['plan','pause','resume','cancel'])controls.append($(id));
 progress.insertBefore(controls,$('progress'));main.prepend(progress);
 const advanced=document.createElement('details');advanced.id='agent-advanced-tools';advanced.innerHTML='<summary>Tools & command permissions</summary>';
 $('agent-tool-proposal').before(advanced);advanced.append($('agent-tool-proposal'));panels.tasks.push(advanced);
 const menu=document.createElement('details');menu.id='agent-access-menu';menu.innerHTML='<summary id="agent-access-label">Ask for approval</summary><div class="agent-access-options"><strong>How should Sakura actions be approved?</strong></div>';
 const policyLabels={ask:'Ask for approval',balanced:'Approve for me',full:'Full access'};
 const policyNotes={ask:'Review changes, commands and internet requests. Workspace reads follow your task setting.',balanced:'Run workspace reads and public web lookups; ask before changes or commands.',full:'Run tools, edits, commands and MCP automatically with your Windows permissions.'};
 function policyState(value){const mode=Object.hasOwn(policyLabels,value?.mode)?value.mode:'ask';menu.dataset.mode=mode;document.body.dataset.approvalMode=mode;$('agent-access-label').textContent=policyLabels[mode];for(const item of menu.querySelectorAll('[data-approval-mode]'))item.setAttribute('aria-checked',String(item.dataset.approvalMode===mode));}
 for(const mode of ['ask','balanced','full']){const b=document.createElement('button');b.type='button';b.dataset.approvalMode=mode;b.setAttribute('role','menuitemradio');b.innerHTML='<span></span><small></small>';b.firstElementChild.textContent=policyLabels[mode];b.lastElementChild.textContent=policyNotes[mode];b.onclick=()=>{if(!api)return;void perform(async()=>{const result=await api('approval-policy',{mode});policyState(result);menu.open=false;});};menu.lastElementChild.append(b);}
 const scope=document.createElement('small');scope.textContent='This app session only. Auto-continue must be on. Existing workspace checks remain active.';menu.lastElementChild.append(scope);actions.prepend(menu);
 if(api)void api('approval-policy').then(policyState).catch(()=>policyState(null));else policyState(null);
 const keyboard=event=>{if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();$('create').click();}};$('goal').addEventListener('keydown',keyboard);
 const send=$('create').onclick;$('create').onclick=event=>{if(!$('workspace').value.trim()&&!$('goal').value.trim().startsWith('/')){options.open=true;$('workspace').focus();$('status').textContent='Choose a workspace folder in Task settings before starting this task.';return;}return send(event);};
 for(const key of ['connections','skills','history'])for(const panel of panels[key])if(panel)main.append(panel);
 const icons={tasks:'<path d="M4 4h16v16H4zM8 9h8M8 13h6M8 17h4"/>',local:'<rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 1v4m6-4v4M9 19v4m6-4v4M1 9h4m-4 6h4m14-6h4m-4 6h4"/>',connections:'<path d="M8 12h8M9 7V4H4v5h3m10 0h3V4h-5v3M7 15H4v5h5v-3m6 0v3h5v-5h-3"/>',skills:'<path d="m5 20 4-1L20 8l-4-4L5 15zM13 7l4 4"/>',automations:'<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2M4 4l-2 4m18-4 2 4"/>',history:'<path d="M4 7v5h5M4 12a8 8 0 1 0 3-6M12 8v5l3 2"/>'};
 icons.memory='<path d="M8 4a4 4 0 0 0-4 4v2a4 4 0 0 0 0 7 4 4 0 0 0 8 2V6a4 4 0 0 0-4-2m4 2a4 4 0 0 1 8 2v2a4 4 0 0 1 0 7 4 4 0 0 1-8 2M8 9v4m8-4v4"/>';
 const labels={tasks:'Tasks',local:'Local AI',connections:'Connections',skills:'Skills',memory:'Memory & learning',automations:'Automations',history:'Task history'};
 const buttons=new Map();
 function show(key){
  document.body.dataset.agentView=key;
  for(const [name,items]of Object.entries(panels))for(const panel of items)if(panel)panel.hidden=name!==key||(panel.id==='connected-calendar-schedule'&&panel.dataset.calendarConnected!=='true');
  for(const [name,button]of buttons)button.setAttribute('aria-pressed',String(name===key));
  heading.textContent=labels[key];
 }
 for(const key of ['tasks','local','connections','skills','memory','automations','history']){
  const button=document.createElement('button');button.type='button';button.setAttribute('aria-label',labels[key]);button.title=labels[key];
  button.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true">'+icons[key]+'</svg><span>'+labels[key]+'</span>';
  button.onclick=()=>{
   const tab=tabs?.querySelector('[data-workspace-view="'+key+'"]');if(tab)tab.click();
   show(key);
  };buttons.set(key,button);nav.append(button);
 }
 document.body.prepend(nav);
 const quick=document.createElement('div');quick.id='agent-sidebar-actions';
 const fresh=document.createElement('button');fresh.type='button';fresh.textContent='+ New task';fresh.onclick=()=>{show('tasks');newTask();$('goal').focus();};
 const search=document.createElement('button');search.type='button';search.textContent='Search sessions';search.onclick=()=>{show('history');$('history-query').focus();};quick.append(fresh,search);nav.insertBefore(quick,buttons.get('tasks'));
 const recent=document.createElement('section');recent.id='agent-recent-tasks';const title=document.createElement('h3');title.textContent='Recent tasks';recent.append(title,$('tasks'));nav.append(recent);
 const subtitle=document.createElement('small');subtitle.className='agent-sidebar-note';subtitle.textContent='Sakura Agent · tools run on this PC';nav.append(subtitle);
 const observer=new MutationObserver(()=>{
  const pending=review.classList.contains('action')&&review.childNodes.length>0;
  dock.hidden=!pending;review.hidden=!pending;document.body.classList.toggle('agent-review-open',pending);
 });observer.observe(review,{childList:true,attributes:true,attributeFilter:['class']});
 window.addEventListener('pagehide',()=>observer.disconnect(),{once:true});
 const history=$('tasks');if(history)new MutationObserver(()=>{
  for(const button of history.querySelectorAll('button'))if(!button.dataset.studioBound){button.dataset.studioBound='1';button.addEventListener('click',()=>show('tasks'));}
 }).observe(history,{childList:true});
 show('tasks');
 window.addEventListener('sakura-agent-task-view',()=>show('tasks'));
};
