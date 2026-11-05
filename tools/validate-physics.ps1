param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $root
$env:TEMP = Join-Path $root 'build/tmp'
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
function Invoke-Python([string[]]$Arguments) {
    & python -B @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python validation failed: $Arguments" }
}
& "$PSScriptRoot/check-size.ps1"
if (!$SkipBuild) {
    & cmake --build --preset dev
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
}
& ctest --preset dev
if ($LASTEXITCODE -ne 0) { throw 'CTest failed' }
Invoke-Python @('-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py')
foreach ($script in @('audit_sync.py', 'inspect_longitudinal.py', 'inspect_frame.py',
                      'validate_longitudinal.py', 'validate_movement.py', 'validate_grounded_drive.py')) {
    Invoke-Python @("tools/$script")
}
foreach ($scenario in @('idle', 'straight', 'left', 'right', 'brake', 'reverse', 'drift-left', 'drift-right')) {
    Invoke-Python @('tools/trace_physics_offline.py', '--dispatch', '--scenario', $scenario)
}
$trace = Join-Path $root 'local/validation/frame-inspection/offline-dispatch-trace.json'
$first = (Get-FileHash -LiteralPath $trace -Algorithm SHA256).Hash
Invoke-Python @('tools/trace_physics_offline.py', '--dispatch')
$second = (Get-FileHash -LiteralPath $trace -Algorithm SHA256).Hash
if ($first -ne $second) { throw 'Repeated dispatcher trace differs' }
@{ dispatcher_repeat_sha256 = $second; identical = $true } | ConvertTo-Json |
    Set-Content -LiteralPath (Join-Path $root 'local/validation/frame-inspection/repeat-validation.json') -Encoding utf8
& "$PSScriptRoot/check-size.ps1"
Write-Output 'All bounded offline physics checks passed. Hardware frame timing and full C++ physics coverage remain pending.'
