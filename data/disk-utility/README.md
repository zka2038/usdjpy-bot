# disk-utility

Tools for keeping long-running jobs alive on this machine, where the repo and `data/` live on an
external USB drive (`/Volumes/bzk Drive`, exFAT) that has dropped out and been unplugged
mid-fetch. Tracked in git (an exception to `data/*` in `.gitignore`); nothing here is data.

## `fetch_supervisor.sh`: auto-restart for the spec 004 gap-fill fetch

Restarts `scripts/download_gap_fill.py all` within about a minute whenever it exits early, waits
out drive dropouts, and stops for good when `fetch.log` reports `stage 3 complete`. The handoff's
rule is that the fetch is restarted, never abandoned (`handoffs/HANDOFF-2026-11-26-remaining.md` §2);
this applies it unattended. Full behaviour is in the script's header.

```bash
cd "/Volumes/bzk Drive/usdjpy-bot"            # or any checkout that has this folder
bash data/disk-utility/fetch_supervisor.sh start    # copies itself to ~/usdjpy-fetch-supervisor/ and runs there
bash data/disk-utility/fetch_supervisor.sh status   # running?, fetch PIDs, last lines of its log
bash data/disk-utility/fetch_supervisor.sh stop     # stops the watcher only; the fetch keeps running
```

- **Runs from the internal disk** (`~/usdjpy-fetch-supervisor/`, with its own `supervisor.log`), so a
  drive dropout cannot kill it. `status` and `stop` also work from that copy.
- **Never starts a second fetch** while one runs, never contacts Dukascopy itself, and reads nothing
  under `data/tokyo_hours/` except `fetch.log`'s tail (spec 004's blinding).
- At most 6 restarts an hour, then a 15-minute back-off, so a persistent fault cannot thrash.
- **It cannot stop the Mac sleeping on battery** (lid closed): keep the Mac on mains power.
- Tested against a stand-in fetch on a fake tree (restart, PID capture, cap and back-off, drive
  absent, completion, already-running) before first use on 2026-11-27.
