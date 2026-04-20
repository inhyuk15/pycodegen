#!/usr/bin/env bash
# Restore tmp_backup_*.py files to their original names.
# tmp_backup_ contains the ORIGINAL content (pre-modification),
# and the non-prefixed file is the broken/modified version.
# So we move tmp_backup_* → original to recover.

set -euo pipefail

SOURCE_ROOT="${1:-/home/ihkang/ttt/pycodegen/DevEval/Source_Code}"

count=0
fail=0
while IFS= read -r -d '' tmp; do
    dir=$(dirname "$tmp")
    base=$(basename "$tmp")
    orig="${dir}/${base#tmp_backup_}"
    if mv -f "$tmp" "$orig" 2>/dev/null; then
        count=$((count + 1))
    else
        fail=$((fail + 1))
        echo "FAILED: $tmp"
    fi
done < <(find "$SOURCE_ROOT" -name "tmp_backup_*.py" -print0)

# Also clean up stray tmp_*.py (from pass_k_verbose.py)
tmp_count=0
while IFS= read -r -d '' tmp; do
    dir=$(dirname "$tmp")
    base=$(basename "$tmp")
    # Only "tmp_xxx.py" without "backup"
    if [[ "$base" == tmp_backup_* ]]; then continue; fi
    orig="${dir}/${base#tmp_}"
    if mv -f "$tmp" "$orig" 2>/dev/null; then
        tmp_count=$((tmp_count + 1))
    fi
done < <(find "$SOURCE_ROOT" -name "tmp_*.py" -print0)

# Remove stale lock files
lock_count=0
while IFS= read -r -d '' lock; do
    rm -f "$lock" && lock_count=$((lock_count + 1))
done < <(find "$SOURCE_ROOT" -name ".eval.lock" -print0)

echo "Restored $count tmp_backup_*.py files ($fail failures)"
echo "Restored $tmp_count tmp_*.py files"
echo "Removed $lock_count stale lock files"
