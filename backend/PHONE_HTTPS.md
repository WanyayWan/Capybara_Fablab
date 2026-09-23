# Phone HTTPS Development Setup

FabAI serves the phone client over HTTPS because mobile browsers require a secure
context before allowing microphone access from a LAN address.

The backend generates a local development CA and certificate in the backend/certs
directory. Before using the phone microphone, install and trust fabai-dev-ca.pem on
the phone as a certificate authority, following the phone operating system's normal
certificate-installation process. This CA is for the private development network only.

After trusting the CA, open the HTTPS address printed by the backend on port 8443, tap Enable Voice,
and allow microphone access. The phone maintains a WebSocket connection and receives
BOOT-button listening requests over that connection.
