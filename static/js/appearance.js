// Appearance is independent of avatar lighting and capture backgrounds.
export function installAppearance() {
    const modes = ['light', 'dark', 'system'];
    const system = window.matchMedia('(prefers-color-scheme: dark)');
    let stored = null;
    try { const saved = localStorage.getItem('sakura_ui_theme'); if (modes.includes(saved)) stored = saved; } catch (_) {}
    let mode = stored || 'system', revision = 0;
    let saveQueue = Promise.resolve();
    function apply() {
        const resolved = mode === 'system' ? (system.matches ? 'dark' : 'light') : mode;
        document.documentElement.dataset.uiTheme = resolved;
        document.documentElement.style.colorScheme = resolved;
        document.querySelectorAll('[data-appearance-select]').forEach(select => { select.value = mode; });
    }
    function persist(value) {
        revision++;
        mode = value;
        try { localStorage.setItem('sakura_ui_theme', mode); } catch (_) {}
        apply();
        // The native startup dialog reads this same choice from settings.json.
        const selected = mode;
        saveQueue = saveQueue.catch(() => {}).then(() => fetch('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ui_theme: selected})})).catch(() => {});
    }
    function controls() {
        const group = document.createElement('div');
        group.className = 'setting-group appearance-controls';
        const label = document.createElement('label'); label.textContent = 'Appearance';
        const select = document.createElement('select'); select.dataset.appearanceSelect = ''; select.setAttribute('aria-label', 'Appearance theme');
        for (const value of modes) select.add(new Option(value[0].toUpperCase() + value.slice(1), value));
        label.append(select); group.append(label);
        const hint = document.createElement('p'); hint.className = 'modal-hint'; hint.textContent = 'System follows your device’s light or dark appearance.'; group.append(hint);
        select.addEventListener('change', () => { persist(select.value); });
        return group;
    }
    for (const container of [document.getElementById('tab-theme'), document.querySelector('#theme-popover .popover-body')]) {
        if(container)container.replaceChildren(controls());
    }
    const heading = document.querySelector('#theme-popover .popover-header span'); if (heading) heading.textContent = 'Appearance';
    const button = document.getElementById('theme-btn'); if (button) button.title = 'Appearance · Light, Dark or System';
    const themePanel=document.getElementById('tab-theme');
    if(themePanel&&(window.SAKURA_EDITION||'companion')!=='vtuber'){
        const access=document.createElement('div');access.className='setting-group';access.id='computer-access-setting';
        const accessLabel=document.createElement('label'),accessToggle=document.createElement('input');
        accessToggle.id='theme-computer-access';accessToggle.type='checkbox';accessToggle.style.width='auto';accessToggle.disabled=true;
        accessToggle.setAttribute('role','switch');accessToggle.setAttribute('aria-label','Computer access');accessToggle.setAttribute('aria-checked','false');
        const accessState=document.createElement('span');accessState.textContent='Off';
        accessLabel.append(accessToggle,document.createTextNode(' Computer access · '),accessState);
        const accessNote=document.createElement('p');accessNote.className='modal-hint';accessNote.textContent='Allow supported PC tools such as PC status, volume and opening apps. Actions that require approval still ask first. Saves automatically.';
        access.append(accessLabel,accessNote);themePanel.append(access);
        let accessRevision=0;
        const showAccess=value=>{
            accessToggle.checked=!!value;accessToggle.setAttribute('aria-checked',String(!!value));accessState.textContent=value?'On':'Off';
            for(const id of ['computer-control-toggle','system-tools-permission']){const input=document.getElementById(id);if(input)input.checked=!!value;}
        };
        async function readAccess(){
            const current=accessRevision;
            try{const response=await fetch('/api/settings'),data=await response.json();if(!response.ok)throw Error(data.error||'Could not read computer access.');if(current!==accessRevision)return;showAccess(data.computer_control_enabled===true);accessToggle.disabled=false;}
            catch(error){accessNote.textContent=error.message;}
        }
        accessToggle.addEventListener('change',async()=>{
            const requested=accessToggle.checked;accessRevision++;accessToggle.disabled=true;
            try{
                const response=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({computer_control_enabled:requested})});
                const data=await response.json();if(!response.ok||data.ok!==true)throw Error(data.error||'Could not save computer access.');
                showAccess(requested);accessNote.textContent=requested?'Computer access is on. You can ask Sakura for PC status. Approval requirements still apply.':'Computer access is off. PC tools are blocked.';
            }catch(error){showAccess(!requested);accessNote.textContent=error.message;}
            finally{accessToggle.disabled=false;}
        });
        document.querySelector('.tab-btn[data-tab="theme"]')?.addEventListener('click',()=>{if(!accessToggle.disabled)void readAccess();});
        void readAccess();
        const group=document.createElement('div');group.className='setting-group';group.id='windows-startup-setting';
        const label=document.createElement('label'),toggle=document.createElement('input');toggle.type='checkbox';toggle.style.width='auto';toggle.disabled=true;
        label.append(toggle,document.createTextNode(' Run Sakura when Windows starts'));const note=document.createElement('p');note.className='modal-hint';note.textContent='Launch Companion automatically when you sign in to Windows.';group.append(label,note);themePanel.append(group);
        async function initialize(){
            const native=window.pywebview?.api;if(!native?.windows_startup_status)return;
            try{const result=await native.windows_startup_status();toggle.checked=!!result.enabled;toggle.disabled=!result.supported;if(result.error)note.textContent=result.error;}catch{note.textContent='Windows startup settings are unavailable.';}
        }
        toggle.addEventListener('change',async()=>{const requested=toggle.checked;toggle.disabled=true;try{const result=await window.pywebview.api.set_windows_startup(requested);if(result.error)throw Error(result.error);toggle.checked=!!result.enabled;note.textContent=result.enabled?'Companion will start when you sign in to Windows.':'Automatic startup is off.';}catch(error){toggle.checked=!requested;note.textContent=error.message;}finally{toggle.disabled=false;}});
        window.addEventListener('pywebviewready',initialize);void initialize();
    }
    system.addEventListener('change', () => { if (mode === 'system') apply(); });
    apply();
    // A theme saved on this PC wins over this browser profile's copy; a profile-only
    // choice from before settings stored it is migrated up so the launcher can see it.
    fetch('/api/settings').then(response => response.ok ? response.json() : null).then(data => {
        if (revision) return; // A newer user choice outranks this startup read.
        const saved = data && modes.includes(data.ui_theme) ? data.ui_theme : null;
        if (saved && saved !== mode) { mode = saved; try { localStorage.setItem('sakura_ui_theme', mode); } catch (_) {} apply(); }
        else if (!saved && stored) persist(stored);
    }).catch(() => {});
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', installAppearance, {once:true}); else installAppearance();
