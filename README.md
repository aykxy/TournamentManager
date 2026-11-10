# Arena Tournament Manager — V2 (PySide6)

This is a **source-based Windows testing release**, not a precompiled Windows executable. It has passed Python syntax checks, but the Windows graphical interface has **not** been runtime-tested in this environment.

## Install once

1. Install Python 3.10 or later from python.org (with the Python launcher enabled).
2. Extract this ZIP to a permanent folder such as `C:\ArenaTournamentManager`.
3. Double-click `run_windows.bat`. On the first run it creates a `.venv` and installs PySide6. Subsequent launches reuse that environment.
4. Optionally run `build_windows.bat` to build a Windows executable (requires PyInstaller; Windows-only).

## Storage and backups

Tournament, player and team data is stored in `%USERPROFILE%\ArenaTournamentManager\tournaments.json` and remains separate from the application. Automatic rolling backups are in `%USERPROFILE%\ArenaTournamentManager\backups`. Back up this folder before moving from an earlier build. The application does not silently migrate or delete your previous database.

**Stream URLs are stored in local JSON without encryption.** Restrict access to the computer and backups; do not share the database. Player DMs must be sent manually in Discord; marking Sent confirms delivery. No Discord self-bot is used.

## Features in this test build

- Official user-provided Arena logo, PySide6 dark interface, separate Tournaments / Players / Teams / Settings pages.
- Tournament creation: multiple calendar dates (DD-MM-YYYY), format dropdown, qualifiers and locked rosters.
- Checklist: developer receipt and file import are separate; optional qualifier tasks; Create Tournament Games before Announce Live.
- Permanent team identity using Arena crew ID when present, name history and a separate roster database.
- Transfer windows: replacement = one change; configurable per-team limit; explicit checkbox + reason required to override.
- Tournament imports (Arena JSON) and Cloudflare stream key TXT, private DM copying, sent tracking, spare keys, admin commands.
- Podium: 1st/2nd/3rd team selection with **both** total team cash and gems rewards.
- Bracket tab with Qt WebEngine view (when supported) and browser fallback.
- Finished tournament editing requires explicit acknowledgement before saving changes; audit log stored locally.
- In-app update checks and an update button, **once a trusted HTTPS update manifest is configured**.

## GitHub Releases updater (V2.2 source candidate)

The packaged Windows application checks the latest published release in `aykxy/TournamentManager` automatically and on demand in Settings. It compares versions, verifies the release ZIP using its published SHA-256 file, and launches `ArenaUpdater.exe` from a temporary location to replace the installed application after it exits. The previous application folder is retained alongside it as `.previous` for rollback. The tournament database remains in `%USERPROFILE%\ArenaTournamentManager` and is not included in release archives.

To build a test ZIP, commit the source files and `.github/workflows/windows-release.yml`, then run the **Build Windows release** workflow manually in GitHub Actions. Download the workflow artifact to test on Windows. Only publish a version tag after verifying the first build and updater end-to-end.

**Important:** Do not overwrite a running installation or extract an update ZIP directly over an existing app. Use the in-app updater once a tested release is published. The updater requires the packaged EXE, not the source-based `.bat` launcher.

## Known limitations

- Bracket HQ embed is unverified inside Qt WebEngine, and **does not** automatically import scores or placements.
- No direct Discord ticket automation or direct Discord DM sending.
- The OBS guide and ticket tasks are manual checklist steps.
- Cloudflare import currently accepts the four-line **TXT format**, not DOCX stream documents.
- Permanent roster changes are made via transfer windows; roster snapshots from previous tournaments remain unchanged.
- There is no account-based access control; explicit confirmations protect against accidental changes, not malicious local access.
- Update install has not been tested on Windows; keep a backup before using it.

## V2.4 development: Backup Manager
Settings → Open Backup Manager lists local backups with validation, creates protected manual backups, exports selected backups, and restores selected backups with confirmation. Restoring automatically creates a pre-restore safety snapshot. Rolling backups retain the latest 25; protected/manual/pre-restore snapshots are not automatically pruned. Tournament deletion, recovery and finished-tournament overrides request protected snapshots. Backups are stored in `~/ArenaTournamentManager/backups` and contain local application data; treat exported copies as sensitive.

**Status:** Python syntax and backup core round-trip tested. Full GUI and Windows executable testing still required.


## V2.5 development changes
- Replaced inconsistent OS-provided navigation icons with locally rendered vector icons, including Settings.
- Protected snapshot required before permanent roster replacement.
- Backup integrity and restore regression tests added under tests/.

Not yet validated as a Windows executable.

## V2.6 development changes
- Overview now opens by default and prioritises active tournaments by earliest scheduled date.
- Each tournament shows preparation progress, missing export/key warnings, and actionable outstanding tasks.
- Outstanding task shortcuts open the corresponding tournament tab (Files, Streams, Bracket, Results, or Checklist).
- Compact competitive snapshot follows operational cards.
- Pure overview calculations are in `overview_logic.py`; tests cover sorting, qualifier tasks, explicit stream-key sent flags, missing dates, and completion status.
- Run tests with `python -m unittest discover -s tests -v`.
- Windows GUI and EXE packaging are not yet validated; keep existing installation unchanged.

## V2.8 team identity reconciliation
- Arena crew IDs are authoritative when present.
- Existing local team records merge into an Arena record only with matching name history, at least two overlapping players and >=50% overlap of the smaller roster, with exactly one matching Arena record.
- Ambiguous records remain untouched and are flagged for review.
- Previous local record is retained in reconciliation history; permanent Arena roster is not overwritten.
- A protected backup is created before startup reconciliation and tournament import.
- This is a development source build; test on a copy of your database before production use.

## V2.14 — Checklist notifications
- Windows system tray reminders and Discord webhook notifications for checklist deadlines.
- 24-hour-before and overdue reminders, with deduplication per tournament/task/due-date/channel.
- Startup outstanding-task summary and settings to enable/disable each channel.
- Discord webhook URL is stored in the local database; treat that file and backups as sensitive.
- The application must remain running for reminders to be sent; missed 24-hour alerts are not backfilled after the due time (overdue alerts are delivered when reopened).
- Windows toast appearance depends on system notification support; a live Windows GUI and Discord delivery test are still required.
