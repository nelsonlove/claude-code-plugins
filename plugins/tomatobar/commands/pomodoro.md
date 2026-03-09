---
name: pomodoro
description: Control TomatoBar Pomodoro timer. Subcommands: start, stop, skip, status (default).
argument-hint: "[start|stop|skip|status]"
---

Control the TomatoBar Pomodoro timer.

<$ARGUMENTS>

## Instructions

Parse the argument (default to "status" if empty).

### start / stop
Run: `open tomatobar://startStop`
Report back what you did ("Started timer" or "Stopped timer" — you can check state first to know which).

### skip
Run: `open tomatobar://skipRest`
Report: "Skipped rest, starting next work session."

### status
Parse current state and today's count:

````bash
LOG="$HOME/Library/Containers/com.github.ivoronin.TomatoBar/Data/Library/Caches/TomatoBar.log"

# Current state (idle / work / rest)
STATE=$(grep '"type":"transition"' "$LOG" 2>/dev/null | tail -1 | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['toState'])" 2>/dev/null || echo "unknown")

# Today's completed pomodoros
COUNT=$(grep '"type":"transition"' "$LOG" 2>/dev/null | python3 -c "
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
" 2>/dev/null || echo "0")

echo "State: $STATE"
echo "Pomodoros today: $COUNT"
````

Report the state and count in a friendly one-liner, e.g.:
- "Timer is idle. You've completed 3 pomodoros today."
- "Work session in progress. 5 pomodoros completed today."
- "Rest break in progress. 2 pomodoros completed today."
