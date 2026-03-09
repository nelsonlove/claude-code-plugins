# tomatobar

Claude Code plugin for [TomatoBar](https://github.com/ivoronin/TomatoBar), a macOS menu bar Pomodoro timer.

## Prerequisites

- TomatoBar installed (available as `cask "tomatobar"` in Homebrew or from the Mac App Store)
- TomatoBar must have been launched at least once (to create its log file)

## Commands

### `/pomodoro [subcommand]`

| Subcommand | Action |
|------------|--------|
| `status` (default) | Show current timer state and today's pomodoro count |
| `start` | Start the timer |
| `stop` | Stop the timer |
| `skip` | Skip the current rest break |

## Skill

The `tomatobar` skill gives Claude awareness of your Pomodoro state. Claude will automatically use it when you mention Pomodoro, focus sessions, or your work/rest timer.
