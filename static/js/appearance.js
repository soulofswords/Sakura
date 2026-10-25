// Appearance is independent of avatar lighting and capture backgrounds.
export function installAppearance() {
    const modes = ['light', 'dark', 'system'];
    const system = window.matchMedia('(prefers-color-scheme: dark)');
    let stored = null;
    try { const saved = localStorage.getItem('sakura_ui_theme'); if (modes.includes(saved)) stored = saved; } catch (_) {}
    let mode = stored || 'system';
    function apply() {
        const resolved = mode === 'system' ? (system.matches ? 'dark' : 'light') : mode;
        document.documentElement.dataset.uiTheme = resolved;
        document.documentElement.style.colorScheme = resolved;
        document.querySelectorAll('[data-appearance-select]').forEach(select => { select.value = mode; });
    }
    function persist(value) {
        mode = value;
        try { localStorage.setItem('sakura_ui_theme', mode); } catch (_) {}
        apply();
        // The native startup dialog reads this same choice from settings.json.
        fetch('/api/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ui_theme: mode})}).catch(() => {});
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
    // Startup still synchronizes legacy lighting inputs by ID after async loading.
    // Keep those nodes connected, but outside both visible appearance panels.
    const legacy = document.createElement('div'); legacy.id = 'legacy-lighting-controls'; legacy.hidden = true; legacy.setAttribute('aria-hidden', 'true'); document.body.append(legacy);
    for (const container of [document.getElementById('tab-theme'), document.querySelector('#theme-popover .popover-body')]) {
        if (!container) continue;
        legacy.append(...container.childNodes);
        container.append(controls());
    }
    const heading = document.querySelector('#theme-popover .popover-header span'); if (heading) heading.textContent = 'Appearance';
    const button = document.getElementById('theme-btn'); if (button) button.title = 'Appearance · Light, Dark or System';
    system.addEventListener('change', () => { if (mode === 'system') apply(); });
    apply();
    // A theme saved on this PC wins over this browser profile's copy; a profile-only
    // choice from before settings stored it is migrated up so the launcher can see it.
    fetch('/api/settings').then(response => response.ok ? response.json() : null).then(data => {
        const saved = data && modes.includes(data.ui_theme) ? data.ui_theme : null;
        if (saved && saved !== mode) { mode = saved; try { localStorage.setItem('sakura_ui_theme', mode); } catch (_) {} apply(); }
        else if (!saved && stored) persist(stored);
    }).catch(() => {});
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', installAppearance, {once:true}); else installAppearance();
