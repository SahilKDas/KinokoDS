param([long]$LimitBytes = 200000000)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$total = [long]0
$pending = [Collections.Generic.Stack[string]]::new()
$pending.Push($root)
while ($pending.Count -gt 0) {
    foreach ($entry in Get-ChildItem -LiteralPath $pending.Pop() -Force) {
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Reparse point prevents reliable size accounting: $($entry.FullName)"
        }
        if ($entry.PSIsContainer) { $pending.Push($entry.FullName) }
        else { $total += $entry.Length }
    }
}
Write-Output ("Workspace: {0:N0} bytes / {1:N0} byte limit (includes .git and build)" -f $total, $LimitBytes)
if ($total -ge $LimitBytes) { throw 'Workspace must remain strictly below the limit.' }
if ($total -ge ($LimitBytes * 0.8)) { Write-Warning 'Less than 20% headroom; clean or reduce generated output before further work.' }
