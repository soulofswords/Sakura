/* External MCP connections, matching the NVIDIA Broadcast setup flow. */
window.installAgentServices = function () {
    const byId = id => document.getElementById(id);
    const connections = byId('connections').closest('section');
    connections.id = 'service-connections';
    connections.querySelector('p').textContent = 'Add your provider’s MCP server URL and any required bearer token, just like NVIDIA Broadcast. Google and LinkedIn require an MCP provider with the permissions you need. Saving a connection does not run tools; discovery and actions still need approval.';
    connections.parentElement.prepend(connections);
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
