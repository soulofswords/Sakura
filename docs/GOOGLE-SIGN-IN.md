# Google sign-in for Calendar

The Agent workspace presents a **Sign in with Google** button and never asks end users to paste a client ID. The app build must be configured with its registered Google Desktop client ID using `SAKURA_GOOGLE_OAUTH_CLIENT_ID`. A client ID is public configuration, not a client secret.

After selecting an account, Google displays its consent page for the narrow Calendar events scope. Sakura only reads events and proposes event changes for explicit review. Gmail and Drive are not requested. User tokens remain in the existing OS-protected secret store.

The browser authorization uses PKCE, one-time state, and a loopback callback. The account chooser is shown on every sign-in. Tokens are bound to the client ID that issued them; changing the app client requires signing in again.
