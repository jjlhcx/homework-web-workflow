. (Join-Path $PSScriptRoot 'runtime.ps1')
$pythonRuntime = Get-CxPython
& $pythonRuntime (Join-Path $PSScriptRoot 'cx.py') @args
exit $LASTEXITCODE
