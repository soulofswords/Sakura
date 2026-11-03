/* Presentation shell: all tools continue through the authenticated Agent API. */
window.installAgentStudio=({newTask=()=>{},api,perform}={})=>{
 if(document.getElementById('agent-studio-nav'))return;
 const $=id=>document.getElementById(id),main=document.querySelector('main'),tabs=$('agent-workspace-tabs');
 const nav=document.createElement('nav');nav.id='agent-studio-nav';nav.setAttribute('aria-label','Agent studio');
 const brand=document.createElement('div');brand.className='agent-nav-brand';brand.textContent='✿';brand.setAttribute('aria-hidden','true');nav.append(brand);
 const heading=document.createElement('p');heading.id='agent-view-heading';$('status').after(heading);
 const dock=document.createElement('div');dock.id='agent-review-dock';dock.hidden=true;
 const review=$('review');dock.append(review);
 // One right column: the outstanding approval on top, the task inspector below it. Keeping them
 // in a single rail is what stops an approval card and the process list from covering each other.
 const rail=document.createElement('div');rail.id='agent-right-rail';rail.append(dock);
 const inspector=$('agent-inspector');if(inspector)rail.append(inspector);
 document.querySelector('.grid').before(rail);
 const panels={tasks:[$('agent-compose'),$('agent-conversation'),$('agent-task-progress'),$('agent-tool-proposal')],local:[$('agent-local-ai')],automations:[$('agent-automations')],connections:[$('service-connections'),$('agent-integrations'),$('connected-calendar-schedule'),$('agent-telegram'),$('agent-extension-store')],skills:[$('agent-skills')],memory:[$('agent-memory'),$('agent-memory-workbench')],history:[$('agent-history'),$('agent-metrics')]};
 if($('agent-browser'))panels.browser=[$('agent-browser')];
 const compose=$('agent-compose'),progress=$('agent-task-progress');
 const options=document.createElement('details');options.id='agent-task-options';options.innerHTML='<summary>Task settings <span>Workspace, model & skills</span></summary>';
 const goalLabel=$('goal').closest('label'),actions=$('create').closest('.row');
 for(const child of [...compose.children])if(child!==goalLabel&&child!==actions&&child.tagName!=='H2')options.append(child);
 compose.insertBefore(options,actions);compose.querySelector('h2').textContent='Message Sakura';
 // The usage strip belongs under the buttons, not inside the settings drawer it got swept into.
 const usage=$('agent-usage-bar');if(usage)compose.append(usage);
 $('goal').placeholder='What would you like to work on?';$('goal').setAttribute('aria-label','Message Sakura');
 $('create').textContent='Start task';$('create').title='Create a task and start planning';
 const notice=options.querySelector('.notice');if(notice)notice.textContent='Tools follow the approval mode selected below. Commands and MCP processes run with your Windows permissions; the workspace is not a sandbox. Cloud AI receives the results it reads. Broad access requires Windows confirmation and resets when Sakura restarts.';
 const controls=document.createElement('div');controls.className='agent-task-controls';
 for(const id of ['plan','pause','resume','cancel'])controls.append($(id));
 progress.insertBefore(controls,$('progress'));
 // A chat reads downward: the task and its activity come first, then the exchange, then the
 // box you type in. Prepending put every new message above the goal instead of below it.
 main.insertBefore($('agent-conversation'),progress.nextSibling);
 const advanced=document.createElement('details');advanced.id='agent-advanced-tools';advanced.innerHTML='<summary>Tools & command permissions</summary>';
 $('agent-tool-proposal').before(advanced);advanced.append($('agent-tool-proposal'));panels.tasks.push(advanced);
 const menu=document.createElement('details');menu.id='agent-access-menu';menu.innerHTML='<summary id="agent-access-label">Ask for approval</summary><div class="agent-access-options"><strong>How should Sakura actions be approved?</strong></div>';
 const policyLabels={ask:'Ask for approval',balanced:'Approve for me',full:'Full access'};
 const policyNotes={ask:'Review changes, commands and internet requests. Workspace reads follow your task setting.',balanced:'Run workspace reads and public web lookups; ask before changes or commands.',full:'Run tools, edits, commands and MCP automatically with your Windows permissions.'};
 let modeInitialised=false,policyRevision=0,policyBusy=false;
 function policyControlsBusy(busy){policyBusy=busy;for(const b of document.querySelectorAll('[data-approval-mode],[data-execution-mode]'))b.disabled=busy;}
 function policyState(value){const mode=Object.hasOwn(policyLabels,value?.mode)?value.mode:'ask';menu.dataset.mode=mode;document.body.dataset.approvalMode=mode;$('agent-access-label').textContent=policyLabels[mode];
  // The policy survives a panel reload but the run-mode choice lived only in the page, so the
  // first read adopts the server's answer instead of showing a stale half-set switch.
  if(!modeInitialised&&$('auto-plan')){modeInitialised=true;$('auto-plan').checked=mode==='full';}
  for(const item of menu.querySelectorAll('[data-approval-mode]'))item.setAttribute('aria-checked',String(item.dataset.approvalMode===mode));showRunMode();}
 for(const mode of ['ask','balanced','full']){const b=document.createElement('button');b.type='button';b.dataset.approvalMode=mode;b.setAttribute('role','menuitemradio');b.innerHTML='<span></span><small></small>';b.firstElementChild.textContent=policyLabels[mode];b.lastElementChild.textContent=policyNotes[mode];b.onclick=()=>{if(!api||policyBusy)return;modeInitialised=true;++policyRevision;policyControlsBusy(true);void perform(async()=>{try{const result=await api('approval-policy',{mode});policyState(result);menu.open=false;}finally{policyControlsBusy(false);}});};menu.lastElementChild.append(b);}
 const scope=document.createElement('small');scope.textContent='This app session only. Run mode sets both auto-continue and this policy; choosing a level here leaves auto-continue as it is. Existing workspace checks remain active.';menu.lastElementChild.append(scope);
 // The model that plans this task is chosen where the task is started, not two drawers away.
 const planner=$('planner-provider')?.closest('label');if(planner)actions.prepend(planner);
 actions.prepend(menu);
 // Auto-continue and the approval policy decide the same thing together, so the panel offers one
 // visible choice for it. Two separate controls meant a task could be started with the wrong pair.
 const runMode=document.createElement('div');runMode.id='agent-execution-mode';runMode.setAttribute('role','radiogroup');runMode.setAttribute('aria-label','Run mode');
 const runModeCopy={approval:{label:'Approval',note:'Nothing runs until you click Approve.'},auto:{label:'Auto',note:'Plans, runs and continues to the end without a click.'}};
 const modePills=['approval','auto'].map(key=>{const b=document.createElement('button');b.type='button';b.dataset.executionMode=key;b.setAttribute('role','radio');b.textContent=runModeCopy[key].label;b.title=runModeCopy[key].note;b.onclick=()=>{if(!api)return;void chooseRunMode(key);};runMode.append(b);return b;});
 function showRunMode(){const auto=$('auto-plan')?.checked===true,policy=document.body.dataset.approvalMode;const autoSelected=auto&&policy==='full',approvalSelected=!auto&&policy==='ask';for(const b of modePills)b.setAttribute('aria-checked',String(b.dataset.executionMode==='auto'?autoSelected:approvalSelected));runMode.dataset.state=autoSelected?'auto':approvalSelected?'approval':'custom';const badge=document.querySelector('header .badge');if(badge)badge.textContent=autoSelected?'Auto: steps run without a click':approvalSelected?'Local approval required':'Mixed: check the run mode';runMode.title=autoSelected?runModeCopy.auto.note:approvalSelected?runModeCopy.approval.note:'Mixed: auto-continue '+(auto?'on':'off')+' with '+policyLabels[policy]+'. Open the access menu to change it.';}
 async function chooseRunMode(key){if(policyBusy)return;modeInitialised=true;++policyRevision;policyControlsBusy(true);const auto=key==='auto';const previous=$('auto-plan').checked;$('auto-plan').checked=auto;showRunMode();try{const result=await api('approval-policy',{mode:auto?'full':'ask'});policyState(result);$('status').textContent=auto?'Auto is on: each planned step, including file edits and commands, runs with your Windows permissions and without another click.':'Approval is on: nothing runs until you click Approve on that step.';}catch(error){$('auto-plan').checked=previous;showRunMode();$('status').textContent=error.message;}finally{policyControlsBusy(false);}}
 actions.prepend(runMode);
 if(api){const revision=policyRevision;void api('approval-policy').then(value=>{if(revision===policyRevision)policyState(value);}).catch(()=>{if(revision===policyRevision)policyState(null);});}else policyState(null);
 const keyboard=event=>{if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();$('create').click();}};$('goal').addEventListener('keydown',keyboard);
 const send=$('create').onclick;$('create').onclick=event=>{if(!$('workspace').value.trim()&&!$('goal').value.trim().startsWith('/')){options.open=true;$('workspace').focus();$('status').textContent='Choose a workspace folder in Task settings before starting this task.';return;}return send(event);};
 for(const key of ['connections','skills','history'])for(const panel of panels[key])if(panel)main.append(panel);
 const icons={tasks:'<path d="M4 4h16v16H4zM8 9h8M8 13h6M8 17h4"/>',local:'<rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 1v4m6-4v4M9 19v4m6-4v4M1 9h4m-4 6h4m14-6h4m-4 6h4"/>',connections:'<path d="M8 12h8M9 7V4H4v5h3m10 0h3V4h-5v3M7 15H4v5h5v-3m6 0v3h5v-5h-3"/>',skills:'<path d="m5 20 4-1L20 8l-4-4L5 15zM13 7l4 4"/>',automations:'<circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2M4 4l-2 4m18-4 2 4"/>',history:'<path d="M4 7v5h5M4 12a8 8 0 1 0 3-6M12 8v5l3 2"/>'};
 icons.memory='<path d="M8 4a4 4 0 0 0-4 4v2a4 4 0 0 0 0 7 4 4 0 0 0 8 2V6a4 4 0 0 0-4-2m4 2a4 4 0 0 1 8 2v2a4 4 0 0 1 0 7 4 4 0 0 1-8 2M8 9v4m8-4v4"/>';
 const labels={tasks:'Tasks',local:'Local AI',connections:'Connections',skills:'Skills',memory:'Memory & learning',automations:'Automations',history:'Task history'};
 const buttons=new Map();
 labels.browser='Browser';icons.browser='<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 8h18M7 5h1m2 0h1"/>';
 function show(key){
  document.body.dataset.agentView=key;
  for(const [name,items]of Object.entries(panels))for(const panel of items)if(panel)panel.hidden=name!==key||(panel.id==='connected-calendar-schedule'&&panel.dataset.calendarConnected!=='true');
  for(const [name,button]of buttons)button.setAttribute('aria-pressed',String(name===key));
  heading.textContent=labels[key];
 }
 for(const key of ['tasks','local','connections','skills','memory','automations','history',...(panels.browser?['browser']:[])]){
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
 window.addEventListener('sakura-agent-browser-view',()=>show('browser'));
};
