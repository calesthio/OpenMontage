# Security Policy

## Reporting a vulnerability

If you believe you have found a security vulnerability in OpenMontage, please report
it **privately** so it can be triaged before public disclosure:

- Use GitHub's private vulnerability reporting: open the repository's
  **Security** tab → **Report a vulnerability**, or
- Open a minimal issue that describes the impact **without** including a working
  exploit, and ask a maintainer for a private channel.

Please do not disclose the details publicly until a fix or mitigation is available.

## Official distribution

The **only** official source of OpenMontage is this repository:

> **https://github.com/calesthio/OpenMontage**

OpenMontage is distributed **as source code** and installed from source (see the
README "Install & Run" steps). The project does **not** publish prebuilt Windows
`.exe` release binaries. Treat any standalone OpenMontage executable — especially
one offered as a GitHub *release asset* — as untrusted.

## ⚠️ Known malicious impersonation

A lookalike repository impersonates this project and distributes malware. It is
**not affiliated with OpenMontage** in any way.

- **Impersonating repository:** `Open-Montage/OpenMontage` (hyphenated — note that
  the official org is `calesthio`, not `Open-Montage`).
- It has published a Windows release archive (`OpenMontage-x64.7z` containing
  `OpenMontage-x64.exe`) that behaves like a trojan/loader when executed.
- Microsoft Defender detects the payload as **`Trojan:MSIL/PureRat.ABA!MTB`**.

### Observed behaviour when run

- Fetches a configuration manifest and a token/string from Pastebin.
- Downloads additional `.7z` payloads from an Azure DevOps-hosted endpoint.
- Writes payloads under `C:\Users\Public\...` using system-like folder names.
- Drops/spawns executables such as `serveless.exe`, `cloude_edge.exe`,
  `vsghssl.exe`, `vi_labs.exe`, `ngrok-daemon.exe`, `sqlite-host.exe`,
  `DeltaNet.exe`, `SkyBridge.exe`, `node_ipsec.exe`, `audioconfig.exe`.
- Establishes persistence via `Run` keys and scheduled tasks, and attempts to
  tamper with Microsoft Defender.

### Indicators of compromise (IOCs)

Network indicators are **defanged** below — do not visit them.

| Type | Indicator |
| --- | --- |
| Archive SHA-256 | `5a9844c2cb469e913e2653f644965ba047c0c6a43b0204f568c29b89400ef574` |
| EXE SHA-256 | `d1a7e531176d4345f49ee1cdcb3ad43877623fa26de6a62c3cd05e4624ee8502` |
| Defender signature | `Trojan:MSIL/PureRat.ABA!MTB` |
| C2 / config | `hxxps://pastebin[.]com/raw/kh7qrEqA`, `hxxps://pastebin[.]com/raw/1zM5Xtif` |
| Payload host | `hxxps://dev[.]azure[.]com/sagonbretzpr/...` |
| Persistence (HKCU\...\Run) | `USBController`, `USBHost`, `SyncCoordinator` |
| Persistence (HKLM\...\Run) | `WindowsSystemUpdate` |
| Scheduled tasks | `NgrokUpdateTask*`, `SQLiteUpdateTask*` |

### What to do

- **Only** obtain OpenMontage by cloning the official repository above; never run a
  prebuilt OpenMontage `.exe`.
- If you downloaded or ran the impersonating build: disconnect from the network,
  run a full anti-malware scan, remove the persistence entries and scheduled tasks
  listed above, and **rotate any credentials or API keys** that were present on the
  machine.
- Report the impersonating repository to GitHub via
  <https://github.com/contact/report-abuse>.

_Reference: reported in issue #200._
