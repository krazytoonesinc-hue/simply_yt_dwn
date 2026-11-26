# simply_yt_dwn

Descargador de YouTube para Windows. Acepta videos, listas de reproducción y listas manuales. El modo Audio guarda FLAC de 32 bits a 44,1 kHz y consulta MusicBrainz para las etiquetas. El modo Video guarda MP4 a 1080p y 60 fps con audio estéreo.

Consulta [LEEME.md](LEEME.md) para usar la app.

## Compilar en Windows

Instala Python 3.14 x64 con Tcl/Tk y PyInstaller 6.21.0. Coloca yt-dlp, FFmpeg, FFprobe y Deno en `bin/` según la guía y ejecuta `./build.ps1` desde PowerShell. El ZIP se genera en `dist/`.

## Publicar una versión

Crea una etiqueta Git para el commit de la versión y adjunta el ZIP generado a una release de esa etiqueta. Utiliza una etiqueta nueva para cada actualización.
