"""Test streaming output from async launcher."""

import subprocess
import time
from pathlib import Path

from vibe3.agents.backends.async_launcher import build_async_shell_command


def test_streaming_output_with_stdbuf():
    """Verify that async commands produce realtime streaming output."""
    # Create a test script that outputs lines with delays
    test_script = Path("/tmp/test_streaming_delay.sh")
    test_script.write_text("""#!/usr/bin/env zsh
echo "Start at $(date +%H:%M:%S)"
for i in {1..5}; do
  echo "Line $i at $(date +%H:%M:%S)"
  sleep 0.3
done
echo "End at $(date +%H:%M:%S)"
""")
    test_script.chmod(0o755)

    # Build async shell command with streaming enabled
    cmd = ["bash", str(test_script)]
    log_path = Path("/tmp/test_streaming_output.log")
    shell = build_async_shell_command(cmd, log_path=log_path, keep_alive_seconds=0)

    # Verify stdbuf is present for line buffering
    assert "stdbuf -oL -eL" in shell, "Should use stdbuf for line buffering"

    # Verify awk uses fflush() for realtime output
    assert "fflush()" in shell, "awk should flush output immediately"

    # Run command and measure timing
    start = time.time()
    proc = subprocess.Popen(
        ["bash", "-c", shell],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    lines = []
    for line in proc.stdout:
        lines.append(line.strip())
        # Each line should arrive within ~0.5s of previous (not buffered until end)
        elapsed = time.time() - start
        print(f"[{elapsed:.2f}s] {line.strip()}")

    proc.wait()
    total_time = time.time() - start

    # Verify output (includes vibe3 async status line)
    assert len(lines) >= 7, f"Expected at least 7 lines, got {len(lines)}"
    assert "Start at" in lines[0]
    assert "Line 5 at" in lines[5]
    assert "End at" in lines[6]

    # Verify timing: should take ~1.5s (5 iterations * 0.3s), not 0s (buffered)
    assert total_time > 1.4, f"Should take ~1.5s with delays, took {total_time:.2f}s"
    assert total_time < 2.5, f"Should complete quickly, took {total_time:.2f}s"

    print(f"\n✅ Streaming test passed! Total time: {total_time:.2f}s")


def test_awk_filter_flushes_output():
    """Verify awk filter includes fflush() for realtime output."""
    from vibe3.agents.backends.async_launcher import build_async_log_filter

    filter_cmd = build_async_log_filter()

    # Should be awk command with fflush
    assert filter_cmd[0] == "awk"
    awk_script = filter_cmd[1]

    # Check for fflush after print
    assert "print; fflush()" in awk_script, "awk should flush after each print"

    # Check for fflush in END block
    assert "fflush()" in awk_script, "awk END block should also flush"

    print("✅ awk filter flushes output correctly")


if __name__ == "__main__":
    test_awk_filter_flushes_output()
    print()
    test_streaming_output_with_stdbuf()
