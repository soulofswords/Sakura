/* Shared cloud library: keeps PMX, VRM and Live2D selectors intact. */
async function api(path, body) {
    const response = await fetch('/api/model-library' + path, body === undefined ? {} : {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The library request failed.');
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
        <details><summary>Advanced connection</summary>
        <p>For a library you or a friend host with Sakura's own model-library service. The Sakura cloud signs in with the email and password above; it has no access codes.</p>
        <label>Library address<input type="url" data-library-url placeholder="https://library.example.com" autocomplete="off"></label>
        <label data-library-code-row hidden>Your library access code<input type="password" data-library-code autocomplete="off"></label>
        <button type="button" data-library-connect hidden>Connect with code</button></details>
        </details><button type="button" data-library-disconnect>Sign out</button>
        <label>Find a cloud character<input type="search" data-library-search placeholder="Search by character name"></label>
        <button type="button" data-library-refresh>Refresh library</button>
        <p data-library-status role="status" aria-live="polite">Connect to the Sakura library to browse characters.</p>
        <div data-library-results></div></div>`;
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
    let models = [], selectedFormat = '', cloudHost = '';
    const status = text => { get('status').textContent = text; };
    function revealPassword(show) {
        get('password').type = show ? 'text' : 'password';
        get('reveal').setAttribute('aria-pressed', String(show));
        get('reveal').setAttribute('aria-label', show ? 'Hide password' : 'Show password');
        get('reveal').title = get('reveal').getAttribute('aria-label');
    }
    get('reveal').onclick = () => revealPassword(get('password').type !== 'text');
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
        for (const model of models.filter(m => m.format === selectedFormat && String(m.name || '').toLocaleLowerCase().includes(query))) {
            const row = document.createElement('div'); row.style.marginBlock = '12px';
            const label = document.createElement('p');
            label.textContent = `${model.name} · ${model.format.toUpperCase()} · ${(model.bytes / 1048576).toFixed(1)} MB`;
            const button = document.createElement('button'); button.type = 'button';
            button.textContent = model.installed ? 'Installed' : 'Download'; button.disabled = model.installed;
            button.onclick = async () => {
                button.disabled = true; button.textContent = 'Downloading…';
                status('Downloading and checking ' + model.name + '. You can keep using Sakura.');
                try {
                    await api('/models/' + encodeURIComponent(model.id) + '/install', {});
                    model.installed = true; button.textContent = 'Installed';
                    document.getElementById('refresh-models')?.click();
                    status(model.name + ' is installed. Select it from the ' + model.format.toUpperCase() + ' selector.');
                } catch (error) { status(error.message); button.disabled = false; button.textContent = 'Retry download'; }
            };
            row.append(label, button); results.append(row);
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
        get('title').textContent = button.textContent;
        get('destination').textContent = `Downloaded models install into models/${format}/ and appear in the ${format === 'live2d' ? 'Live2D' : format.toUpperCase()} selector. Your existing models are kept.`;
        get('search').value = ''; render();
        status('Sign in to browse ' + format.toUpperCase() + ' cloud characters.');
        try {
            const config = await api('/connection'); get('url').value = config.url || '';
            cloudHost = config.cloud || ''; syncHost();
            if (config.configured) { section.querySelector('details').open = false; await refresh(); }
            else section.querySelector('details').open = true;
        } catch (error) { status(error.message); }
    };
    get('refresh').onclick = refresh;
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
            else { section.querySelector('details').open = false; await refresh(); }
        } catch (error) { status(error.message); }
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
            status(result.message + ' Open the link on this computer; it ends in a page where you choose the new password.');
        } catch (error) { status(error.message); }
        finally { get('recover').disabled = false; }
    };
    get('connect').onclick = async () => {
        get('connect').disabled = true;
        try {
            await api('/connection', {url: get('url').value, token: get('code').value});
            get('code').value = ''; section.querySelector('details').open = false; await refresh();
        } catch (error) { status(error.message); }
        finally { get('connect').disabled = false; }
    };
    get('disconnect').onclick = async () => {
        try { await api('/connection', {disconnect: true}); models = []; render(); status('Library disconnected. Downloaded models remain installed.'); }
        catch (error) { status(error.message); }
    };
}

function attach() {
    document.querySelectorAll('[data-studio-content="models"], [data-companion-content="character"]').forEach(installCard);
}
attach();
new MutationObserver(attach).observe(document.body, {childList: true, subtree: true});
