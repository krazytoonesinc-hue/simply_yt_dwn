# simply_yt_dwn

[Español](#español) · [English](#english) · [Windows x64](https://github.com/b3smart/simply_yt_dwn/releases/latest)

## Español

**simply_yt_dwn** es una aplicación portátil para Windows que descarga videos y audio de YouTube y convierte los archivos en tu equipo. Las etiquetas del modo Audio ayudan a organizar una biblioteca personal de música.

### Cómo usar

1. Descarga el ZIP de Windows x64 y extrae todo su contenido en una carpeta.
2. Abre `simply_yt_dwn.exe`. Pulsa **Cambiar carpeta** si quieres elegir dónde guardar los archivos.
3. Pega un enlace de YouTube, elige **Video** o **Audio** y pulsa **Descargar**.
4. Para varios enlaces, abre **Lista manual**, pega uno por línea y pulsa **Revisar lista**. Si pegas una lista de reproducción o un Mix de YouTube en el campo principal, también verás la cola antes de descargar. La vista previa de un Mix muestra hasta 50 elementos.
5. En la vista previa puedes quitar elementos. Pulsa **Descargar selección** para iniciar la cola. Si un elemento falla, selecciona su fila para ver el motivo y usa **Reintentar fallidos** cuando corresponda.

Si YouTube pide verificar tu sesión, inicia sesión en una ventana normal de Firefox y elige **Usar sesión de Firefox** en la app.

### Características

- **Video:** MP4 a 1920 × 1080 y 60 fps, con audio estéreo. Conserva la proporción de la imagen y ajusta la resolución y los fotogramas a ese formato de salida.
- **Audio:** FLAC de 32 bits enteros a 44,1 kHz. Si MusicBrainz identifica la grabación con suficiente claridad, añade las etiquetas disponibles, como artista, álbum, fecha y número de pista.
- **Listas:** acepta un video, una lista de reproducción o una lista manual con un enlace por línea. Puedes revisar la cola y quitar elementos antes de descargar.
- **Descargas en segundo plano:** la cola sigue descargando mientras un archivo se convierte. Puedes reintentar los elementos fallidos.

### Ventajas

- **Portátil:** extrae el ZIP y abre `simply_yt_dwn.exe`, sin instalador.
- **Archivos fáciles de ordenar:** guardados con el título y en la carpeta que elijas.
- **Biblioteca organizada:** las etiquetas quedan dentro del FLAC. Cuando falta una coincidencia fiable, se conservan los datos de origen disponibles.

Descarga el ZIP de [Releases](https://github.com/b3smart/simply_yt_dwn/releases/latest) y consulta la [guía de uso](LEEME.md). Usa la aplicación con contenido que tengas autorización para descargar.

## English

**simply_yt_dwn** is a portable Windows app that downloads YouTube video and audio and converts the files on your computer. Audio tags help organize a personal music library.

### How to use

1. Download the Windows x64 ZIP and extract all its contents into a folder.
2. Run `simply_yt_dwn.exe`. Select **Cambiar carpeta** (Change folder) to choose where files are saved.
3. Paste a YouTube link, choose **Video** or **Audio**, and select **Descargar** (Download).
4. For multiple links, open **Lista manual** (Custom list), paste one link per line, and select **Revisar lista** (Review list). A YouTube playlist or Mix pasted into the main field also opens a preview. A Mix preview lists up to 50 items.
5. Remove any unwanted entries, then select **Descargar selección** (Download selection). If an item fails, select its row to see why and use **Reintentar fallidos** (Retry failed) when appropriate.

If YouTube asks you to verify your session, sign in through a standard Firefox window and select **Usar sesión de Firefox** (Use Firefox session) in the app.

### Features

- **Video:** 1920 × 1080 MP4 at 60 fps with stereo audio. The app preserves the picture's aspect ratio and adjusts resolution and frame rate to the output format.
- **Audio:** 32-bit integer FLAC at 44.1 kHz. When MusicBrainz can reliably identify the recording, the app embeds available tags such as artist, album, date, and track number.
- **Playlists:** paste a video link, a playlist, or a custom list with one URL per line. Review the queue and remove entries before downloading.
- **Background downloads:** the queue keeps downloading while another file is being converted. Failed entries can be retried.

### Benefits

- **Portable:** extract the ZIP and run `simply_yt_dwn.exe`. No installer is required.
- **Easy to organize:** files use their titles and go in the folder you choose.
- **Organized music library:** tags are embedded in the FLAC file. When a reliable match is unavailable, the app keeps the metadata available from the source.

Download the ZIP from [Releases](https://github.com/b3smart/simply_yt_dwn/releases/latest). Use the app with content you are authorized to download.

## Build / Compilar

En Windows x64, usa Python 3.14 con Tcl/Tk y PyInstaller 6.21.0. Coloca yt-dlp, FFmpeg, FFprobe y Deno en `bin/` según [LEEME.md](LEEME.md). Ejecuta `./build.ps1` en PowerShell. El ZIP verificado queda en `dist/`.

On Windows x64, use Python 3.14 with Tcl/Tk and PyInstaller 6.21.0. Put yt-dlp, FFmpeg, FFprobe, and Deno in `bin/` as listed in [LEEME.md](LEEME.md), then run `./build.ps1` in PowerShell. The verified ZIP is written to `dist/`.

Para actualizar / To publish an update: create a new Git tag and attach the ZIP to its GitHub release. Third-party notices are in [licenses/](licenses/).
