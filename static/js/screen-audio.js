export function installScreenAudio(isActive, isSpeaking, request = fetch, computerOnly = () => false) {
    const group = document.getElementById('screen-audio-group');
    const toggle = document.getElementById('screen-audio-enabled');
    const list = document.getElementById('screen-audio-sources');
    const status = document.getElementById('screen-audio-status');
    let selected = ['default-output'], busy = false, running = false;
    let catalog = [];
    try {
        toggle.checked = localStorage.getItem('sakura_screen_audio_enabled') !== 'false';
        const saved = JSON.parse(localStorage.getItem('sakura_screen_audio_sources'));
        if (Array.isArray(saved) && saved.length) selected = saved;
    } catch (_) {}
    async function refresh() {
        try {
            const response = await request('/api/screen-audio/sources');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error);
            catalog = data.sources;
            list.replaceChildren();
            const available = new Set(data.sources.map(source => source.id));
            selected = selected.filter(id => available.has(id));
            if (!selected.length && data.sources.length) selected = [data.sources[0].id];
            for (const source of data.sources) {
                if (computerOnly() && source.kind !== 'output') continue;
                const label = document.createElement('label');
                const check = document.createElement('input');
                check.type = 'checkbox'; check.checked = selected.includes(source.id);
                check.addEventListener('change', () => {
                    if (check.checked && selected.length >= 4) {check.checked = false; return;}
                    selected = check.checked ? [...selected, source.id] : selected.filter(id => id !== source.id);
                    localStorage.setItem('sakura_screen_audio_sources', JSON.stringify(selected));
                    void sync();
                });
                label.append(check, document.createTextNode(' ' + source.name));
                label.style.display = 'block'; list.append(label);
            }
            status.textContent = 'Ready · listens while Screen or Game mode is on';
        } catch (error) { status.textContent = 'Audio sources unavailable: ' + error.message; }
    }
    async function sync() {
        if (busy) return;
        const onlyComputer = computerOnly();
        const chosen = onlyComputer ? selected.filter(id => id === 'default-output' ||
            catalog.some(source => source.id === id && source.kind === 'output')) : selected;
        if (onlyComputer && !chosen.length) chosen.push('default-output');
        const enabled = isActive() && toggle.checked && chosen.length > 0;
        if (!enabled && !running) return;
        busy = true;
        try {
            const response = await request('/api/screen-audio', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({enabled, sources: chosen, computer_only: onlyComputer, paused: !!isSpeaking()})});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error);
            running = data.enabled;
            status.textContent = data.paused ? 'Audio listening paused while Sakura speaks' : data.message;
        } catch (error) { status.textContent = 'Audio listening unavailable: ' + error.message; }
        finally { busy = false; }
        // Screen may have been stopped while the backend was loading Whisper.
        if (running && (!isActive() || !toggle.checked)) void sync();
    }
    toggle.addEventListener('change', () => {
        localStorage.setItem('sakura_screen_audio_enabled', String(toggle.checked)); void sync();
    });
    document.getElementById('screen-audio-refresh').addEventListener('click', refresh);
    const timer = setInterval(sync, 1000);
    window.addEventListener('pagehide', () => {
        clearInterval(timer);
        request('/api/screen-audio', {method: 'POST', keepalive: true,
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify({enabled:false})}).catch(() => {});
    });
    return {refresh, sync, setVisible: visible => {group.hidden = !visible;}};
}
