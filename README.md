# shitty-mouse-scroll-fix

## Background

This all started when I wanted to replace my aging and failing Logitech G602 mouse. It had served me well for years, and I wanted to order another, but alas, it had been discontinued. So started my search for a similar mouse: wireless, six side buttons, adjustable DPI. I found that the Corsair Darkstar Wireless was the only mouse on the market that fit these specifications, so I happily placed an order. Little did I know that this would be the worst $169.99 I had ever spent. The Darkstar has a well-documented issue with the scroll wheel gathering dust and failing to work properly, an issue that I discovered soon after receiving my new mouse in the mail. It would skip, scroll up when I try to scroll down; the whole shebang. This means I have to clear the dust frequently to get any work done, only for the issue to reemerge minutes after I remedy it. That's why I created shitty-mouse-scroll-fix. If you have also fallen victim to the Corsair Darkstar Wireless or similar, save this repo immediately. It will only take one installation to solve all your problems and bring your productivity back to its former glory!

## What it does

A tiny background program (Windows, Python, no dependencies) that watches your scroll wheel and throws out the glitches.

Once you've scrolled **5 ticks in one direction** and keep scrolling, any tick that suddenly goes the *other* way is treated as a dust-induced glitch: it's blocked and replaced with a tick in the direction you were already going. Stop scrolling for **400 ms** and everything resets, so you can still change direction normally by pausing for a moment.

## Install

Requires [Python 3](https://www.python.org/downloads/) (check "Add python.exe to PATH" during setup).

**Double-click `install.bat`.** That's it.

This adds a shortcut to your Startup folder (so it runs every time you log in) and starts it right away. It runs with no window, and only one copy runs at a time. It shows up in Task Manager → Startup apps, where you can disable it.

To stop it and remove it from startup, **double-click `uninstall.bat`**.

> The `.bat` files just run `install.ps1` / `uninstall.ps1` with PowerShell's script restriction bypassed for that one run, since Windows blocks `.ps1` scripts by default.

## Tuning

Pass options to `install.bat` from a terminal (or to `scroll_fix.py` directly):

| Option | Default | Meaning |
| --- | --- | --- |
| `--threshold N` | 5 | Ticks in one direction before reversals get blocked |
| `--timeout MS` | 400 | A pause longer than this ends the scroll and resets everything |
| `--confirm N` | 0 | Accept a reversal mid-scroll after N opposite ticks in a row (0 = only after a pause) |
| `--log FILE` | | Write a log file |
| `-v` | | Log every corrected tick |

For example, `.\install.bat --threshold 3 --timeout 500` is more aggressive. To try settings out first, run `python scroll_fix.py -v` in a terminal and watch the corrections as you scroll (Ctrl+C to quit).

## Limitations

- It can't fix *skipped* ticks (no signal at all), only ticks that go the wrong way.
- A corrected tick can't be replaced inside windows running as administrator unless the fix runs as administrator too. The bad tick is still blocked; it just isn't swapped for a good one.

