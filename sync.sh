#!/bin/bash
# Sync: local → git → build → FTP
# Usage: bash /Users/abbas/Projects/GameOS/PMF/sync.sh "commit message"

set -e
cd "/Users/abbas/Projects/GameOS/PMF"
MSG="${1:-update}"

echo "=== 1. Git push ==="
export PATH="/opt/homebrew/bin:$PATH"
git add -A
git commit -m "$MSG" || echo "(nothing to commit)"
git push origin main 2>/dev/null && echo "pushed" || echo "(push skipped — no remote or offline)"

echo "=== 2. Build frontend ==="
cd web
npm run build

echo "=== 3. FTP upload ==="
D="dist"
U="abbas@llamagriffin.com:Y0r3kJ3st3r"
SRV="ftp://ftp.bakatron.com/game-os/PMF"

# Ensure API dirs exist
mkdir -p "$D/api/v1"

# .htaccess
echo 'RewriteEngine On
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule ^(.*)$ index.php [QSA,L]' > "$D/api/v1/.htaccess"

# PHP (restore from backup after Vite cleans dist)
cp "../api-backup/v1/index.php" "$D/api/v1/index.php" && echo "  ✓ PHP restored from backup"

# Upload
for f in $(find "$D" -type f); do
  remote="${f#$D/}"
  curl -s --ftp-create-dirs -T "$f" "$SRV/$remote" --user "$U" > /dev/null && echo "  ✓ $remote" || echo "  ✗ $remote"
done

echo "=== Done ==="
