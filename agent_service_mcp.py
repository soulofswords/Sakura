"""Sakura's built-in MCP adapters over its existing approved account APIs.

Uses the MCP SDK's in-memory transport: no extra process, port or shared secret.
These are Sakura adapters, not Google's remote developer-preview MCP endpoints.
"""
import copy
import hashlib
import json

SERVICES = {'google-calendar': 'Google Calendar', 'google-drive': 'Google Drive, Docs & Sheets', 'linkedin': 'LinkedIn'}


def binding(service):
    from agent_connections import secret_get
    if service == 'linkedin':
        from agent_linkedin import linkedin
        if not linkedin.status().get('connected'):
            raise ValueError('Connect LinkedIn in Connections first.')
        saved = secret_get('linkedin')
        identity = [saved.get('client_id'), saved.get('access_token'), saved.get('scopes')]
    else:
        from agent_calendar import google_calendar
        status = google_calendar.status()
        if not status.get('workspace_connected' if service == 'google-drive' else 'connected'):
            raise ValueError('Connect this Google service in Connections first.')
        saved = secret_get('google-calendar')
        identity = [google_calendar.config_fingerprint(), saved.get('refresh_token'), saved.get('scopes')]
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def tool_specs(service):
    if service not in SERVICES:
        raise ValueError('Choose Google Calendar, Google Drive or LinkedIn.')
    from agent_runtime import LOCAL_TOOLS
    from agent_google import TOOLS
    prefix = {'google-calendar': 'calendar.', 'google-drive': 'google.', 'linkedin': 'linkedin.'}[service]
    account = binding(service)
    tools = []
    for item in [*LOCAL_TOOLS, *TOOLS]:
        if not item['name'].startswith(prefix):
            continue
        item = copy.deepcopy(item)
        schema = item['inputSchema']
        schema['properties']['account_binding'] = {'type': 'string', 'const': account,
            'description': 'Use this exact account binding. A changed account requires new discovery and approval.'}
        schema.setdefault('required', []).append('account_binding')
        tools.append(item)
    return tools


def execute(service, name, arguments):
    from jsonschema import validate
    spec = next((tool for tool in tool_specs(service) if tool['name'] == name), None)
    if not spec:
        raise ValueError('This service does not expose that tool.')
    validate(arguments, spec['inputSchema'])
    args = {key: value for key, value in arguments.items() if key != 'account_binding'}
    if service == 'google-calendar':
        from agent_calendar import google_calendar
        methods = {'calendar.events.list': google_calendar.list_events, 'calendar.events.create': google_calendar.create_event,
                   'calendar.events.update': google_calendar.update_event}
        return methods[name](**args)
    if service == 'google-drive':
        from agent_google import execute as google_execute
        return google_execute(name, args)
    from agent_linkedin import linkedin
    if name == 'linkedin.profile':
        return {'profile': linkedin.profile()}
    return linkedin.publish(args['text'], args['visibility'])


def create_server(service):
    if service not in SERVICES:
        raise ValueError('Choose a supported service.')
    binding(service)  # Fail before the protocol task group if account access is missing.
    from mcp.server import Server
    from mcp.types import Tool, TextContent
    from starlette.concurrency import run_in_threadpool
    server = Server('sakura-' + service)

    @server.list_tools()
    async def list_tools():
        return [Tool(**item) for item in tool_specs(service)]

    @server.call_tool()
    async def call_tool(name, arguments):
        result = await run_in_threadpool(execute, service, name, arguments)
        return [TextContent(type='text', text=json.dumps(result, ensure_ascii=False))]

    return server
