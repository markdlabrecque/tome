#!/bin/sh
# #33's attended confirmations, batched. Run as root from a real terminal --
# sudo cannot prompt from inside the Claude Code harness (no TTY).
#
#   sudo ./research/33-attended.sh check      # read-only; safe to re-run
#   sudo ./research/33-attended.sh arm        # installs the reboot probe, then reboot
#   sudo ./research/33-attended.sh readback   # after logging back in; self-cleaning
#
# ponytail: two plists and a text file, not a test harness. The probe answers one
# question -- does anything run before login -- and deletes itself once it has.
set -eu

[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

UID_REAL="${SUDO_UID:-501}"
HOME_REAL="$(dscl . -read "/Users/$(id -un "$UID_REAL")" NFSHomeDirectory | awk '{print $2}')"
PROBE_LOG="$HOME_REAL/.tome-boot-probe.log"
PGDATA=/opt/homebrew/var/postgresql@18
MODELS="$HOME_REAL/.ollama/models"
DAEMON=/Library/LaunchDaemons/dev.tome.bootprobe.plist
AGENT=/Library/LaunchAgents/dev.tome.loginprobe.plist

probe_plist() {  # $1 label, $2 path
	cat > "$2" <<-EOF
		<?xml version="1.0" encoding="UTF-8"?>
		<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
		<plist version="1.0"><dict>
		  <key>Label</key><string>$1</string>
		  <key>RunAtLoad</key><true/>
		  <key>ProgramArguments</key><array>
		    <string>/bin/sh</string><string>-c</string>
		    <string>echo "\$(date -u +%s) $1 uid=\$(id -u)" >> "$PROBE_LOG" 2>/dev/null || true</string>
		  </array>
		</dict></plist>
	EOF
	chown root:wheel "$2"; chmod 644 "$2"
}

case "${1:-check}" in

check)
	echo "=== Background Task Management (item 4.5) ==="
	# The one thing here that genuinely needs root. A LaunchAgent can be switched
	# off from System Settings with no log line anywhere; this is how you see it.
	for L in homebrew.mxcl.ollama homebrew.mxcl.postgresql@18; do
		printf '%s: ' "$L"
		sfltool dumpbtm 2>/dev/null | grep -A6 -F "$L" \
			| grep -m1 -iE 'disposition|disabled|enabled' || echo "NOT PRESENT IN BTM"
	done
	echo
	echo "=== launchd's own view (no root needed, shown for contrast) ==="
	for L in homebrew.mxcl.ollama homebrew.mxcl.postgresql@18; do
		printf '%s: ' "$L"
		launchctl print "gui/$UID_REAL/$L" 2>/dev/null \
			| grep -m1 -E '^\s*state = ' || echo "not loaded"
	done
	echo
	echo "=== Time Machine (items 3.1 / 16) ==="
	tmutil destinationinfo 2>&1 | head -5
	echo "PGDATA excluded:  $(tmutil isexcluded "$PGDATA" 2>&1)"
	echo "models excluded:  $(tmutil isexcluded "$MODELS" 2>&1)"
	echo
	echo "Exclusions are set by 'arm'. They are correct with or without a"
	echo "destination: the backup carries pg_dump output, never PGDATA."
	;;

arm)
	echo "=== Time Machine exclusions (sticky, path-based -- needs root) ==="
	# Correct before a destination exists, so attaching a disk cannot get it wrong.
	for P in "$PGDATA" "$MODELS"; do
		[ -e "$P" ] || { echo "skip (missing): $P"; continue; }
		tmutil addexclusion -p "$P" && echo "excluded: $P"
	done
	echo
	echo "=== Boot-vs-login probe (item 4.6) ==="
	: > "$PROBE_LOG"; chown "$UID_REAL" "$PROBE_LOG"
	probe_plist dev.tome.bootprobe "$DAEMON"
	probe_plist dev.tome.loginprobe "$AGENT"
	launchctl load -w "$DAEMON" 2>/dev/null || true
	echo "installed. Both write to $PROBE_LOG at load."
	echo
	echo "Now REBOOT and log in as usual, then run: sudo $0 readback"
	echo "If macOS shows a background-items notification on reboot, that is"
	echo "item 4.5's silent off-switch making itself visible -- note the wording."
	;;

readback)
	# ponytail: anchor on "{ sec =" -- a greedy .*sec= matches through to "usec"
	# and silently returns microseconds, which reads as a plausible small number.
	BOOT=$(sysctl -n kern.boottime | sed -n 's/.*{ *sec = \([0-9]*\).*/\1/p')
	echo "boot epoch: $BOOT  ($(date -r "$BOOT" -u '+%Y-%m-%dT%H:%M:%SZ'))"
	echo
	if [ -s "$PROBE_LOG" ]; then
		echo "seconds-after-boot  label"
		while read -r TS LABEL _; do
			echo "  +$((TS - BOOT))s  $LABEL"
		done < "$PROBE_LOG"
		echo
		echo "Reading: a daemon line at ~+0s means the Data volume was reachable"
		echo "before login. A daemon line arriving with the agent line means it was"
		echo "not -- so the LaunchDaemon-vs-LaunchAgent choice is moot under"
		echo "FileVault, and 'I rebooted and left it' produces no enrichment."
	else
		echo "PROBE LOG EMPTY -- neither job could write. That is itself the answer:"
		echo "nothing usable runs before login."
	fi
	echo
	echo "=== cleaning up ==="
	launchctl unload -w "$DAEMON" 2>/dev/null || true
	rm -f "$DAEMON" "$AGENT"
	echo "probe removed (log left at $PROBE_LOG for the record)"
	echo
	echo "Re-run 'check' now: a reboot is when Background Task Management is"
	echo "most likely to have quietly disabled something."
	;;

*) echo "usage: $0 {check|arm|readback}" >&2; exit 2 ;;
esac
