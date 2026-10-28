/* Shared cloud library: keeps PMX, VRM and Live2D selectors intact. */
if (!document.getElementById('cloud-character-grid-style')) {
    const style=document.createElement('style');style.id='cloud-character-grid-style';
    style.textContent=`.cloud-character-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:12px;margin-top:14px}
    .cloud-character-card{min-width:0;border:1px solid var(--border,#8796a755);border-radius:12px;padding:8px;background:var(--panel-bg,transparent)}
    .cloud-character-pick{display:flex!important;flex-direction:column;gap:8px;width:100%;padding:0!important;border:0!important;background:transparent!important;color:inherit!important;text-align:left;cursor:pointer}
    .cloud-character-image{width:100%;aspect-ratio:1;display:grid;place-items:center;overflow:hidden;border-radius:8px;background:#8796a71a}
    .cloud-character-image img{width:100%;height:100%;object-fit:contain}
    .cloud-character-image>span{padding:10px;overflow-wrap:anywhere;text-align:center;font-weight:600}
    .cloud-character-name{font-weight:600;overflow-wrap:anywhere;line-height:1.35}
    .cloud-character-meta{font-size:.8rem;opacity:.8;margin:6px 0}
    .cloud-character-card:has([aria-pressed="true"]){outline:2px solid var(--accent,#47acdf);outline-offset:1px}
    .cloud-character-card>button{width:100%}
    .cloud-character-grid>p{grid-column:1/-1}`;
    style.textContent+=`.cloud-library-breadcrumb{display:flex;gap:8px;align-items:center;margin:12px 0;flex-wrap:wrap}
    .cloud-library-folder{min-height:110px;display:flex!important;flex-direction:column;align-items:center;justify-content:center;gap:10px}
    .cloud-download-progress{display:block;width:100%;height:7px;margin:8px 0;accent-color:var(--accent,#47acdf)}
    .cloud-download-spinner{display:inline-block;width:13px;height:13px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;vertical-align:middle;margin-right:6px;animation:sakura-download-spin .8s linear infinite}
    @keyframes sakura-download-spin{to{transform:rotate(360deg)}}
    @media(prefers-reduced-motion:reduce){.cloud-download-spinner{animation:none}}`;
    document.head.append(style);
}
async function api(path, body) {
    const response = await fetch('/api/model-library' + path, body === undefined ? {} : {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) {
        // reset_pending is the difference between "you typed the wrong password" and "your reset
        // link is verified and waiting on this PC", so the caller needs the whole reply body.
        const error = new Error(data.error || 'The library request failed.');
        error.payload = data;
        throw error;
    }
    return data;
}

function installCard(host) {
    if (host.querySelector('[data-cloud-library]')) return;
    const section = document.createElement('section');
    section.className = 'studio-card';
    section.dataset.cloudLibrary = '';
    section.hidden = true;
    section.innerHTML = `<h3 data-library-title>Cloud import</h3>
        <p data-library-destination></p>
        <div data-library-panel>
        <details data-library-account><summary>Sign in or create a Sakura account</summary>
        <p>Enter your email and choose a password to create your Sakura account. You will receive a verification email.</p>
        <label style="display:block;margin:12px 0">Email<input style="display:block;width:100%;box-sizing:border-box;margin-top:6px" type="email" data-library-email autocomplete="email" placeholder="you@example.com" required></label>
        <label style="display:block;margin:12px 0">Password<span style="display:block;position:relative;margin-top:6px"><input style="display:block;width:100%;box-sizing:border-box;padding-right:2.4rem" type="password" data-library-password autocomplete="current-password" placeholder="At least 8 characters" minlength="8" required><button type="button" data-library-reveal aria-pressed="false" aria-label="Show password" title="Show password" style="position:absolute;right:2px;top:50%;transform:translateY(-50%);border:0;background:transparent;cursor:pointer;font-size:1.05rem;line-height:1;padding:.2rem .45rem">👁</button></span></label>
        <button type="button" data-library-signin>Sign in</button>
        <button type="button" data-library-signup>Create account</button>
        <button type="button" data-library-recover>Forgot password?</button>
        <div data-library-finish-box hidden>
        <p>Sakura verified your reset link on this computer, so you can finish it here instead of hunting for the browser tab.</p>
        <label style="display:block;margin:12px 0">New password<span style="display:block;position:relative;margin-top:6px"><input style="display:block;width:100%;box-sizing:border-box;padding-right:2.4rem" type="password" data-library-new autocomplete="new-password" placeholder="At least 8 characters" minlength="8" required><button type="button" data-library-eye-new aria-pressed="false" aria-label="Show password" title="Show password" style="position:absolute;right:2px;top:50%;transform:translateY(-50%);border:0;background:transparent;cursor:pointer;font-size:1.05rem;line-height:1;padding:.2rem .45rem">👁</button></span></label>
        <label style="display:block;margin:12px 0">Repeat it<span style="display:block;position:relative;margin-top:6px"><input style="display:block;width:100%;box-sizing:border-box;padding-right:2.4rem" type="password" data-library-new-repeat autocomplete="new-password" placeholder="Type it the same way again" minlength="8" required><button type="button" data-library-eye-repeat aria-pressed="false" aria-label="Show password" title="Show password" style="position:absolute;right:2px;top:50%;transform:translateY(-50%);border:0;background:transparent;cursor:pointer;font-size:1.05rem;line-height:1;padding:.2rem .45rem">👁</button></span></label>
        <button type="button" data-library-finish>Set new password</button>
        </div>
        <details><summary>Advanced connection</summary>
        <p>For a library you or a friend host with Sakura's own model-library service. The Sakura cloud signs in with the email and password above; it has no access codes.</p>
        <label>Library address<input type="url" data-library-url placeholder="https://library.example.com" autocomplete="off"></label>
        <label data-library-code-row hidden>Your library access code<input type="password" data-library-code autocomplete="off"></label>
        <button type="button" data-library-connect hidden>Connect with code</button></details>
        </details><button type="button" data-library-disconnect>Sign out</button>
        <div data-library-browse hidden>
        <label>Find a cloud character<input type="search" data-library-search placeholder="Search by character name"></label>
        <button type="button" data-library-refresh>Refresh library</button>
        <nav data-library-folders class="cloud-library-breadcrumb" aria-label="Cloud library folders"></nav>
        <div data-library-results class="cloud-character-grid" aria-label="Cloud characters"></div></div>
        <p data-library-status role="status" aria-live="polite">Connect to the Sakura library to browse characters.</p>
        </div>`;
    const imports = host.querySelector('[data-studio-port="imports"], [data-companion-port="imports"]');
    const importCard = imports?.closest('.studio-card');
    const buttons = document.createElement('div');
    buttons.className = 'studio-actions';
    buttons.style.marginTop = '10px';
    buttons.setAttribute('aria-label', 'Import a character from the cloud');
    for (const format of ['pmx', 'vrm', 'live2d']) {
        const button = document.createElement('button'); button.type = 'button';
        button.dataset.libraryFormat = format;
        button.textContent = 'Cloud import ' + (format === 'live2d' ? 'Live2D' : format.toUpperCase());
        button.setAttribute('aria-expanded', 'false');
        buttons.append(button);
    }
    if (importCard) {
        const hint = importCard.querySelector('p');
        importCard.insertBefore(buttons, hint);
        importCard.after(section);
    } else host.append(buttons, section);
    const get = key => section.querySelector('[data-library-' + key + ']');
    let models = [], selectedFormat = '', cloudHost = '', selectedModel = '', downloads = 0, selectedGame='';
    const modelParts=model=>{
        const parts=String(model.name||'').split(' / ');
        return model.format==='pmx'&&parts.length>1?{game:parts[0],path:parts.slice(0,-1),name:parts.at(-1)}:{game:'Other characters',path:['Other characters'],name:String(model.name||'')};
    };
    const status = text => { get('status').textContent = text; };
    function revealPassword(show) {
        get('password').type = show ? 'text' : 'password';
        get('reveal').setAttribute('aria-pressed', String(show));
        get('reveal').setAttribute('aria-label', show ? 'Hide password' : 'Show password');
        get('reveal').title = get('reveal').getAttribute('aria-label');
    }
    get('reveal').onclick = () => revealPassword(get('password').type !== 'text');
    // Typing a new password twice is where this whole reset goes wrong for real people, so both
    // fields get the same show/hide eye the reset page in the browser gives them.
    for (const [eye, field] of [['eye-new', 'new'], ['eye-repeat', 'new-repeat']]) {
        get(eye).onclick = () => {
            const show = get(field).type !== 'text';
            get(field).type = show ? 'text' : 'password';
            get(eye).setAttribute('aria-pressed', String(show));
            get(eye).setAttribute('aria-label', show ? 'Hide password' : 'Show password');
            get(eye).title = get(eye).getAttribute('aria-label');
        };
    }
    // A code is only meaningful to a library the owner hosts, so the cloud address never shows one.
    function syncHost() {
        const typed = get('url').value.trim().replace(/\/+$/, '');
        const custom = !!typed && typed !== cloudHost.replace(/\/+$/, '');
        get('code-row').hidden = get('connect').hidden = !custom;
    }
    get('url').oninput = syncHost;
    function render() {
        const query = get('search').value.trim().toLocaleLowerCase();
        const results = get('results'); results.replaceChildren();
        const navigation=get('folders');navigation.replaceChildren();
        // Retain old combined package IDs for already-installed users, but hide
        // their card once the authored outfit/variant children are published.
        const all=models.filter(m=>m.format===selectedFormat).filter((model,_,formatModels)=>
            model.format!=='pmx'||!formatModels.some(other=>String(other.name||'').startsWith(String(model.name||'')+' / ')));
        const hierarchical=selectedFormat==='pmx'&&all.some(m=>String(m.name||'').includes(' / '));
        const currentPath=selectedGame?selectedGame.split(' / '):[];
        const within=model=>{
            const path=modelParts(model).path;
            return currentPath.every((part,index)=>path[index]===part);
        };
        if(hierarchical){
            const home=document.createElement('button');home.type='button';home.textContent='All games';home.onclick=()=>{selectedGame='';get('search').value='';render();};navigation.append(home);
            for(let index=0;index<currentPath.length;index++){
                const crumb=document.createElement('button');crumb.type='button';crumb.textContent=currentPath[index];
                crumb.onclick=()=>{selectedGame=currentPath.slice(0,index+1).join(' / ');get('search').value='';render();};navigation.append(crumb);
            }
            if(!query){
                const folders=[...new Set(all.filter(within).map(m=>modelParts(m).path[currentPath.length]).filter(Boolean))].sort();
                for(const game of folders){
                    const folder=document.createElement('button');folder.type='button';folder.className='cloud-library-folder';
                    const icon=document.createElement('span');icon.textContent='📁';icon.style.fontSize='30px';icon.setAttribute('aria-hidden','true');
                    const title=document.createElement('span');title.textContent=game;
                    folder.append(icon,title);folder.setAttribute('aria-label',(currentPath.length?'Open folder ':'Open game ')+game);folder.onclick=()=>{selectedGame=[...currentPath,game].join(' / ');render();};results.append(folder);
                }
                if(!currentPath.length&&results.childElementCount)return;
            }
        }
        for (const model of all.filter(m => (!hierarchical||(within(m)&&(query||modelParts(m).path.length===currentPath.length)))&&String(m.name || '').toLocaleLowerCase().includes(query))) {
            const displayName=hierarchical?modelParts(model).name:model.name;
            const row = document.createElement('article');row.className='cloud-character-card';
            const pick=document.createElement('button');pick.type='button';pick.className='cloud-character-pick';
            pick.setAttribute('aria-label','Select '+model.name);
            pick.setAttribute('aria-pressed',String(selectedModel===model.id));
            const square=document.createElement('span');square.className='cloud-character-image';
            const placeholder=document.createElement('span');placeholder.textContent=displayName;
            square.append(placeholder);
            if(model.preview){
                const image=document.createElement('img');image.alt=model.name+' preview';image.loading='lazy';image.decoding='async';
                image.src='/api/model-library/models/'+encodeURIComponent(model.id)+'/preview';
                image.onload=()=>placeholder.remove();image.onerror=()=>image.remove();square.append(image);
            }
            const name=document.createElement('span');name.className='cloud-character-name';name.textContent=displayName;
            pick.append(square,name);
            pick.onclick=()=>{
                selectedModel=model.id;
                for(const other of results.querySelectorAll('[aria-pressed]'))other.setAttribute('aria-pressed',String(other===pick));
                status(model.installed?model.name+' is installed. Choose it from the '+model.format.toUpperCase()+' selector.':
                    model.name+' selected. Choose Download to install this character.');
            };
            const label = document.createElement('p');label.className='cloud-character-meta';
            label.textContent = `${displayName} · ${model.format.toUpperCase()} · ${(model.bytes / 1048576).toFixed(1)} MB`;
            const button = document.createElement('button'); button.type = 'button';
            button.textContent = model.installed ? 'Installed' : 'Download'; button.disabled = model.installed;
            button.onclick = async () => {
                downloads++;
                button.disabled = true;button.replaceChildren();
                const spinner=document.createElement('span');spinner.className='cloud-download-spinner';spinner.setAttribute('aria-hidden','true');
                button.append(spinner,document.createTextNode('Downloading…'));
                row.setAttribute('aria-busy','true');
                const progress=document.createElement('progress');progress.className='cloud-download-progress';progress.setAttribute('aria-label','Downloading '+displayName);row.append(progress);
                status('Downloading and checking ' + model.name + '. You can keep using Sakura.');
                try {
                    await api('/models/' + encodeURIComponent(model.id) + '/install', {});
                    model.installed = true; button.textContent = 'Installed';
                    document.getElementById('refresh-models')?.click();
                    status(model.name + ' is installed. Select it from the ' + model.format.toUpperCase() + ' selector.');
                } catch (error) { status(error.message); button.disabled = false; button.textContent = 'Retry download'; }
                finally { downloads--;row.removeAttribute('aria-busy');progress.remove(); }
            };
            row.append(pick,label, button); results.append(row);
        }
        if (!results.childElementCount) {
            const message = document.createElement('p');
            message.textContent = query ? 'No character matches this name.' : 'No ' + selectedFormat.toUpperCase() + ' models are published yet.';
            results.append(message);
        }
    }
    async function refresh() {
        get('refresh').disabled = true; status('Loading model library…');
        try { models = (await api('/models')).models; render(); status(models.filter(m => m.format === selectedFormat).length + ' ' + selectedFormat.toUpperCase() + ' cloud characters available.'); }
        catch (error) { models = []; render(); status(error.message); }
        finally { get('refresh').disabled = false; }
    }
    get('search').oninput = render;
    for (const button of buttons.querySelectorAll('button')) button.onclick = async () => {
        const format = button.dataset.libraryFormat;
        const closing = selectedFormat === format && !section.hidden;
        section.hidden = closing;
        for (const other of buttons.querySelectorAll('button')) other.setAttribute('aria-expanded', String(!closing && other === button));
        if (closing) return;
        selectedFormat = format;
        selectedGame='';
        get('browse').hidden = true;
        get('title').textContent = button.textContent;
        get('destination').textContent = `Downloaded models install into models/${format}/ and appear in the ${format === 'live2d' ? 'Live2D' : format.toUpperCase()} selector. Your existing models are kept.`;
        get('search').value = ''; render();
        status('Sign in to browse ' + format.toUpperCase() + ' cloud characters.');
        try {
            const config = await api('/connection'); get('url').value = config.url || '';
            cloudHost = config.cloud || ''; syncHost();
            if (config.configured) { get('browse').hidden=false; section.querySelector('details').open = false; await refresh(); }
            else { models=[];render();section.querySelector('details').open = true; }
        } catch (error) { status(error.message); }
    };
    get('refresh').onclick = refresh;
    const autoRefresh=setInterval(()=>{
        if(!section.hidden&&!get('browse').hidden&&section.getClientRects().length&&document.visibilityState==='visible'&&!downloads&&!get('refresh').disabled)refresh();
    },60000);
    addEventListener('pagehide',()=>clearInterval(autoRefresh),{once:true});
    for (const action of ['signin', 'signup']) get(action).onclick = async () => {
        get('email').value = get('email').value.trim();
        if (!get('email').checkValidity()) {
            status('Enter a valid email address first.'); get('email').focus(); return;
        }
        if (get('password').value.length < 8) {
            status('Enter a password of at least 8 characters first.'); get('password').focus(); return;
        }
        get('signin').disabled = get('signup').disabled = true;
        status(action === 'signup' ? 'Creating your Sakura account…' : 'Signing into Sakura…');
        try {
            const result = await api('/account/' + action, {url: get('url').value,
                email: get('email').value, password: get('password').value});
            get('password').value = ''; revealPassword(false);
            if (result.confirmation_required) status(result.message);
            else { get('browse').hidden=false;section.querySelector('details').open = false; await refresh(); }
        } catch (error) {
            status(error.message);
            // A verified link waiting on this PC is worth more than a sentence the user has to
            // read, so put the password box in front of them while the session is still held.
            const waiting = error.payload?.reset_pending === true;
            get('finish').dataset.resetId = waiting ? error.payload.reset_id || '' : '';
            get('finish-box').hidden = !waiting;
            get('account').open = waiting || get('account').open;
            if (waiting) get('new').focus();
        }
        finally { get('signin').disabled = get('signup').disabled = false; }
    };
    get('recover').onclick = async () => {
        get('email').value = get('email').value.trim();
        if (!get('email').checkValidity()) {
            status('Enter the email address your Sakura account uses first.'); get('email').focus(); return;
        }
        get('recover').disabled = true;
        status('Sending a reset email…');
        try {
            const result = await api('/account/recover', {url: get('url').value, email: get('email').value});
            status(result.message);
        } catch (error) { status(error.message); }
        finally { get('recover').disabled = false; }
    };
    get('finish').onclick = async () => {
        const password = get('new').value;
        if (password.length < 8) { status('Enter the new password with at least 8 characters first.'); get('new').focus(); return; }
        if (password !== get('new-repeat').value) { status('The two new passwords do not match. Type it the same way twice.'); return; }
        get('finish').disabled = true;
        status('Setting your new password…');
        try {
            const result = await api('/finish-reset', {reset_id: get('finish').dataset.resetId || '', password, confirm: password});
            get('new').value = get('new-repeat').value = '';
            get('finish-box').hidden = true;
            status(result.message);
        } catch (error) { status(error.message); }
        finally { get('finish').disabled = false; }
    };
    get('connect').onclick = async () => {
        get('connect').disabled = true;
        try {
            await api('/connection', {url: get('url').value, token: get('code').value});
            get('code').value = '';get('browse').hidden=false; section.querySelector('details').open = false; await refresh();
        } catch (error) { status(error.message); }
        finally { get('connect').disabled = false; }
    };
    get('disconnect').onclick = async () => {
        try { await api('/connection', {disconnect: true}); models = []; render();get('browse').hidden=true;get('account').open=true; status('Library disconnected. Downloaded models remain installed.'); }
        catch (error) { status(error.message); }
    };
}

function attach() {
    document.querySelectorAll('[data-studio-content="models"], [data-companion-content="character"]').forEach(installCard);
}
attach();
new MutationObserver(attach).observe(document.body, {childList: true, subtree: true});
