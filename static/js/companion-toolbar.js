export function installCompanionToolbar() {
    const button = document.getElementById('companion-toolbar-toggle');
    const panel = document.getElementById('companion-toolbar');
    const closeDropdowns = () => {
        panel.querySelectorAll('.dropdown-menu').forEach(menu => menu.classList.add('hidden'));
        panel.querySelectorAll('.custom-dropdown').forEach(dropdown => dropdown.classList.remove('open'));
    };
    function setExpanded(expanded) {
        document.body.classList.toggle('companion-toolbar-open', expanded);
        button.setAttribute('aria-expanded', String(expanded));
        button.title = expanded ? 'Hide companion controls' : 'Show companion controls';
        if (!expanded) closeDropdowns();
    }
    // Native titlebar drag handlers must never intercept this button.
    for (const type of ['pointerdown', 'mousedown']) button.addEventListener(type, event => event.stopPropagation());
    button.addEventListener('click', event => {
        event.stopPropagation();
        setExpanded(!document.body.classList.contains('companion-toolbar-open'));
    });
    document.addEventListener('click', event => {
        if (document.body.classList.contains('companion-toolbar-open') &&
            !panel.contains(event.target) && !button.contains(event.target)) setExpanded(false);
    }, true);
    document.addEventListener('keydown', event => { if (event.key === 'Escape') setExpanded(false); });
    panel.addEventListener('scroll', event => { if (event.target === panel) closeDropdowns(); }, true);
    window.addEventListener('resize', () => setExpanded(false));
    function positionDropdown(trigger, menu) {
        if (!document.body.classList.contains('desktop-companion')) {
            for (const property of ['position','top','left','width','maxHeight']) menu.style[property] = '';
            return;
        }
        const box = trigger.getBoundingClientRect();
        const width = Math.min(260, window.innerWidth - 24);
        let top = box.bottom + 6;
        if (window.innerHeight - top < 120 && box.top > 160) top = Math.max(12, box.top - 256);
        Object.assign(menu.style, {position:'fixed', top:top+'px',
            left:Math.max(12, Math.min(box.left, window.innerWidth-width-12))+'px',
            width:width+'px', maxHeight:Math.max(60, Math.min(250, window.innerHeight-top-12))+'px'});
    }
    return {setExpanded, positionDropdown};
}
