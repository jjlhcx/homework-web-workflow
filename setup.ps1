param([string]$PythonPath)
. (Join-Path $PSScriptRoot 'runtime.ps1')
try { $pythonRuntime = Get-CxPython -PythonPath $PythonPath } catch {
    Write-Output $_.Exception.Message
    exit 2
}
& $pythonRuntime (Join-Path $PSScriptRoot 'setup_deps.py')
exit $LASTEXITCODE
