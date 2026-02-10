#!/usr/bin/env zsh
line='test_key = "test_value"'
if [[ "$line" =~ ^[[:space:]]*([a-zA-Z0-9_-]+)[[:space:]]*=[[:space:]]*(.*)[[:space:]]*$ ]]; then
    echo "Match found"
    echo "Key: ${match[1]}"
    echo "Value: ${match[2]}"
else
    echo "No match"
fi
