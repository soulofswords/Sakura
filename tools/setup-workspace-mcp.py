"""Connect an already-installed external Workspace MCP to this PC's Sakura.

Owner account credentials stay in Sakura's encrypted MCP environment storage.
Google OAuth consent is not bypassed and no existing refresh token is copied.
"""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--executable', type=Path, required=True)
    args = parser.parse_args()
    app = args.app.resolve()
    if not (app / 'agent_connections.py').is_file() or not args.executable.is_file():
        parser.error('Choose the editable Sakura app and installed workspace-mcp executable.')
    sys.path.insert(0, str(app))
    from agent_connections import Connections, secret_get
    account = secret_get('google-calendar')
    if not account.get('client_id') or not account.get('client_secret'):
        parser.error('The owner Google OAuth app is not configured in this Sakura copy.')
    credentials = Path(os.environ['LOCALAPPDATA']) / 'Sakura' / 'MCP' / 'GoogleWorkspace'
    credentials.mkdir(parents=True, exist_ok=True)
    connections = Connections()
    existing = next((item for item in connections.public() if item.get('name') == 'Google Workspace MCP' and item.get('transport') == 'stdio'), None)
    payload = {'name': 'Google Workspace MCP', 'transport': 'stdio', 'command': str(args.executable.resolve()),
               'args': ['--transport', 'stdio', '--tool-tier', 'core'],
               'env': {'GOOGLE_OAUTH_CLIENT_ID': account['client_id'], 'GOOGLE_OAUTH_CLIENT_SECRET': account['client_secret'],
                       'WORKSPACE_MCP_CREDENTIALS_DIR': str(credentials), 'WORKSPACE_MCP_PORT': '8789',
                       'WORKSPACE_MCP_BASE_URI': 'http://localhost', 'OAUTHLIB_INSECURE_TRANSPORT': '1'}}
    if existing:
        payload['id'] = existing['id']
    item = connections.save(payload)
    print('Saved external stdio connection:', item['name'])
    print('Google consent is still required for the added Workspace scopes.')


if __name__ == '__main__':
    main()
