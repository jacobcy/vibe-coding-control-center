#!/usr/bin/env python3
"""Test trace functionality across different command tiers."""

import subprocess
import sys

commands = [
    # Skill Layer (3个)
    ("flow show", "Skill Layer"),
    ("flow status", "Skill Layer"),
    ("task show", "Skill Layer"),

    # Shell Layer (5个)
    ("handoff status", "Shell Layer"),
    ("pr show", "Shell Layer"),
    ("pr ready", "Shell Layer"),
    ("inspect symbols", "Shell Layer"),
    ("snapshot show", "Shell Layer"),

    # Infrastructure (2个)
    ("check", "Infrastructure"),
    ("scan", "Infrastructure"),
]

print("Testing trace functionality across 10 commands\n")
print("=" * 80)

for cmd, expected_tier in commands:
    print(f"\n### Test: {cmd} (expected: {expected_tier})")
    print("-" * 80)

    # Run command with --trace
    result = subprocess.run(
        ["uv", "run", "python", "src/vibe3/cli.py"] + cmd.split() + ["--trace"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Check if tier label appears in output
    output = result.stdout + result.stderr
    tier_found = f"[{expected_tier}]" in output
    method_trace_found = "→" in output and "✓" in output

    print(f"Tier label [{expected_tier}]: {'✅' if tier_found else '❌'}")
    print(f"Method traces (→/✓): {'✅' if method_trace_found else '❌'}")

    # Show first few lines of output
    lines = output.split("\n")[:5]
    for line in lines:
        if line.strip():
            print(f"  {line[:100]}")

print("\n" + "=" * 80)
print("Test complete!")
