param(
  [string]$SshTarget = "ubuntu@145.239.65.130",
    [string]$IdentityFile = "$env:USERPROFILE\.ssh\id_ed25519_server",
    [int[]]$Ports = @(8001, 8002, 8003, 8004)
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $IdentityFile)) {
    throw "SSH identity file not found: $IdentityFile"
}

$portsJoined = ($Ports -join ' ')

$remoteScript = @'
set -e

echo "--- docker port mappings ---"
for p in __PORTS__; do
  echo "PORT $p"
  docker ps --format '{{.ID}}\t{{.Names}}\t{{.Ports}}' | grep "0.0.0.0:${p}->" || echo "(no mapping)"
done

echo ""
echo "--- container artifact fingerprints ---"
for p in __PORTS__; do
  c=$(docker ps --format '{{.Names}}\t{{.Ports}}' | awk -v p="$p" '$0 ~ "0.0.0.0:"p"->" {print $1; exit}')
  echo "PORT $p CONTAINER ${c:-<none>}"
  if [ -n "${c:-}" ]; then
    echo "compose.project=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$c" 2>/dev/null || true)"
    echo "compose.working_dir=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' "$c" 2>/dev/null || true)"
    docker exec "$c" sh -lc 'echo "index.html:"; sha256sum /usr/share/nginx/html/index.html; echo "assets:"; ls -1 /usr/share/nginx/html/assets 2>/dev/null | head -n 10 || true'
  fi
done

echo ""
echo "--- http response hashes (GET /) ---"
for p in __PORTS__; do
  echo "PORT $p"
  # Quick fingerprinting headers
  curl -sS -I "http://127.0.0.1:${p}/" | head -n 12 | tr -d '\r' || true
  # Hash the body
  curl -fsSL "http://127.0.0.1:${p}/" | sha256sum | awk '{print $1}'
done

echo ""
echo "--- generated source file hashes (if present) ---"
for root in /opt/thesisapp /app; do
  if [ -d "$root/generated/apps" ]; then
    echo "ROOT $root"
    for f in \
      "$root/generated/apps/anthropic_claude-3-haiku/app1/frontend/src/pages/UserPage.jsx" \
      "$root/generated/apps/anthropic_claude-3-haiku/app2/frontend/src/pages/UserPage.jsx" \
      "$root/generated/apps/anthropic_claude-3-5-haiku/app3/frontend/src/pages/UserPage.jsx" \
      "$root/generated/apps/anthropic_claude-3-5-haiku/app4/frontend/src/pages/UserPage.jsx" \
      "$root/generated/apps/anthropic_claude-3-haiku/app1/frontend/src/App.jsx" \
      "$root/generated/apps/anthropic_claude-3-haiku/app2/frontend/src/App.jsx" \
      "$root/generated/apps/anthropic_claude-3-5-haiku/app3/frontend/src/App.jsx" \
      "$root/generated/apps/anthropic_claude-3-5-haiku/app4/frontend/src/App.jsx" \
      "$root/generated/apps/anthropic_claude-3-haiku/app1/backend/routes/user.py" \
      "$root/generated/apps/anthropic_claude-3-haiku/app2/backend/routes/user.py" \
      "$root/generated/apps/anthropic_claude-3-5-haiku/app3/backend/routes/user.py" \
      "$root/generated/apps/anthropic_claude-3-5-haiku/app4/backend/routes/user.py" \
      "$root/generated/apps/anthropic_claude-3-haiku/app1/backend/app.py" \
      "$root/generated/apps/anthropic_claude-3-haiku/app2/backend/app.py" \
      "$root/generated/apps/anthropic_claude-3-5-haiku/app3/backend/app.py" \
      "$root/generated/apps/anthropic_claude-3-5-haiku/app4/backend/app.py" \
      ; do
      if [ -f "$f" ]; then
        sha256sum "$f" | awk '{print $1"  "$2}'
      else
        echo "MISSING $f"
      fi
    done
  fi
done
'@

$remoteScript = $remoteScript.Replace('__PORTS__', $portsJoined)

$remoteScript = $remoteScript.Replace("`r", "")

$tmp = New-TemporaryFile
try {
  # Ensure UTF-8 without BOM; also ensure the script ends with a newline
  $content = $remoteScript
  if (-not $content.EndsWith("`n")) { $content += "`n" }
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($tmp.FullName, $content, $utf8NoBom)
  $sshCmd = 'ssh -i "' + $IdentityFile + '" ' + $SshTarget + ' bash -s < "' + $tmp.FullName + '"'
  cmd /c $sshCmd
}
finally {
  Remove-Item -LiteralPath $tmp.FullName -Force -ErrorAction SilentlyContinue
}
