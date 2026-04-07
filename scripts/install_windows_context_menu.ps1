$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$sender = Join-Path $appRoot "send_to_baba.py"

if (-not (Test-Path $sender)) {
  throw "Missing sender script: $sender"
}

$pythonw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pythonw) {
  $pythonw = (Get-Command python -ErrorAction SilentlyContinue).Source
}
if (-not $pythonw) {
  throw "Python not found in PATH"
}

$command = "`"$pythonw`" `"$sender`" `"%1`""

$targets = @(
  "HKCU:\Software\Classes\AllFilesystemObjects\shell\SendToBaba",
  "HKCU:\Software\Classes\Directory\shell\SendToBaba"
)

foreach ($t in $targets) {
  New-Item -Path $t -Force | Out-Null
  New-ItemProperty -Path $t -Name "MUIVerb" -Value "Send to BABA" -PropertyType String -Force | Out-Null
  New-ItemProperty -Path $t -Name "Icon" -Value "$pythonw,0" -PropertyType String -Force | Out-Null
  $cmdKey = "$t\command"
  New-Item -Path $cmdKey -Force | Out-Null
  Set-Item -Path $cmdKey -Value $command
}

Write-Host "Installed Windows context menu: Send to BABA"
Write-Host "Command: $command"
