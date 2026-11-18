param([string]$PythonPath)
. (Join-Path $PSScriptRoot 'runtime.ps1')
try { $pythonRuntime = Get-CxPython -PythonPath $PythonPath } catch {
    $code = if ($PythonPath) { 'PYTHON_PATH_INVALID' } else { 'PYTHON_MISSING' }
    @{ok=$false;error=$code;next='Reuse an existing Python 3.10+ with setup.ps1 -PythonPath <full path to python.exe>; install Python only if none is available.'} | ConvertTo-Json -Compress
    exit 2
}
& $pythonRuntime (Join-Path $PSScriptRoot 'setup_deps.py') --check
$dependenciesReady = $LASTEXITCODE -eq 0
try {
    & $pythonRuntime -c "import sys; sys.path.insert(0,sys.argv[1]); import cx; cx.browser_command('https://i.chaoxing.com/base','http://127.0.0.1:9222')" $PSScriptRoot 2>$null
    $edgeReady = $LASTEXITCODE -eq 0
} catch { $edgeReady = $false }
@{ok=($dependenciesReady -and $edgeReady);python=$pythonRuntime;dependencies=$dependenciesReady;edge=$edgeReady;browser_started=$false} | ConvertTo-Json -Compress
if (-not $dependenciesReady) { exit 3 }
if (-not $edgeReady) { exit 4 }
exit 0
