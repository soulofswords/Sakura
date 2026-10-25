# Phone discovery and reconnect fixes — 2026-10-24

Scope: mobile_link.py, Android MainActivity discovery/reconnect, and PhoneIdentity.java. Agent mode was not edited.

Reconnect now sends an unauthenticated random-nonce identity challenge, never a bearer token. The PC signs PC identity, its verified local HTTP endpoint and nonce with HMAC-SHA256 using the stored token hash. Android verifies the proof against its Keystore-decrypted pairing secret before sending its token. Saved-address and discovered-address reconnect share this check. Old records without a PC identity adopt the proven identity. A peer without the paired secret cannot pass; changing the advertised endpoint invalidates a forwarded proof. This is not TLS: the phone link still requires a trusted LAN.

Discovery replies must advertise the datagram sender's private IPv4 address and a valid port. Broadcast targets come from InterfaceAddress.getBroadcast(), with limited broadcast as fallback. The PC rechecks local addresses every two seconds and rebinds discovery sockets, including after temporary disconnection; it never advertises 0.0.0.0. Duplicate remembered endpoints are tried only once.

Validation: 26 targeted Python tests, executable Java proof tests, all Android Java source compilation, phone discovery UI and mobile appearance tests. Real UDP recovery test changes bind addresses and removes/restores network addresses. Physical phone DHCP roaming remains to be tested.

Deployment: mobile_link.py copied to both installed PC editions; app restart loads it. Android source is ready. No APK built for this fix, as requested. Existing APKs do not contain the new proof verification.
