// Local alarm overlay and chime; works without model or speech downloads.
export function installReminders(isActive,getSpeaker=()=> '') {
    const panel=document.createElement('section');panel.id='reminder-alert';panel.hidden=true;
    panel.setAttribute('role','alertdialog');panel.setAttribute('aria-label','Sakura timer or alarm');
    panel.innerHTML='<strong>⏰ Sakura alert</strong><p></p><button type="button" data-action="dismiss">Dismiss</button> <button type="button" data-action="snooze">Snooze 5 minutes</button>';
    document.body.appendChild(panel);
    const nudge=document.createElement('aside');nudge.hidden=true;nudge.style.cssText='position:fixed;bottom:70px;left:90px;max-width:320px;padding:12px;background:var(--panel-bg,#20252d);color:inherit;border:1px solid #778899;border-radius:12px;z-index:1200';
    const nudgeText=document.createElement('p'),revisit=document.createElement('button'),dismiss=document.createElement('button');revisit.textContent='Revisit saves';dismiss.textContent='Dismiss';nudge.append(nudgeText,revisit,dismiss);document.body.append(nudge);
    revisit.onclick=()=>{nudge.hidden=true;window.dispatchEvent(new Event('sakura-open-archaeology'));};dismiss.onclick=()=>nudge.hidden=true;
    let current=null,context=null,polling=false,lastTone=0,closed=false;
    const stopSound=()=>{context?.close().catch(()=>{});context=null;};
    async function chime(){
        if(Date.now()-lastTone<4000)return;lastTone=Date.now();
        try{
            context ||= new (window.AudioContext||window.webkitAudioContext)();
            if(getSpeaker()&&context.setSinkId)await context.setSinkId(getSpeaker());
            await context.resume();if(!current)return;
            const oscillator=context.createOscillator(),gain=context.createGain(),now=context.currentTime;
            oscillator.frequency.setValueAtTime(880,now);oscillator.frequency.setValueAtTime(1100,now+.18);
            gain.gain.setValueAtTime(.15,now);gain.gain.exponentialRampToValueAtTime(.001,now+.6);
            oscillator.connect(gain);gain.connect(context.destination);oscillator.start(now);oscillator.stop(now+.65);
        }catch(_){} // The visible alert still works if audio is blocked.
    }
    async function poll(){
        if(closed||polling)return;
        if(!isActive()){panel.hidden=true;nudge.hidden=true;current=null;stopSound();return;}
        polling=true;
        try{
            const response=await fetch('/api/reminders');if(!response.ok)return;
            const data=await response.json();if(closed||!isActive())return;
            if(data.archaeology_nudge){nudgeText.textContent=data.archaeology_nudge.message;nudge.hidden=false;}
            current=data.items?.find(item=>item.status==='ringing')||null;
            panel.hidden=!current;
            if(current){panel.querySelector('p').textContent=`${current.kind==='timer'?'Timer finished':'Alarm'}: ${current.label}`;await chime();}
            else stopSound();
        }catch(_){}finally{polling=false;}
    }
    panel.addEventListener('click',async event=>{
        const action=event.target.dataset.action;if(!current||!action)return;
        const id=current.id;
        try{
            const response=await fetch('/api/reminders/dismiss',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,snooze:action==='snooze'})});
            if(!response.ok)throw new Error();
            current=null;panel.hidden=true;stopSound();await poll();
        }catch(_){panel.querySelector('p').textContent='Could not update the alert. Please retry.';}
    });
    let calendarBusy=false;
    async function pollCalendar(){
        if(closed||calendarBusy||!isActive())return;
        calendarBusy=true;
        try{const response=await fetch('/api/memory-archaeology/calendar-context');if(!response.ok)return;
            const data=await response.json();if(closed||!isActive())return;
            if(data.nudge?.message){nudgeText.textContent=data.nudge.message;nudge.hidden=false;}
        }catch(_){}finally{calendarBusy=false;}
    }
    const calendarTimer=setInterval(pollCalendar,60000);void pollCalendar();
    const timer=setInterval(poll,1000);poll();
    window.addEventListener('pagehide',()=>{closed=true;clearInterval(timer);clearInterval(calendarTimer);stopSound();panel.remove();nudge.remove();},{once:true});
}
