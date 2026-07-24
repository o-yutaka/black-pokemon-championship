param(
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw "管理者権限で実行してください"
}

$wslIpRaw = (wsl.exe sh -lc "hostname -I | awk '{print `$1}'").Trim()
$wslIp = ($wslIpRaw -split '\s+')[0]
if (-not $wslIp) {
  throw "WSL2のIPアドレスを取得できません"
}

$configuration = Get-NetIPConfiguration |
  Where-Object { $_.NetAdapter.Status -eq "Up" -and $_.IPv4DefaultGateway -and $_.IPv4Address } |
  Select-Object -First 1
$windowsIp = $configuration.IPv4Address.IPAddress
if (-not $windowsIp) {
  throw "WindowsのLAN IPアドレスを取得できません"
}

netsh interface portproxy delete v4tov4 listenport=$Port listenaddress=0.0.0.0 2>$null | Out-Null
netsh interface portproxy add v4tov4 listenport=$Port listenaddress=0.0.0.0 connectport=$Port connectaddress=$wslIp | Out-Null

$ruleName = "BLACK Battle Studio Bridge $Port"
Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private | Out-Null

Write-Host ""
Write-Host "BLACK Battle Studio iPhone接続設定 完了" -ForegroundColor Green
Write-Host "WSL2接続先 : $wslIp`:$Port"
Write-Host "iPhone URL : http://$windowsIp`:$Port/" -ForegroundColor Cyan
Write-Host "iPhoneとPCを同じWi-Fiへ接続し、このURLをSafariで開いてください。"
