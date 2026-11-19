$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'Open-Edge.cmd'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'EDGE_LAUNCHER_NOT_FOUND' }
$explorer = Join-Path $env:SystemRoot 'explorer.exe'
Start-Process -FilePath $explorer -ArgumentList ('/select,"{0}"' -f $launcher)
Write-Output 'EDGE_LAUNCHER_REVEAL_REQUESTED'
