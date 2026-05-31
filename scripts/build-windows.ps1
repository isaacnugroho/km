#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if ($env:OS -ne "Windows_NT") {
    throw "build-windows.ps1 must run on Windows (current OS: $($env:OS))"
}

python -m pip install -q -e ".[build]"
$Args = @("--platform", "windows") + $args
& python "$Root\scripts\build-binary.py" @Args
exit $LASTEXITCODE
