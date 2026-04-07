$ErrorActionPreference = "SilentlyContinue"

$targets = @(
  "HKCU:\Software\Classes\AllFilesystemObjects\shell\SendToBaba",
  "HKCU:\Software\Classes\Directory\shell\SendToBaba"
)

foreach ($t in $targets) {
  Remove-Item -Path $t -Recurse -Force
}

Write-Host "Removed Windows context menu: Send to BABA"
