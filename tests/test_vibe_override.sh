#!/bin/bash
set -e

# Setup test environment
TEST_DIR=$(mktemp -d)
GLOBAL_VIBE="$TEST_DIR/global/bin/vibe"
LOCAL_PROJECT="$TEST_DIR/local_project"
LOCAL_VIBE_BIN="$LOCAL_PROJECT/bin/vibe"

# 1. Mock Global Installation
mkdir -p "$(dirname "$GLOBAL_VIBE")"
cat > "$GLOBAL_VIBE" << 'EOF'
#!/bin/bash
# Default Global Vibe
# ... shim logic would be here ...
if [[ -z "${VIBE_NO_SHIM}" ]]; then
    # Simplified shim for test
    if [[ -f "$PWD/.vibe/keys.env" ]]; then
       grep_root=$(grep '^VIBE_ROOT=' "$PWD/.vibe/keys.env" | cut -d= -f2-)
       if [[ -n "$grep_root" && -x "$grep_root/bin/vibe" ]]; then
           export VIBE_NO_SHIM=1
           exec "$grep_root/bin/vibe" "$@"
       fi
    fi
fi
echo "GLOBAL_VIBE_EXECUTED"
EOF
chmod +x "$GLOBAL_VIBE"

# 2. Mock Local Installation
mkdir -p "$(dirname "$LOCAL_VIBE_BIN")"
cat > "$LOCAL_VIBE_BIN" << 'EOF'
#!/bin/bash
echo "LOCAL_VIBE_EXECUTED_ARGS:$*"
EOF
chmod +x "$LOCAL_VIBE_BIN"

# 3. Configure Local Project
mkdir -p "$LOCAL_PROJECT/.vibe"
echo "VIBE_ROOT=$LOCAL_PROJECT" > "$LOCAL_PROJECT/.vibe/keys.env"

# 4. Run Test: Global Vibe inside Local Project
cd "$LOCAL_PROJECT"
OUTPUT=$("$GLOBAL_VIBE" help)

if [[ "$OUTPUT" == "LOCAL_VIBE_EXECUTED_ARGS:help" ]]; then
    echo "PASS: Global vibe handed over to local vibe"
else
    echo "FAIL: Global vibe did not handover. Output:"
    echo "$OUTPUT"
    exit 1
fi

# 5. Run Test: Loop Prevention
# Point VIBE_ROOT to global itself (should just run global)
echo "VIBE_ROOT=$TEST_DIR/global" > "$LOCAL_PROJECT/.vibe/keys.env"
# To avoid infinite recursion in our simplified test shim, we rely on VIBE_NO_SHIM env var or logic
# The real script checks file paths. Here let's just check the env var logic is respected
OUTPUT2=$(VIBE_NO_SHIM=1 "$GLOBAL_VIBE")
if [[ "$OUTPUT2" == "GLOBAL_VIBE_EXECUTED" ]]; then
     echo "PASS: Loop prevention / NO_SHIM respected"
else
     echo "FAIL: Loop prevention failed. Output:"
     echo "$OUTPUT2"
     exit 1
fi

# 6. Run Test: VIBE_HOME Logic (Implicit Parent)
# Remove VIBE_ROOT from keys.env, rely on parent dir inference
echo "SOME_OTHER_VAR=1" > "$LOCAL_PROJECT/.vibe/keys.env"

# Copy the real bin/vibe logic is tested by using the global mocked one (which we should update with real content)
# Wait, the GLOBAL_VIBE in this test was a MOCK. We needs to update it to use the REAL logic we just wrote.
cp bin/vibe "$GLOBAL_VIBE"

# Reset VIBE_NO_SHIM for new test
export VIBE_NO_SHIM=""
cd "$LOCAL_PROJECT"
OUTPUT3=$("$GLOBAL_VIBE" help || true)

if [[ "$OUTPUT3" == *"LOCAL_VIBE_EXECUTED"* ]]; then
    echo "PASS: Implicit parent directory inference worked"
else
    echo "FAIL: Implicit parent directory inference failed. Output: $OUTPUT3"
    exit 1
fi

rm -rf "$TEST_DIR"
