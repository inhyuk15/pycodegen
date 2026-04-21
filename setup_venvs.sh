#!/usr/bin/env bash
# Setup per-repo virtual environments for DevEval Source_Code.
#
# Each repo gets its own venv under DevEval/.venvs/<repo_name>/ that
# inherits packages from the currently-active conda env
# (--system-site-packages). Then "pip install -e ." installs the repo
# and its declared dependencies into that venv.
#
# Parallel install via xargs -P. Failed installs are logged to
# setup_venvs_failed.txt and their venv is removed.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$SCRIPT_DIR/DevEval/Source_Code"
VENV_BASE="$SCRIPT_DIR/DevEval/.venvs"
LOG_OK="$SCRIPT_DIR/setup_venvs_ok.txt"
LOG_FAIL="$SCRIPT_DIR/setup_venvs_failed.txt"
PARALLEL="${PARALLEL:-8}"

mkdir -p "$VENV_BASE"
: > "$LOG_OK"
: > "$LOG_FAIL"

setup_one() {
    local repo_dir="$1"
    local repo_name
    repo_name=$(basename "$repo_dir")
    local venv_path="$VENV_BASE/$repo_name"

    # Skip if already set up.
    if [ -f "$venv_path/.install_ok" ]; then
        echo "[skip] $repo_name"
        echo "$repo_name" >> "$LOG_OK"
        return
    fi

    # Need setup.py or pyproject.toml.
    if [ ! -f "$repo_dir/setup.py" ] && [ ! -f "$repo_dir/pyproject.toml" ]; then
        echo "[no-setup] $repo_name"
        echo "$repo_name : no setup.py / pyproject.toml" >> "$LOG_FAIL"
        return
    fi

    rm -rf "$venv_path"
    python -m venv --system-site-packages "$venv_path" 2>/dev/null || {
        echo "[venv-fail] $repo_name"
        echo "$repo_name : venv creation failed" >> "$LOG_FAIL"
        return
    }

    # Install the repo (and its deps) into the venv.
    if (cd "$repo_dir" && "$venv_path/bin/pip" install -e . --quiet --no-build-isolation 2>&1) > "$venv_path/install.log"; then
        touch "$venv_path/.install_ok"
        echo "[ok] $repo_name"
        echo "$repo_name" >> "$LOG_OK"
    else
        echo "[install-fail] $repo_name (see $venv_path/install.log)"
        echo "$repo_name" >> "$LOG_FAIL"
        # Keep the venv so we can inspect install.log
    fi
}

export -f setup_one
export VENV_BASE LOG_OK LOG_FAIL

# Find all repos
repos=()
while IFS= read -r repo; do
    repos+=("$repo")
done < <(find "$SOURCE_ROOT" -maxdepth 2 -mindepth 2 -type d | sort)

echo "=== Found ${#repos[@]} repos. Installing with parallelism=$PARALLEL ==="

# Run in parallel
printf '%s\n' "${repos[@]}" | xargs -I{} -P "$PARALLEL" bash -c 'setup_one "$@"' _ {}

echo ""
echo "=== Summary ==="
echo "OK:     $(wc -l < $LOG_OK) repos"
echo "FAILED: $(wc -l < $LOG_FAIL) repos"
echo ""
echo "Failed list (in $LOG_FAIL):"
cat "$LOG_FAIL"
