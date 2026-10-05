$exe = "C:\Users\zizek\Documents\iRacing-AI-Cinematic-Studio\dist\iRacingCinematicStudio.exe"
$workdir = "C:\Users\zizek\Documents\iRacing-AI-Cinematic-Studio\dist"
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop "iRacing Cinematic Studio.lnk"

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = $exe
$s.WorkingDirectory = $workdir
$s.Description = "iRacing AI Cinematic Studio"
$s.IconLocation = "$exe,0"
$s.Save()

Write-Output "Atajo creado: $lnk"
