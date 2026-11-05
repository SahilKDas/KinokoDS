param([switch]$WithoutROM, [switch]$Hidden, [switch]$Wait)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
& (Join-Path $PSScriptRoot 'check-size.ps1')
$emuDir = Join-Path $root 'local/melonDS'
$config = Join-Path $emuDir 'portable/melonDS.toml'
if (!(Test-Path -LiteralPath $config)) { throw 'Missing local portable configuration' }
if (Get-Process -Name melonDS -ErrorAction SilentlyContinue | Where-Object Path -EQ (Join-Path $emuDir 'melonDS.exe')) {
    throw 'This repo melonDS is already running; close it before starting another instance.'
}
$oldTemp = $env:TEMP
$oldTmp = $env:TMP
try {
    $env:TEMP = Join-Path $emuDir 'portable/tmp'
    $env:TMP = $env:TEMP
    $startArgs = @{
        FilePath = (Join-Path $emuDir 'melonDS.exe')
        WorkingDirectory = $emuDir
        WindowStyle = $(if ($Hidden) { 'Hidden' } else { 'Normal' })
        PassThru = $true
    }
    if (!$WithoutROM) {
        $rom = Join-Path $root 'local/roms/Mario Kart DS.nds'
        if (!(Test-Path -LiteralPath $rom)) { throw 'Missing local ROM' }
        $startArgs.ArgumentList = '"' + $rom + '"'
    }
    $process = Start-Process @startArgs
    Write-Output "Started melonDS (PID $($process.Id)); portable data: $emuDir/portable"
    if ($Wait) { $process.WaitForExit() }
} finally {
    $env:TEMP = $oldTemp
    $env:TMP = $oldTmp
}
