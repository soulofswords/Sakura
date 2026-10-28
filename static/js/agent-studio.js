/* Presentation shell: all tools continue through the authenticated Agent API. */
window.installAgentStudio=()=>{
 if(document.getElementById('agent-studio-nav'))return;
 const $=id=>document.getElementById(id),main=document.querySelector('main'),tabs=$('agent-workspace-tabs');
 const nav=document.createElement('nav');nav.id='agent-studio-nav';nav.setAttribute('aria-label','Agent studio');
 const brand=document.createElement('div');brand.className='agent-nav-brand';brand.textContent='✿';brand.setAttribute('aria-hidden','true');nav.append(brand);
 const heading=document.createElement('p');heading.id='agent-view-heading';$('status').after(heading);
 const dock=document.createElement('div');dock.id='agent-review-dock';dock.hidden=true;document.querySelector('.grid').before(dock);
 const review=$('review');dock.append(review);
 const panels={tasks:[$('agent-compose'),$('agent-task-progress'),$('agent-tool-proposal')],local:[$('agent-local-ai')],automations:[$('agent-automations')],connections:[$('service-connections'),$('connected-calendar-schedule'),$('agent-telegram')],skills:[$('agent-skills')],memory:[$('agent-memory')],history:[$('agent-history')]};
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
   show(key);
   const tab=tabs?.querySelector('[data-workspace-view="'+key+'"]');if(tab)tab.click();
  };buttons.set(key,button);nav.append(button);
 }
 document.body.prepend(nav);
 const observer=new MutationObserver(()=>{
  const pending=review.classList.contains('action')&&review.childNodes.length>0;
  dock.hidden=!pending;review.hidden=!pending;document.body.classList.toggle('agent-review-open',pending);
 });observer.observe(review,{childList:true,attributes:true,attributeFilter:['class']});
 window.addEventListener('pagehide',()=>observer.disconnect(),{once:true});
 const history=$('tasks');if(history)new MutationObserver(()=>{
  for(const button of history.querySelectorAll('button'))if(!button.dataset.studioBound){button.dataset.studioBound='1';button.addEventListener('click',()=>show('tasks'));}
 }).observe(history,{childList:true});
 show('tasks');
};
