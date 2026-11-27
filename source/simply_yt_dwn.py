from concurrent.futures import ThreadPoolExecutor
import ctypes
from fractions import Fraction
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk
import unicodedata
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(sys.executable if getattr(sys, "frozen", False) else __file__).parent
APP_NAME = "simply_yt_dwn"
APP_DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
SETTINGS = APP_DATA / APP_NAME / "settings.json"
OLD_SETTINGS = APP_DATA / "ytdwn" / "settings.json"
BG, PANEL, LINE = "#161718", "#202224", "#35383b"
INK, MUTED, ACCENT, ERROR = "#f3f0ea", "#adb1b4", "#ffab73", "#ff9390"
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
FIREFOX_SESSION = object()


def tool(name):
    local = ROOT / "bin" / (name + ".exe")
    return str(local) if local.is_file() else shutil.which(name)


def youtube_url(value):
    try:
        parsed = urlsplit(value.strip())
        query = parse_qs(parsed.query)
        host = parsed.hostname
        if parsed.scheme not in ("http", "https") or host not in {
            "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"
        }:
            raise ValueError
        playlist = query.get("list", [""])[0]
        parts = parsed.path.strip("/").split("/")
        video = query.get("v", [""])[0] if parts == ["watch"] else ""
        if host == "youtu.be" or (len(parts) == 2 and parts[0] in {"shorts", "live", "embed"}):
            video = parts[-1]
        if re.fullmatch(r"[A-Za-z0-9_-]+", playlist):
            if playlist.startswith("RD") and VIDEO_ID.fullmatch(video):
                return "https://www.youtube.com/watch?" + urlencode({"v": video, "list": playlist, "start_radio": 1})
            return "https://www.youtube.com/playlist?" + urlencode({"list": playlist})
        if VIDEO_ID.fullmatch(video):
            return "https://www.youtube.com/watch?v=" + video
    except ValueError:
        pass
    raise ValueError("Pega un enlace válido de YouTube.")


def manual_urls(text):
    urls = []
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip():
            try:
                urls.append(youtube_url(line))
            except ValueError as exc:
                raise ValueError(f"Línea {number}. {exc}") from exc
    if not urls:
        raise ValueError("Pega al menos un enlace de YouTube.")
    return tuple(urls)


def public_title(url):
    endpoint = "https://www.youtube.com/oembed?" + urlencode({"url": url, "format": "json"})
    try:
        with urlopen(endpoint, timeout=4) as response:
            title = json.load(response).get("title")
            return title if isinstance(title, str) and title.strip() else url
    except (OSError, ValueError):
        return url


def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = value[:100].strip(" .") or "Sin título"
    if re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]",
                    value.split(".", 1)[0].rstrip(), re.IGNORECASE):
        return "_" + value
    return value


def youtube_session(path):
    with path.open(encoding="utf-8-sig") as file:
        header = file.readline().strip()
        if header not in {"# Netscape HTTP Cookie File", "# HTTP Cookie File"}:
            raise ValueError("Selecciona un archivo cookies.txt en formato Netscape.")
        records = []
        for line in file:
            fields = line.rstrip("\r\n").split("\t")
            domain = fields[0].removeprefix("#HttpOnly_").lstrip(".").lower()
            if len(fields) == 7 and (domain == "youtube.com" or domain.endswith(".youtube.com")):
                records.append("\t".join(fields))
        if not records:
            raise ValueError("El archivo no contiene cookies de youtube.com.")
    return "\n".join([header, *records, ""])


def music_key(value):
    plain = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in plain if char.isalnum())


class MusicBrainz:
    def __init__(self, cancel):
        self.cancel = cancel
        self.last_request = None

    def get(self, resource, **params):
        delay = 0 if self.last_request is None else max(0, 1.05 - (time.monotonic() - self.last_request))
        if self.cancel.wait(delay):
            raise Cancelled
        self.last_request = time.monotonic()
        request = Request("https://musicbrainz.org/ws/2/" + resource + "?" + urlencode({"fmt": "json", **params}),
                          headers={"User-Agent": "simply_yt_dwn/1.0 (Windows home music library tagger)"})
        try:
            with urlopen(request, timeout=4) as response:
                return json.load(response)
        except (OSError, ValueError):
            return {}

    def tags(self, info, fallback):
        title = info.get("track") or ""
        artist = info.get("artist") or ", ".join(info.get("artists") or [])
        if not title or not artist:
            parts = re.split(r"\s+[-–—]\s+", info.get("title") or fallback, maxsplit=1)
            if len(parts) == 2:
                artist = artist or parts[0]
                title = title or re.sub(
                    r"\s*[\[(](?:official (?:music )?video|official audio|lyric video|audio oficial|video oficial)[\])]\s*$",
                    "", parts[1], flags=re.IGNORECASE)
        tags = {"title": info.get("track") or info.get("title") or fallback}
        for key in ("artist", "album", "album_artist", "track_number", "disc_number", "release_date"):
            if info.get(key):
                tags[{"track_number": "TRACKNUMBER", "disc_number": "DISCNUMBER",
                      "album_artist": "ALBUMARTIST", "release_date": "date"}.get(key, key)] = info[key]
        duration = info.get("duration")
        if not title or not artist or not isinstance(duration, (int, float)) or not 0 < duration < 86400:
            return tags, False

        def quote(value):
            return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'

        milliseconds = round(duration * 1000)
        window = f"[{max(0, milliseconds - 5000)} TO {milliseconds + 5000}]"
        search = self.get("recording", query=f"recording:{quote(title)} AND artist:{quote(artist)} AND dur:{window}",
                          limit=25)
        matches = []
        for recording in search.get("recordings", []):
            credit = self.credit(recording)
            length = recording.get("length")
            if (credit and music_key(credit) == music_key(artist)
                    and music_key(recording["title"]) == music_key(title)
                    and isinstance(length, int) and abs(length - duration * 1000) <= 5000):
                releases = self.releases(recording, info.get("album"))
                matches.append((not bool(releases), abs(length - duration * 1000), recording, releases))
        matches.sort(key=lambda match: match[:2])
        if not matches or (len(matches) > 1 and matches[0][0] == matches[1][0]
                           and matches[1][1] - matches[0][1] < 1500):
            return tags, False
        _, _, recording, releases = matches[0]
        tags.update(title=recording["title"], artist=self.credit(recording),
                    MUSICBRAINZ_TRACKID=recording["id"])
        if releases:
            release = releases[0]
            tags.update(album=release["title"], MUSICBRAINZ_ALBUMID=release["id"])
            if release.get("date"):
                tags["date"] = release["date"]
            details = self.get("release/" + release["id"], inc="recordings+artist-credits")
            album_artist = self.credit(details)
            if album_artist:
                tags["ALBUMARTIST"] = album_artist
            for disc in details.get("media", []):
                for track in disc.get("tracks", []):
                    if track.get("recording", {}).get("id") == recording["id"]:
                        tags.update(TRACKNUMBER=track["number"], DISCNUMBER=disc["position"],
                                    MUSICBRAINZ_RELEASETRACKID=track["id"])
                        return tags, True
        return tags, True

    @staticmethod
    def credit(entry):
        return "".join(credit["name"] + credit.get("joinphrase", "")
                       for credit in entry.get("artist-credit", []))

    @staticmethod
    def releases(recording, album):
        candidates = []
        for release in recording.get("releases", []):
            group = release.get("release-group", {})
            if release.get("status") != "Official":
                continue
            if album:
                if music_key(album) == music_key(release["title"]):
                    candidates.append(release)
            elif group.get("primary-type") in {"Album", "Single", "EP"} and not group.get("secondary-types"):
                if release.get("date"):
                    candidates.append(release)
        return sorted(candidates, key=lambda release: (release.get("date", "9999"), release["id"]))


def encode_args(source, output, mode, tags=None):
    args = ["-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
    if mode == "audio":
        args += ["-map", "0:a:0", "-c:a", "flac", "-ar", "44100", "-sample_fmt", "s32",
                 "-bits_per_raw_sample", "32", "-strict", "experimental"]
        if tags:
            args += ["-map_metadata", "-1"]
            for key, value in tags.items():
                args += ["-metadata", f"{key}={value}"]
    else:
        args += ["-map", "0:v:0", "-map", "0:a:0", "-vf",
                 "scale=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2:reset_sar=1,"
                 "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=60",
                 "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "320k", "-ac", "2", "-movflags", "+faststart"]
    return ["-progress", "pipe:1", "-nostats", *args, str(output)]


def verify_streams(streams, mode):
    audio = next((s for s in streams if s["codec_type"] == "audio"), {})
    if mode == "audio":
        return (audio.get("codec_name"), audio.get("sample_rate"), audio.get("bits_per_raw_sample")) == (
            "flac", "44100", "32")
    video = next((s for s in streams if s["codec_type"] == "video"), {})
    return (video.get("codec_name"), video.get("width"), video.get("height"),
            video.get("avg_frame_rate"), audio.get("channels")) == ("h264", 1920, 1080, "60/1", 2)


class Cancelled(Exception):
    pass


class Worker:
    def __init__(self, events, preview_playlists=False):
        self.events = events
        self.preview_playlists = preview_playlists
        self.cancel = threading.Event()
        self.musicbrainz = MusicBrainz(self.cancel)
        self.process = None
        self.converter = None
        self.lock = threading.Lock()

    def emit(self, *event):
        self.events.put(event)

    def stop(self):
        with self.lock:
            self.cancel.set()
            if self.process is not None and self.process.poll() is None:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                if self.process.poll() is None:
                    self.process.kill()
        if self.converter is not None:
            self.converter.stop()

    def run(self, args, on_line=None, capture=False):
        # Keep diagnostics separate so JSON output stays valid.
        with tempfile.TemporaryFile() as errors:
            with self.lock:
                if self.cancel.is_set():
                    raise Cancelled
                self.process = process = subprocess.Popen(
                    args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errors,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            lines = []
            try:
                with process.stdout:
                    for line in process.stdout:
                        if capture:
                            lines.append(line)
                        if on_line:
                            on_line(line.strip())
                status = process.wait()
            finally:
                with self.lock:
                    self.process = None
            if self.cancel.is_set():
                raise Cancelled
            if status:
                errors.seek(0)
                detail = errors.read().decode("utf-8", "replace").strip().splitlines()
                if any("Sign in to confirm" in line for line in detail):
                    raise RuntimeError("YouTube pide verificar la sesión. Inicia sesión en Firefox y activa «Usar sesión de Firefox».")
                if any("could not find firefox cookies database" in line.lower() for line in detail):
                    raise RuntimeError("Abre Firefox e inicia sesión en youtube.com en una ventana normal antes de reintentar.")
                raise RuntimeError(detail[-1] if detail else f"El comando terminó con código {status}.")
            return "".join(lines)

    def __call__(self, url, mode, folder, retry=None, session=None):
        try:
            if session is FIREFOX_SESSION:
                self.process_job(url, mode, folder, retry, ["--cookies-from-browser", "firefox"])
                return
            if session is None:
                self.process_job(url, mode, folder, retry, [])
                return
            with tempfile.TemporaryDirectory(prefix=f"{APP_NAME}-session-") as temp:
                jar = Path(temp) / "cookies.txt"
                jar.write_text(session, encoding="utf-8")
                self.process_job(url, mode, folder, retry, ["--cookies", str(jar)])
        except OSError as exc:
            self.emit("done", str(exc))

    def process_job(self, url, mode, folder, retry, auth):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            ytdlp, ffmpeg, ffprobe = (tool(name) for name in ("yt-dlp", "ffmpeg", "ffprobe"))
            runtime = tool("deno") or tool("node")
            if not all((ytdlp, ffmpeg, ffprobe, runtime)):
                raise RuntimeError("Faltan yt-dlp, FFmpeg, FFprobe o un motor JavaScript en la carpeta bin.")
            engine = "deno" if Path(runtime).stem.lower() == "deno" else "node"
            common = [ytdlp, "--ignore-config", "--no-color", "--socket-timeout", "25",
                      "--js-runtimes", f"{engine}:{runtime}", "--ffmpeg-location", str(Path(ffmpeg).parent), *auth]
            if retry is None:
                if isinstance(url, tuple):
                    title, playlist = "Lista manual", True
                    entries = self.read_manual(common, url)
                else:
                    title, playlist, entries = self.read_listing(common, url)
                items = [(index, *entry) for index, entry in enumerate(entries, 1)]
                if playlist and self.preview_playlists:
                    self.emit("preview", title, items)
                    return
                self.emit("listing", title, items)
            else:
                items = retry
            self.converter = Worker(self.events)
            self.converter.cancel = self.cancel
            self.converter.musicbrainz = self.musicbrainz
            with tempfile.TemporaryDirectory(prefix=f".{APP_NAME}-", dir=folder) as staging:
                with ThreadPoolExecutor(max_workers=1) as conversions:
                    pending = []
                    for item in items:
                        if self.cancel.is_set():
                            raise Cancelled
                        temp = Path(staging) / str(item[0])
                        try:
                            if isinstance(item[3], str) and retry is not None and VIDEO_ID.fullmatch(item[2].removeprefix("https://www.youtube.com/watch?v=")):
                                _, _, recovered = self.read_listing(common, item[2])
                                item = (item[0], *recovered[0])
                            temp.mkdir()
                            source = self.download(common, mode, temp, item)
                            if item[2].startswith("https://www.youtube.com/watch?"):
                                info_file = temp / "source.info.json"
                                if info_file.is_file():
                                    title = json.loads(info_file.read_text(encoding="utf-8")).get("title")
                                    if title:
                                        item = (item[0], item[1], title, item[3])
                                        self.emit("title", item[0], title)
                        except (RuntimeError, ValueError, OSError) as exc:
                            shutil.rmtree(temp, ignore_errors=True)
                            self.emit("row", item[0], "Falló", str(exc))
                            continue
                        self.emit("row", item[0], "En cola de conversión", "")
                        pending.append(conversions.submit(
                            self.converter.convert_item, ffmpeg, ffprobe, mode, folder, item, source))
                    for conversion in pending:
                        conversion.result()
            if self.cancel.is_set():
                raise Cancelled
            self.emit("done", "")
        except Cancelled:
            self.emit("done", "Descarga cancelada.")
        except (RuntimeError, ValueError, OSError) as exc:
            self.emit("done", str(exc))

    def read_manual(self, common, urls):
        singles = "https://www.youtube.com/watch?v="
        entries = []
        with ThreadPoolExecutor(max_workers=6) as lookups:
            titles = {url: lookups.submit(public_title, url)
                      for url in dict.fromkeys(urls) if VIDEO_ID.fullmatch(url.removeprefix(singles))}
            try:
                for index, url in enumerate(urls, 1):
                    if self.cancel.is_set():
                        raise Cancelled
                    if url in titles:
                        entries.append((url.removeprefix(singles), titles[url].result(), False))
                    else:
                        try:
                            _, _, playlist = self.read_listing(common, url)
                        except (RuntimeError, ValueError, OSError) as exc:
                            entries.append(("", url, str(exc)))
                        else:
                            entries.extend(playlist)
                    self.emit("reading", index, len(urls))
            finally:
                for future in titles.values():
                    future.cancel()
        return entries

    def read_listing(self, common, url):
        list_id = parse_qs(urlsplit(url).query).get("list", [""])[0]
        mix_limit = ["--playlist-end", "50"] if list_id.startswith("RD") else []
        listing = json.loads(self.run([*common, "--flat-playlist", *mix_limit, "--dump-single-json", "--", url],
                                      capture=True) or "{}") or {}
        entries = listing.get("entries")
        playlist = entries is not None
        if list_id and not playlist:
            raise RuntimeError("YouTube no devolvió la lista de reproducción. Vuelve a intentarlo.")
        if entries is None and listing.get("id"):
            entries = [listing]
        if not entries:
            raise RuntimeError("YouTube no devolvió elementos para este enlace.")
        entries = [entry or {} for entry in entries]
        items = [(entry.get("id", ""), entry.get("title") or "Sin título", playlist) for entry in entries]
        return listing.get("title") or ("Lista de reproducción" if playlist else "Descargas"), playlist, items

    def download(self, common, mode, temp, item):
        index, video_id, title, issue = item
        if isinstance(issue, str):
            raise RuntimeError(issue)
        if not VIDEO_ID.fullmatch(video_id):
            raise ValueError("YouTube no devolvió un identificador válido.")
        self.emit("row", index, "Descargando", "")

        def download_progress(line):
            if line.startswith("D|"):
                percent = line[2:].strip()
                if re.fullmatch(r"\d+(?:\.\d+)?%", percent):
                    self.emit("row", index, "Descargando · " + percent, "")
        selection = "bestaudio/best" if mode == "audio" else "bestvideo*+bestaudio/best"
        metadata = ["--write-info-json"] if mode == "audio" or title.startswith("https://www.youtube.com/watch?") else []
        self.run([*common, "--no-playlist", "--no-simulate", "--no-warnings", "--progress", "--newline",
                  *metadata,
                  "--progress-template", "download:D|%(progress._percent_str)s",
                  "--merge-output-format", "mkv", "-f", selection, "-o", "source.%(ext)s",
                  "-P", str(temp), "--", "https://www.youtube.com/watch?v=" + video_id], download_progress)
        sources = [p for p in temp.iterdir() if p.name.startswith("source.") and p.name.count(".") == 1]
        if len(sources) != 1:
            raise RuntimeError("No se encontró la pista descargada.")
        return sources[0]

    def convert_item(self, ffmpeg, ffprobe, mode, folder, item, source):
        index, _, title, _ = item
        try:
            if self.cancel.is_set():
                return
            self.emit("row", index, "Convirtiendo", "")
            detail = self.convert(ffmpeg, ffprobe, mode, folder, title, source)
        except Cancelled:
            return
        except (RuntimeError, ValueError, OSError) as exc:
            self.emit("row", index, "Falló", str(exc))
        else:
            self.emit("row", index, "Guardado", detail)
        finally:
            shutil.rmtree(source.parent, ignore_errors=True)

    def convert(self, ffmpeg, ffprobe, mode, folder, title, source):
        temp = source.parent
        probe_args = [ffprobe, "-v", "error", "-show_streams", "-of", "json"]
        original = json.loads(self.run([*probe_args, str(source)], capture=True))["streams"]
        track = next((s for s in original if s["codec_type"] == mode), {})
        if mode == "video" and track.get("avg_frame_rate", "0/0") != "0/0":
            fps = float(Fraction(track["avg_frame_rate"]))
            source_info = f"Origen · {track['width']} × {track['height']} · {fps:g} fps"
        else:
            source_info = f"Origen · {track.get('codec_name', 'desconocido').upper()}"
        extension = "flac" if mode == "audio" else "mp4"
        converted = temp / ("final." + extension)
        tags = None
        if mode == "audio":
            info_path = temp / "source.info.json"
            info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.is_file() else {}
            tags, matched = self.musicbrainz.tags(info, title)
            source_info += " · Etiquetas de MusicBrainz" if matched else " · Etiquetas de origen"
        self.run([ffmpeg, *encode_args(source, converted, mode, tags)])
        probe = self.run([*probe_args, str(converted)], capture=True)
        if not verify_streams(json.loads(probe)["streams"], mode):
            raise RuntimeError("El archivo convertido no cumple las especificaciones de salida.")
        stem = safe_name(title)
        with self.lock:
            if self.cancel.is_set():
                raise Cancelled
            target = folder / f"{stem}.{extension}"
            suffix = 2
            while True:
                try:
                    converted.rename(target)
                    break
                except FileExistsError:
                    target = folder / f"{stem} ({suffix}).{extension}"
                    suffix += 1
        return source_info


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.worker = None
        self.preview = False
        self.items = []
        self.states = {}
        self.errors = {}
        self.finished = 0
        self.job = None
        self.session_data = None
        self.closing = False
        self.mode = "video"
        try:
            settings_path = SETTINGS if SETTINGS.is_file() else OLD_SETTINGS
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            settings = {}
        self.folder = Path(settings.get("folder") or (Path.home() / "Downloads" / APP_NAME))
        root.title(APP_NAME)
        root.geometry("880x620")
        root.minsize(710, 510)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)

        shell = tk.Frame(root, bg=BG)
        shell.pack(fill="both", expand=True, padx=32, pady=26)
        header = tk.Frame(shell, bg=BG)
        header.pack(fill="x", pady=(0, 22))
        self.label(header, APP_NAME, size=29, bold=True).pack(side="left")
        self.session_button = self.button(header, "Usar sesión de Firefox", self.toggle_firefox)
        self.session_button.pack(side="right", pady=(9, 0))
        self.file_session_button = self.button(header, "Archivo de sesión", self.choose_session)
        self.file_session_button.pack(side="right", padx=(0, 6), pady=(9, 0))
        self.label(shell, "Enlace de YouTube", bold=True).pack(anchor="w", pady=(0, 7))
        field = tk.Frame(shell, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        field.pack(fill="x")
        self.url = tk.Entry(field, bg=PANEL, fg=INK, insertbackground=INK, relief="flat",
                            font=("Segoe UI", 13), selectbackground="#805334")
        self.url.pack(side="left", fill="x", expand=True, padx=13, ipady=11)
        self.button(field, "Pegar", self.paste, bg=PANEL).pack(side="right", padx=4)
        self.url.bind("<Return>", lambda event: self.start() if self.worker is None else None)
        options = tk.Frame(shell, bg=BG)
        options.pack(fill="x", pady=(12, 20))
        self.video = self.button(options, "Video", lambda: self.select_mode("video"))
        self.audio = self.button(options, "Audio", lambda: self.select_mode("audio"))
        self.video.pack(side="left", padx=(0, 4))
        self.audio.pack(side="left")
        self.format = self.label(options, "", fg=MUTED, size=10)
        self.format.pack(side="left", padx=12)
        self.go = self.button(options, "Descargar ↓", self.start, bg=ACCENT, fg=BG)
        self.go.pack(side="right")
        self.manual = self.button(options, "Lista manual", self.open_manual)
        self.manual.pack(side="right", padx=(0, 8))
        self.select_mode("video")

        queue_header = tk.Frame(shell, bg=BG)
        queue_header.pack(fill="x", pady=(0, 8))
        self.heading = self.label(queue_header, "Cola", size=15, bold=True)
        self.heading.pack(side="left")
        self.count = self.label(queue_header, "0 archivos", fg=MUTED)
        self.count.pack(side="right")
        self.remove_items = self.button(queue_header, "Quitar seleccionados", self.remove_selected)
        self.cancel_preview = self.button(queue_header, "Descartar lista", self.discard_preview)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Queue.Treeview", background=PANEL, fieldbackground=PANEL, foreground=INK,
                        rowheight=32, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Queue.Treeview.Heading", background="#2a2c2e", foreground=MUTED,
                        relief="flat", font=("Segoe UI", 9))
        style.map("Queue.Treeview", background=[("selected", "#3f3831")], foreground=[("selected", INK)])
        box = tk.Frame(shell, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        box.pack(fill="both", expand=True)
        self.rows = ttk.Treeview(box, columns=("number", "title", "state"), show="headings", height=4,
                                 style="Queue.Treeview", selectmode="extended")
        for key, label, width, stretch in (("number", "N.º", 54, False), ("title", "Archivo", 360, True),
                                           ("state", "Estado", 170, False)):
            self.rows.heading(key, text=label, anchor="w")
            self.rows.column(key, width=width, minwidth=width, stretch=stretch)
        style.configure("Queue.Vertical.TScrollbar", background="#484b4e", troughcolor=PANEL,
                        bordercolor=PANEL, lightcolor="#484b4e", darkcolor="#484b4e", arrowcolor=MUTED)
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.rows.yview,
                               style="Queue.Vertical.TScrollbar")
        self.rows.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.rows.pack(fill="both", expand=True)
        self.empty = self.label(box, "Pega un enlace para empezar", bg=PANEL, fg=MUTED)
        self.empty.place(relx=.5, rely=.56, anchor="center")
        self.rows.bind("<<TreeviewSelect>>", self.show_detail)
        self.rows.bind("<Delete>", self.remove_selected)
        self.rows.tag_configure("failed", foreground=ERROR)
        self.rows.tag_configure("active", foreground=ACCENT)

        line = tk.Frame(shell, bg=BG)
        line.pack(fill="x", pady=(7, 8))
        self.status = self.label(line, "", fg=MUTED, size=10, wraplength=580, justify="left")
        self.status.pack(side="left", fill="x", expand=True)
        self.retry = self.button(line, "Reintentar fallidos", self.retry_failed)
        footer = tk.Frame(shell, bg=BG, highlightbackground=LINE, highlightthickness=1)
        footer.pack(fill="x")
        self.button(footer, "Cambiar carpeta", self.choose_folder).pack(side="right", padx=5, pady=4)
        self.button(footer, "Abrir", self.open_folder).pack(side="right", padx=(5, 0), pady=4)
        self.destination = self.label(footer, "", fg=MUTED, size=10)
        self.destination.pack(side="left", padx=11)
        self.folder_label()
        self.url.focus_set()
        root.after(75, self.poll)

    def label(self, parent, text, size=11, fg=INK, bg=BG, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=bg, fg=fg, anchor="w",
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kwargs)

    def button(self, parent, text, callback, bg="#2a2c2e", fg=INK):
        return tk.Button(parent, text=text, command=callback, bg=bg, fg=fg, activebackground="#54504b"
                         if fg != BG else "#ffc098", activeforeground=fg, disabledforeground="#818487",
                         relief="flat", cursor="hand2", padx=13, pady=6, font=("Segoe UI", 10, "bold"),
                         highlightthickness=1, highlightbackground=LINE)

    def paste(self):
        try:
            value = self.root.clipboard_get()
        except tk.TclError:
            return
        self.url.delete(0, "end")
        self.url.insert(0, value.strip())
        self.url.focus_set()

    def select_mode(self, mode):
        self.mode = mode
        self.video.configure(bg="#504035" if mode == "video" else "#2a2c2e")
        self.audio.configure(bg="#504035" if mode == "audio" else "#2a2c2e")
        self.format.configure(text="MP4  ·  1080p / 60 fps  ·  Estéreo" if mode == "video"
                              else "FLAC  ·  32 bits / 44,1 kHz")

    def folder_label(self):
        path = str(self.folder)
        self.destination.configure(text="Destino  ·  " + (path if len(path) < 59 else "…" + path[-57:]))

    def toggle_firefox(self):
        if self.session_data is FIREFOX_SESSION:
            self.session_data = None
            self.status.configure(text="Sesión retirada.", fg=MUTED)
        else:
            self.session_data = FIREFOX_SESSION
            self.status.configure(text="Inicia sesión en youtube.com en una ventana normal de Firefox y vuelve a intentar.", fg=MUTED)
        self.update_session_buttons()

    def update_session_buttons(self):
        firefox = self.session_data is FIREFOX_SESSION
        self.session_button.configure(text="Quitar sesión de Firefox" if firefox else "Usar sesión de Firefox")
        self.file_session_button.configure(text="Quitar archivo" if isinstance(self.session_data, str) else "Archivo de sesión")

    def choose_session(self):
        if isinstance(self.session_data, str):
            self.session_data = None
            self.update_session_buttons()
            self.status.configure(text="Sesión retirada.", fg=MUTED)
            return
        path = filedialog.askopenfilename(title="Seleccionar cookies de YouTube",
                                         filetypes=[("Archivo de cookies", "*.txt"), ("Todos", "*.*")])
        if not path:
            return
        try:
            self.session_data = youtube_session(Path(path))
        except (ValueError, OSError) as exc:
            self.status.configure(text=str(exc), fg=ERROR)
            return
        self.update_session_buttons()
        self.status.configure(text="Sesión cargada para la próxima descarga.", fg=MUTED)

    def choose_folder(self):
        folder = filedialog.askdirectory(initialdir=str(self.folder if self.folder.exists() else self.folder.parent))
        if folder:
            self.folder = Path(folder)
            self.folder_label()
            try:
                SETTINGS.parent.mkdir(parents=True, exist_ok=True)
                SETTINGS.write_text(json.dumps({"folder": folder}), encoding="utf-8")
            except OSError:
                self.status.configure(text="La carpeta se aplicó durante esta sesión.")

    def open_folder(self):
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            os.startfile(self.folder)
        except OSError as exc:
            self.status.configure(text=str(exc))

    def start(self):
        if self.preview:
            if self.items:
                self.job = (self.job[0], self.mode, self.folder)
                self.end_preview()
                self.begin(self.items)
            return
        if self.worker:
            self.request_cancel()
            return
        try:
            url = youtube_url(self.url.get())
        except ValueError as exc:
            self.status.configure(text=str(exc), fg=ERROR)
            return
        self.load_urls(url)

    def open_manual(self):
        if self.worker or self.preview:
            return
        dialog = tk.Toplevel(self.root, bg=BG)
        dialog.title("Lista manual")
        dialog.transient(self.root)
        dialog.resizable(True, True)
        dialog.minsize(480, 270)
        body = tk.Frame(dialog, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=16)
        self.label(body, "Pega un enlace de YouTube por línea.", bold=True).pack(anchor="w", pady=(0, 8))
        links = tk.Text(body, width=68, height=8, wrap="word", background=PANEL, foreground=INK,
                        insertbackground=INK, relief="flat", padx=9, pady=7, font=("Segoe UI", 11))
        links.pack(fill="both", expand=True)
        error = self.label(body, "", fg=ERROR, wraplength=420, justify="left")
        error.pack(fill="x", pady=(5, 2))

        def review():
            try:
                urls = manual_urls(links.get("1.0", "end-1c"))
            except ValueError as exc:
                error.configure(text=str(exc))
                return
            dialog.destroy()
            self.load_urls(urls)

        controls = tk.Frame(body, bg=BG)
        controls.pack(fill="x")
        self.button(controls, "Revisar lista", review, bg=ACCENT, fg=BG).pack(side="right")
        self.button(controls, "Cerrar", dialog.destroy).pack(side="right", padx=(0, 8))
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.grab_set()
        links.focus_set()

    def load_urls(self, url):
        self.items, self.states, self.errors = [], {}, {}
        self.finished = 0
        self.rows.delete(*self.rows.get_children())
        self.heading.configure(text="Cola")
        self.count.configure(text="0 archivos")
        self.empty.configure(text="Leyendo los enlaces…" if isinstance(url, tuple) else "Leyendo el enlace…")
        self.empty.place(relx=.5, rely=.56, anchor="center")
        self.job = (url, self.mode, self.folder)
        self.begin()

    def begin(self, retry=None):
        self.retry.pack_forget()
        self.manual.configure(state="disabled")
        self.status.configure(text="Preparando descarga…", fg=MUTED)
        self.go.configure(text="Cancelar", state="normal")
        self.worker = Worker(self.events, preview_playlists=True)
        threading.Thread(target=self.worker, args=(*self.job, retry, self.session_data), daemon=True).start()

    def request_cancel(self):
        self.go.configure(text="Cancelando…", state="disabled")
        threading.Thread(target=self.worker.stop, daemon=True).start()

    def retry_failed(self):
        items = [item for item in self.items if self.states.get(item[0]) in {"Falló", "Cancelado"}]
        for index, *_ in items:
            self.update_row(index, "En espera", "")
        if items:
            self.begin(items)

    def show_detail(self, _event):
        if self.preview:
            self.remove_items.configure(state="normal" if self.rows.selection() else "disabled")
            return
        for key in self.rows.selection():
            self.status.configure(text=self.errors.get(int(key), ""), fg=MUTED)

    def remove_selected(self, _event=None):
        if not self.preview:
            return
        selection = self.rows.selection()
        excluded = set(selection)
        self.items = [item for item in self.items if str(item[0]) not in excluded]
        self.rows.delete(*selection)
        self.remove_items.configure(state="disabled")
        self.count.configure(text=f"{len(self.items)} para descargar")
        self.go.configure(state="normal" if self.items else "disabled")
        if not self.items:
            self.empty.configure(text="No quedan elementos en la lista")
            self.empty.place(relx=.5, rely=.56, anchor="center")

    def end_preview(self):
        self.preview = False
        self.cancel_preview.pack_forget()
        self.remove_items.pack_forget()
        self.url.configure(state="normal")
        self.manual.configure(state="normal")

    def discard_preview(self):
        self.end_preview()
        self.items = []
        self.rows.delete(*self.rows.get_children())
        self.heading.configure(text="Cola")
        self.count.configure(text="0 archivos")
        self.empty.configure(text="Pega un enlace para empezar")
        self.empty.place(relx=.5, rely=.56, anchor="center")
        self.status.configure(text="", fg=MUTED)
        self.go.configure(text="Descargar ↓", state="normal")

    def update_row(self, index, state, detail):
        terminal = {"Guardado", "Falló", "Cancelado"}
        self.finished += int(state in terminal) - int(self.states.get(index) in terminal)
        self.states[index] = state
        self.errors[index] = detail
        if state == "Falló" and detail:
            self.status.configure(text=detail, fg=ERROR)
        number, name, _ = self.rows.item(str(index), "values")
        tag = "failed" if state == "Falló" else "active" if state.startswith(("Descargando", "Convirtiendo")) else ""
        self.rows.item(str(index), values=(number, name, state), tags=(tag,) if tag else ())
        if state in {"Descargando", "Convirtiendo"}:
            self.rows.see(str(index))
        self.count.configure(text=f"{self.finished} de {len(self.items)}")

    def poll(self):
        try:
            while True:
                event, *args = self.events.get_nowait()
                if event in {"listing", "preview"}:
                    title, self.items = args
                    self.heading.configure(text=title[:36])
                    self.count.configure(text=f"0 de {len(self.items)}")
                    self.empty.place_forget()
                    for index, _, title, _ in self.items:
                        self.rows.insert("", "end", iid=str(index), values=(f"{index:03}", title, "En espera"))
                    if event == "preview":
                        self.worker = None
                        if self.closing:
                            self.root.destroy()
                            return
                        self.preview = True
                        self.url.configure(state="disabled")
                        self.heading.pack_forget()
                        self.cancel_preview.pack(side="right", padx=(4, 8))
                        self.remove_items.pack(side="right", padx=(6, 0))
                        self.heading.pack(side="left")
                        self.remove_items.configure(state="disabled")
                        self.count.configure(text=f"{len(self.items)} para descargar")
                        self.go.configure(text="Descargar selección ↓", state="normal")
                        self.status.configure(text="Usa Ctrl o Mayús para seleccionar varias canciones.", fg=MUTED)
                elif event == "reading":
                    current, total = args
                    self.empty.configure(text=f"Leyendo enlaces… {current} de {total}")
                elif event == "title":
                    index, title = args
                    self.rows.set(str(index), "title", title)
                elif event == "row":
                    self.update_row(*args)
                elif event == "done":
                    self.worker = None
                    if self.closing:
                        self.root.destroy()
                        return
                    self.go.configure(text="Descargar ↓", state="normal")
                    self.manual.configure(state="normal")
                    if not self.items:
                        self.empty.configure(text="Pega un enlace para empezar")
                    for index, *_ in self.items:
                        if self.states.get(index) not in {"Guardado", "Falló"}:
                            self.update_row(index, "Cancelado", "")
                    saved = sum(s == "Guardado" for s in self.states.values())
                    failed = sum(s == "Falló" for s in self.states.values())
                    failure = next((self.errors[i] for i in self.states if self.states[i] == "Falló"), "")
                    summary = f"{saved} guardados · {failed} fallidos"
                    self.status.configure(text=args[0] or (f"{summary}. {failure}" if failure else summary),
                                          fg=ERROR if failure or (args[0] and not self.items) else MUTED)
                    if any(s in {"Falló", "Cancelado"} for s in self.states.values()):
                        self.retry.pack(side="right")
        except queue.Empty:
            pass
        self.root.after(75, self.poll)

    def close(self):
        if self.worker:
            self.closing = True
            self.request_cancel()
        else:
            self.root.destroy()


if __name__ == "__main__":
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    window = tk.Tk()
    icon_path = Path(getattr(sys, "_MEIPASS", ROOT)) / "ytdwn.ico"
    if icon_path.is_file():
        window.iconbitmap(default=str(icon_path))
    window.update_idletasks()
    hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
    dark = ctypes.c_int(1)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
    App(window)
    window.mainloop()
