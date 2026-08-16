import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

app = FastAPI(title="YouTube MP3 Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://hakods.github.io",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


def is_youtube_url(value: str) -> bool:
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False

    if parsed.scheme not in {"http", "https"}:
        return False

    host = (parsed.hostname or "").lower().rstrip(".")
    return host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")


def looks_like_playlist(value: str) -> bool:
    parsed = urlparse(value)
    query = parse_qs(parsed.query)
    return parsed.path.rstrip("/").endswith("/playlist") or bool(query.get("list"))


def cleanup_directory(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def download_audio(url: str, target_dir: Path, playlist: bool) -> Path:
    output_template = (
        str(target_dir / "%(playlist_index)03d - %(title)s.%(ext)s")
        if playlist
        else str(target_dir / "%(title)s.%(ext)s")
    )

    options = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "windowsfilenames": True,
        "noplaylist": not playlist,
        "ignoreerrors": playlist,
        "continuedl": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }

    with YoutubeDL(options) as ydl:
        ydl.download([url])

    mp3_files = sorted(target_dir.glob("*.mp3"))
    if not mp3_files:
        raise RuntimeError("MP3 dosyası oluşturulamadı.")

    if len(mp3_files) == 1 and not playlist:
        return mp3_files[0]

    archive_base = target_dir.parent / "youtube_playlist"
    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=target_dir)
    return Path(archive_path)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "youtube-mp3-api", "status": "ok"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/download")
def download(url: str = Form(...), password: str = Form(default="")):
    url = url.strip()

    if not is_youtube_url(url):
        raise HTTPException(status_code=400, detail="Geçerli bir YouTube bağlantısı gir.")

    configured_password = os.getenv("APP_PASSWORD", "").strip()
    if configured_password and password != configured_password:
        raise HTTPException(status_code=401, detail="Erişim anahtarı hatalı.")

    job_dir = tempfile.mkdtemp(prefix="youtube_mp3_")
    target_dir = Path(job_dir) / "media"
    target_dir.mkdir(parents=True, exist_ok=True)
    playlist = looks_like_playlist(url)

    try:
        result_path = download_audio(url, target_dir, playlist)
    except DownloadError as exc:
        cleanup_directory(job_dir)
        message = str(exc)
        if "Sign in to confirm" in message or "not a bot" in message.lower():
            message = (
                "YouTube bu sunucudan gelen isteği anti-bot doğrulamasına taktı. "
                "Bir süre sonra tekrar dene."
            )
        raise HTTPException(status_code=502, detail=message) from exc
    except Exception as exc:
        cleanup_directory(job_dir)
        raise HTTPException(status_code=500, detail=f"İndirme başarısız: {exc}") from exc

    media_type = "application/zip" if result_path.suffix.lower() == ".zip" else "audio/mpeg"

    return FileResponse(
        path=result_path,
        filename=result_path.name,
        media_type=media_type,
        background=BackgroundTask(cleanup_directory, job_dir),
    )
