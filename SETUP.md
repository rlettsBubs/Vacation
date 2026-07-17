# SETUP.md — 014 fare-scout (one-time bootstrap, Windows / Threadripper)

## 1. Repo

```powershell
mkdir "C:\014 fare-scout"
cd "C:\014 fare-scout"
git init
mkdir data, reports
# drop CLAUDE.md and this file in the root
```

## 2. Chrome with remote debugging (dedicated profile)

Recent Chrome versions require a **non-default** user-data-dir for CDP remote
debugging, so fare-scout gets its own profile. You'll log into Expedia/Riu/etc.
once in this profile and the cookies persist across runs.

Create a shortcut (or `start-chrome.ps1`):

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="C:\014 fare-scout\.chrome-profile"
```

Verify it's listening: open http://127.0.0.1:9222/json/version in any browser —
you should see JSON with a `webSocketDebuggerUrl`.

> Add `.chrome-profile/` to `.gitignore` — it contains cookies/sessions.

## 3. MCP config for Claude Code

In the repo root, `.mcp.json`:

```json
{
  "mcpServers": {
    "chrome": {
      "command": "npx",
      "args": [
        "chrome-devtools-mcp@latest",
        "--browser-url=http://127.0.0.1:9222"
      ]
    }
  }
}
```

Requires Node 20+ (already on the Threadripper). First run will `npx`-fetch the
package. Start Chrome **before** starting Claude Code so the attach succeeds.

Alternative if you prefer Playwright's toolset: `@playwright/mcp` with
`--cdp-endpoint=http://127.0.0.1:9222` attaches to the same Chrome. Same
human-in-the-loop model either way; chrome-devtools-mcp is the default here
because its snapshot/inspect tools are leaner for price extraction.

## 4. Python env

```powershell
cd "C:\014 fare-scout"
python -m venv .venv
.venv\Scripts\activate
# stdlib sqlite3 is enough for Phase 0–3; no packages required yet
```

## 5. First run

1. Launch Chrome via the shortcut (port 9222).
2. `claude` in the repo root.
3. Say: **"Read CLAUDE.md and execute Phase 0."**
4. Approve GO gates as they come. When a captcha or login appears, Claude will
   pause and tell you exactly what to click — do it in the Chrome window, then
   tell it to continue.

## Operating notes

- One run = Phases 1→3, roughly 15–25 minutes with you nearby for the occasional
  captcha. Prices land in `data\FareScout.db`; the report lands in `reports\`.
- Run it morning and evening for a few days before booking — the DB deltas are
  the actual signal.
- If a site blocks the session even in real Chrome (Expedia sometimes will),
  the fallback is fully manual for that source: you navigate, then tell Claude
  "capture this page" and it extracts + logs from the open tab. Still beats
  typing numbers into a spreadsheet.
