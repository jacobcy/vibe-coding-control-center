#!/usr/bin/env zsh
# tests/check_help.sh - Verifies that all vibe subcommands support help flags

V_BIN="$(dirname "$0")/../bin/vibe"
FAILED=0

for cmd in doctor check tool keys flow task clean skills alias version help; do
    echo -n "Checking 'vibe $cmd --help'... "
    if $V_BIN "$cmd" --help >/dev/null 2>&1; then
        echo "OK"
    else
        echo "FAIL"
        FAILED=$((FAILED + 1))
    fi
done

if [[ $FAILED -gt 0 ]]; then
    echo "Summary: $FAILED commands failed help check."
    exit 1
else
    echo "Summary: All commands passed help check."
    exit 0
fi
