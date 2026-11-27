# simply_yt_dwn para Windows (64 bits)

1. Extrae el ZIP completo a una carpeta.
2. Abre simply_yt_dwn.exe.
3. Pega un enlace de YouTube, elige Video o Audio y pulsa Descargar.

Por defecto guarda en Downloads/simply_yt_dwn dentro de tu carpeta de usuario. Puedes cambiar el destino desde la ventana. Los archivos se guardan con el título. Si coincide con un nombre existente, se añade (2), (3), etc. Selecciona una fila para consultar su error o la calidad de origen.

Video produce MP4 (H.264, 1920 × 1080, 60 fps y AAC estéreo). Conserva la proporción con bandas si hace falta y ajusta los fotogramas a 60 fps. Audio produce FLAC de 32 bits enteros a 44,1 kHz. La conversión se hace localmente y el resultado se verifica antes de moverlo al destino.

La carpeta bin contiene yt-dlp, FFmpeg, FFprobe y Deno. Puedes reemplazar yt-dlp.exe con una versión más reciente del proyecto si cambia la extracción en YouTube. Encontrarás el código de simply_yt_dwn en source/simply_yt_dwn.py.

## Dependencias incluidas

- yt-dlp 2026.11.23: https://github.com/yt-dlp/yt-dlp/releases/tag/2026.11.23
- FFmpeg y FFprobe 9.1 essentials: https://www.gyan.dev/ffmpeg/builds/ y https://ffmpeg.org/releases/
- Deno 2.9.8: https://github.com/denoland/deno/releases/tag/v2.9.8
- Python 3.14 y Tcl/Tk, empaquetados con PyInstaller 6.21: https://www.python.org/ y https://pyinstaller.org/

En las listas de reproducción y los Mix de YouTube, selecciona las canciones que quieras excluir, pulsa **Quitar seleccionados** y luego **Descargar selección**. La app sigue descargando mientras convierte un archivo. Convierte uno a la vez, en el orden en que se descargaron.

## Verificación de YouTube

Abre youtube.com en una ventana normal de Firefox e inicia sesión. Completa cualquier verificación allí. En simply_yt_dwn, pulsa **Usar sesión de Firefox** y vuelve a descargar o pulsa **Reintentar fallidos**. Se utiliza el perfil de Firefox que detecta yt-dlp. Como alternativa, **Archivo de sesión** permite seleccionar un archivo Netscape que contenga las cookies de youtube.com. Guarda ese archivo fuera de las carpetas sincronizadas.

## Lista manual

Pulsa **Lista manual**, pega un enlace de YouTube por línea y selecciona **Revisar lista**. Puedes mezclar videos y listas de reproducción. Las listas se expanden en el mismo orden. Quita las filas que no quieras y pulsa **Descargar selección**.

Los títulos públicos se consultan en paralelo. Si un título no está disponible en la vista previa, aparece el enlace y la app intenta recuperar el título durante la descarga.

## Etiquetas musicales

En modo Audio, la app busca la grabación en MusicBrainz por título, artista y duración. Cuando hay una coincidencia clara, incrusta los datos disponibles de la edición en el FLAC. Si la coincidencia es ambigua o el servicio no responde, guarda las etiquetas disponibles del origen. La selección de una edición puede variar según los datos de origen.

Los Mix son listas dinámicas. La vista previa muestra hasta 50 elementos. Para descargar un solo video, usa su enlace sin el parámetro `list`.
