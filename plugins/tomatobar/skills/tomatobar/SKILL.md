---
name: tomatobar
description: "Query and control TomatoBar Pomodoro timer. Use when the user mentions Pomodoro, focus sessions, work/rest timer, or asks about their current TomatoBar state."
---

# TomatoBar

TomatoBar is a macOS menu bar Pomodoro timer. It exposes a URL scheme for control and a JSON log for state.

## Ensure running

Before any control or state query, check if TomatoBar is running:

```bash
if ! pgrep -x TomatoBar >/dev/null; then
  open -a TomatoBar
  sleep 2
fi
```

## Control

```bash
open tomatobar://startStop   # start or stop the timer
open tomatobar://skipRest    # skip the current rest, begin next work session
```

Or use the `/pomodoro` command:
- `/pomodoro start` / `/pomodoro stop`
- `/pomodoro skip`
- `/pomodoro status`

## Reading State

**Log file:**
```
~/Library/Containers/com.github.ivoronin.TomatoBar/Data/Library/Caches/TomatoBar.log
```

Each line is a JSON event. Two event types:
- `appstart` — app launched
- `transition` — state changed: has `event`, `fromState`, `toState`

**States:** `idle`, `work`, `rest`
**Events:** `startStop` (manual), `timerFired` (session completed), `skipRest` (manual skip)

**Current state** = `toState` of the last `transition` line.
**Completed pomodoro** = `timerFired` transition where `fromState == "work"`.

### State check snippet

```bash
LOG="$HOME/Library/Containers/com.github.ivoronin.TomatoBar/Data/Library/Caches/TomatoBar.log"
grep '"type":"transition"' "$LOG" 2>/dev/null | tail -1 | python3 -c "import sys,json; e=json.loads(sys.stdin.read()); print(e['toState'], e['timestamp'])" 2>/dev/null || echo "unknown"
```

### Today's pomodoro count

```bash
grep '"type":"transition"' "$LOG" | python3 -c "
import sys, json, datetime
count = 0
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try:
        e = json.loads(line)
        ts = datetime.datetime.fromtimestamp(e['timestamp'])
        if ts.date() == datetime.date.today() and e.get('event') == 'timerFired' and e.get('fromState') == 'work':
            count += 1
    except Exception:
        pass
print(count)
"
```

## Contextual guidance

- If the user seems distracted or is asking for help mid-session, check state and note how long they've been in the current session if useful.
- A typical Pomodoro is 25 minutes work / 5 minutes rest.
- After 4 pomodoros, a longer break (15–30 min) is recommended.
