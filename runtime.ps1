$ErrorActionPreference = 'Stop'
function Get-CxPython([string]$PythonPath) {
    $candidates = @()
    $aliases = @()
    if ($env:CX_PYTHON) { $candidates += $env:CX_PYTHON }
    $savedRuntime = Join-Path $PSScriptRoot '.python-runtime'
    if (Test-Path -LiteralPath $savedRuntime -PathType Leaf) {
        $remembered = Get-Content -LiteralPath $savedRuntime -Encoding UTF8 -TotalCount 1
        if ($remembered -and [IO.Path]::IsPathRooted($remembered)) { $candidates += $remembered }
    }
    $candidates += (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')
    foreach ($name in @('python','python3','py')) {
        foreach ($found in (Get-Command $name -All -CommandType Application -ErrorAction SilentlyContinue)) {
            if ($found.Source -match '\\WindowsApps\\') { $aliases += $found.Source }
            else { $candidates += $found.Source }
        }
    }
    foreach ($key in @('HKCU:\Software\Python','HKLM:\Software\Python','HKLM:\Software\WOW6432Node\Python')) {
        foreach ($install in (Get-Item -Path "$key\*\*\InstallPath" -ErrorAction SilentlyContinue)) {
            $executable = $install.GetValue('ExecutablePath')
            $directory = $install.GetValue('')
            if ($executable) { $candidates += $executable }
            elseif ($directory) { $candidates += (Join-Path $directory 'python.exe') }
        }
    }
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA 'Python\bin\python.exe')
        foreach ($relativeRoot in @('Programs\Python','Python')) {
            $installRoot = Join-Path $env:LOCALAPPDATA $relativeRoot
            foreach ($install in (Get-ChildItem -LiteralPath $installRoot -Directory -Filter 'Python*' -ErrorAction SilentlyContinue)) {
                $candidates += (Join-Path $install.FullName 'python.exe')
            }
        }
    }
    $candidates += $aliases
    if ($PythonPath) {
        if (-not [IO.Path]::IsPathRooted($PythonPath)) {
            throw 'PYTHON_PATH_INVALID: -PythonPath needs the full path to python.exe.'
        }
        $candidates = @($PythonPath)
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $launchArgs = @()
        if ([IO.Path]::GetFileNameWithoutExtension($candidate) -eq 'py') { $launchArgs += '-3' }
        $launchArgs += @('-c','import sys; sys.exit(1) if sys.version_info < (3,10) else print(sys.executable)')
        try {
            $resolved = & $candidate @launchArgs 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved -and (Test-Path -LiteralPath ([string]$resolved))) {
                return [string]$resolved
            }
        } catch { continue }
    }
    if ($PythonPath) { throw 'PYTHON_PATH_INVALID: the specified executable is not a working Python 3.10+.' }
    throw 'PYTHON_MISSING: if Python is already installed, run setup.ps1 -PythonPath with its executable path.'
}
$env:PYTHONIOENCODING = 'utf-8'
