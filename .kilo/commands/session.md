---
description: Manage Kilo sessions — list, switch, create, delete
---

# Session Management

Manage Kilo sessions: list, switch, create, and delete.

## Usage

- `/session` — list all available sessions
- `/session list` — list all sessions with ID, title, status, and last updated
- `/session new` — create a new session
- `/session switch <sessionID>` — switch to an existing session
- `/session delete <sessionID>` — delete a session

## Current sessions

!`kilo session list`

## Session actions

To manage sessions, use the `kilo session` CLI subcommands:

- `kilo session list` — list all sessions
- `kilo session delete <sessionID>` — delete a session by ID

To switch sessions, use the built-in `/sessions` slash command.
To create a new session, run `kilo run <message>`.
To export a session transcript, use `kilo export <sessionID>`.
