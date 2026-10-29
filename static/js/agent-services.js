/* External MCP connections, matching the NVIDIA Broadcast setup flow. */
window.installAgentServices = function ({api,perform,renderRun,selectRun}={}) {
    const byId = id => document.getElementById(id);
    const connections = byId('connections').closest('section');
    connections.id = 'service-connections';
    connections.querySelector('p').textContent = 'Add your provider’s MCP server URL and any required bearer token, just like NVIDIA Broadcast. Google and LinkedIn require an MCP provider with the permissions you need. Saving a connection does not run tools; discovery and actions still need approval.';
    connections.parentElement.prepend(connections);
    const integrations=document.createElement('section');integrations.className='card';integrations.id='agent-integrations';
    integrations.innerHTML='<h2>Web & security tools</h2><p>Playwright uses Sakura’s isolated browser. Firecrawl extracts public websites through its cloud API. Nuclei checks only origins you authorize below. You can also ask Teacher to add these tools.</p><div id="integration-status" role="status">Checking tools…</div><div class="row"><button type="button" data-integration="playwright">Set up Playwright</button><button type="button" data-integration="firecrawl">Set up Firecrawl</button><button type="button" data-integration="nuclei">Install Nuclei</button></div><details><summary>Credentials & authorized scan targets</summary><label>Firecrawl API key<input id="firecrawl-api-key" type="password" autocomplete="off" placeholder="Leave blank to keep saved key"></label><label>Authorized Nuclei origins, one per line<textarea id="nuclei-origins" placeholder="https://your-owned-site.example"></textarea></label><p>Authorize only sites you own or have permission to test. Scans make active HTTP requests. Firecrawl may consume provider credits.</p><button id="integration-save" type="button">Save tool settings</button></details>';
    connections.after(integrations);
    async function integrationState(){try{const data=await api('integrations');byId('integration-status').textContent=Object.entries(data).map(([key,value])=>key+': '+(value.ready?'Ready':value.installed?'Installed · authorize targets':value.configured?'Configured':'Setup needed')).join(' · ');if(document.activeElement!==byId('nuclei-origins'))byId('nuclei-origins').value=(data.nuclei?.origins||[]).join('\n');}catch(error){byId('integration-status').textContent=error.message;}}
    for(const button of integrations.querySelectorAll('[data-integration]'))button.onclick=()=>perform(async()=>{const run=await api('integrations/'+button.dataset.integration+'/setup',{});selectRun?.(run.id);renderRun(run);window.dispatchEvent(new CustomEvent('sakura-agent-task-view'));});
    byId('integration-save').onclick=()=>perform(async()=>{const field=byId('firecrawl-api-key');const key=field.value;field.value='';await api('integrations/configure',{firecrawl_key:key,scan_origins:byId('nuclei-origins').value.split('\n').map(value=>value.trim()).filter(Boolean)});await integrationState();});
    if(api)void integrationState();
    const google = byId('google-calendar');
    const schedule = document.createElement('section'); schedule.className = 'card';
    schedule.id = 'connected-calendar-schedule';
    const heading = document.createElement('h2'); heading.textContent = 'Schedule';
    schedule.append(heading, byId('schedule-manager')); google.before(schedule);
    // Keep existing account state for Companion chat, without offering built-in adapters.
    google.hidden = true;
    byId('linkedin-state').closest('section').hidden = true;
    byId('calendar-open').textContent = 'Connections';
    byId('calendar-open').onclick = () => connections.scrollIntoView({behavior:'smooth',block:'start'});
    return {render(state) {
        const connected = !!state.calendar?.connected;
        schedule.dataset.calendarConnected = String(connected);
        const view = document.body.dataset.agentView;
        schedule.hidden = !connected || (!!view && view !== 'connections');
    }};
};
