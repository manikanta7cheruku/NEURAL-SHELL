# Security policy

Seven can operate the user's computer, so security problems are taken seriously.

## Supported versions

Security fixes are released for the latest minor version. Users receive them through the in-app updater.

| Version | Supported |
|---|---|
| 1.3.x | Yes |
| Older | No, please update |

## Reporting a vulnerability

Email **cherukumanikanta77@gmail.com** with the subject "Seven security". Please include:

- What the problem is and what an attacker could do with it.
- Steps to reproduce, and the Seven and Windows versions.
- Whether you believe it is being exploited.

Please do not open a public issue or share details until a fix is released. You will get an acknowledgement within
three working days and a plan within ten.

## Security model in brief

- The backend listens on `127.0.0.1` only. Nothing on the network can reach it.
- Speech, conversations, memory and documents stay on the device. Outbound connections are listed in
  [privacy and data](docs/architecture/privacy-and-data.md).
- Risky actions ask for confirmation, and every action produces a receipt.
- Updates come only from the Seven server or the official GitHub releases repository.

## Known gaps

- The installer is not code-signed yet.
- Data at rest is not encrypted yet (planned, optional).
- Any local process can call the localhost API; a per-session token is planned.
