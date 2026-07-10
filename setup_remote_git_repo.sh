#!/usr/bin/env bash
set -euo pipefail

ROOT="${TEAM_WS_ROOT:-/home/johnteller/team_ws}"
BRANCH="${GIT_BRANCH:-main}"
GIT_USER_NAME="${GIT_USER_NAME:-RenTA Upgrade Bot}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-renta-upgrade@local}"
MOVE_NESTED_GIT="${MOVE_NESTED_GIT:-true}"
MAX_FILE_MB="${MAX_FILE_MB:-95}"

cd "$ROOT"

echo "[1/8] root=$ROOT"
if [ ! -d sds ] || [ ! -d th ] || [ ! -d wyl ]; then
  echo "ERR: expected sds/th/wyl under $ROOT" >&2
  exit 1
fi

STAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p _archive

if [ "$MOVE_NESTED_GIT" = "true" ]; then
  ARCHIVE="$ROOT/_archive/nested_git_before_root_repo_$STAMP"
  mkdir -p "$ARCHIVE"
  echo "[2/8] archive nested .git dirs -> $ARCHIVE"
  { find . -mindepth 2 -name .git -type d 2>/dev/null || true; } | sort > "$ARCHIVE/nested_git_paths.txt"
  while IFS= read -r gitdir; do
    [ -n "$gitdir" ] || continue
    rel="${gitdir#./}"
    dest="$ARCHIVE/${rel//\//__}"
    echo "  move $rel -> ${dest#$ROOT/}"
    mv "$gitdir" "$dest"
  done < "$ARCHIVE/nested_git_paths.txt"
else
  echo "[2/8] skip nested .git archival"
fi

echo "[3/8] write .gitignore"
cat > .gitignore <<'EOF'
# Secrets and local env
.env
.env.*
!.env.example
**/.env
**/.env.*
!**/.env.example
*.pem
*.key
*.csr
*.p12
*.pfx
id_rsa*
id_ed25519*

# Python runtime/dependencies/cache
**/.venv/
**/venv/
**/.py312deps/
**/__pycache__/
**/*.py[cod]
**/.pytest_cache/
**/.mypy_cache/
**/.ruff_cache/
**/.coverage

# Node/frontend dependencies/build cache
**/node_modules/
**/.vite/
**/.cache/
**/dist/.vite/

# Logs, PID, runtime data
server_logs/
**/logs/
*.log
*.log.*
*.pid
*.pid.*
server_inventory.md

# Database and runtime volumes
sds/runtime/
**/runtime/
*.db
*.sqlite
*.sqlite3
*.sqlite-journal
*.sqlite-wal
*.sqlite-shm
sds/ca-server/agent_ca.db
sds/challenge-server/challenges/
sds/testwork/
sds/registry-server/tmp_upload/

# Uploads/generated task runs/reports
th/mode_router/platform_task_runs/
th/mode_router/reports/
th/mode_router/literature_runs/
yhl/runs/
travel_runs/

# Backups/archive/temp
_archive/
**/backups/
*_backups/
*.bak
*.bak.*
*.tgz
*.tar
*.tar.gz
*.zip
*.7z
*.rar

# Tool/editor/system files
.DS_Store
Thumbs.db
*.swp
*.swo
.vscode/
.idea/

# Nested git metadata archived before root repo init; do not commit nested repo internals
**/.git/
EOF

if [ ! -d .git ]; then
  echo "[4/8] git init"
  git init -b "$BRANCH"
else
  echo "[4/8] root git already exists"
fi

git config user.name "$GIT_USER_NAME"
git config user.email "$GIT_USER_EMAIL"

echo "[5/8] git add source baseline"
git add .

echo "[6/8] check staged large files > ${MAX_FILE_MB}MB"
large_file_report="/tmp/renta_git_large_files_$STAMP.txt"
: > "$large_file_report"
git diff --cached --name-only -z | while IFS= read -r -d '' f; do
  if [ -f "$f" ]; then
    size=$(wc -c < "$f" | tr -d ' ')
    limit=$((MAX_FILE_MB * 1024 * 1024))
    if [ "$size" -gt "$limit" ]; then
      printf '%s %s\n' "$size" "$f" >> "$large_file_report"
    fi
  fi
done
if [ -s "$large_file_report" ]; then
  echo "ERR: staged files exceed ${MAX_FILE_MB}MB; adjust .gitignore or Git LFS before GitHub push:" >&2
  sort -nr "$large_file_report" >&2
  exit 2
fi

echo "[7/8] commit baseline if needed"
if git diff --cached --quiet; then
  echo "No staged changes to commit."
else
  git commit -m "chore: capture remote baseline before ACPs v2.1 upgrade"
fi

echo "[8/8] summary"
git status --short
git log --oneline --decorate -n 3 || true
cat <<EOF

Next GitHub push step, after creating a PRIVATE repo:
  git remote add origin <GITHUB_PRIVATE_REPO_URL>
  git push -u origin $BRANCH

Use SSH deploy key or a fine-scoped token; do not store broad personal credentials on this server.
EOF
