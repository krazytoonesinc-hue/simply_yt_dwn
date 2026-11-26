$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

foreach ($name in 'yt-dlp', 'ffmpeg', 'ffprobe', 'deno') {
    if (!(Test-Path -LiteralPath "bin/$name.exe" -PathType Leaf)) {
        throw "Falta bin/$name.exe. Consulta LEEME.md para preparar las dependencias."
    }
}

$icon = (Resolve-Path 'source/ytdwn.ico').Path
python -m PyInstaller --noconfirm --onedir --windowed --name simply_yt_dwn --icon $icon --add-data "${icon}:." source/simply_yt_dwn.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller no pudo generar el ejecutable.' }

$package = 'dist/simply_yt_dwn'
foreach ($name in '_tcl_data', '_tk_data') {
    $directory = Join-Path "$package/_internal" $name
    if (!(Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory | Out-Null
        New-Item -ItemType File -Path "$directory/.embedded" | Out-Null
    }
}
Copy-Item -LiteralPath bin,source,licenses -Destination $package -Recurse -Force
Copy-Item -LiteralPath LEEME.md -Destination $package -Force
tar.exe -a -cf dist/simply_yt_dwn-Windows-x64.zip -C dist simply_yt_dwn
if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar el ZIP.' }
python -m zipfile -t dist/simply_yt_dwn-Windows-x64.zip
if ($LASTEXITCODE -ne 0) { throw 'El ZIP no pasó la verificación.' }
