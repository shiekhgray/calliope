import io
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile

from app.auth import get_current_user
from app import models
from app.config import settings

router = APIRouter(prefix="/import", tags=["import"])

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus"}


def _decode_amazon(name: str) -> str:
    return name.replace("__", "/")


def _strip_bandcamp_prefix(filename: str, artist: str, album: str) -> str:
    pattern = rf"^.+?\s+-\s+{re.escape(album)}\s+-\s+"
    m = re.match(pattern, filename)
    if m:
        return filename[m.end():]
    prefix = f"{artist} - {album} - "
    if filename.startswith(prefix):
        return filename[len(prefix):]
    return filename


def _transcode_flac_to_mp3(src: Path, dest: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-q:a", "0", str(dest)],
        check=True,
    )


def _process_zip(filename: str, data: bytes, music_root: Path) -> dict:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return {"filename": filename, "status": "error", "message": "Not a valid zip file."}

    names = zf.namelist()
    audio_names = [n for n in names if Path(n).suffix.lower() in AUDIO_EXTENSIONS]

    if not audio_names:
        return {"filename": filename, "status": "warning", "message": "No audio files found in zip."}

    two_level = [n for n in audio_names if len(Path(n).parts) == 3]
    one_level = [n for n in audio_names if len(Path(n).parts) == 2]
    flat = [n for n in audio_names if len(Path(n).parts) == 1]

    if two_level:
        return _extract_amazon(filename, zf, two_level, music_root)
    elif one_level and " - " in Path(one_level[0]).parts[0]:
        return _extract_qobuz(filename, zf, one_level, music_root)
    elif flat and " - " in Path(filename).stem:
        return _extract_bandcamp(filename, zf, flat, names, music_root)
    else:
        return {
            "filename": filename,
            "status": "error",
            "message": "Could not detect format. Expected: Bandcamp ('Artist - Album.zip' flat), Amazon (Artist/Album/track), or Qobuz ('Artist - Album/' subdirectory with FLACs).",
        }


def _extract_qobuz(filename: str, zf: zipfile.ZipFile, audio_names: list, music_root: Path) -> dict:
    subdir = Path(audio_names[0]).parts[0]
    artist, _, album = subdir.partition(" - ")
    artist, album = artist.strip(), album.strip()
    dest_dir = music_root / artist / album
    dest_dir.mkdir(parents=True, exist_ok=True)

    if not shutil.which("ffmpeg"):
        return {"filename": filename, "status": "error", "message": "ffmpeg not found in container — rebuild the API image."}

    count = 0
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for name in sorted(audio_names):
                src_name = Path(name).name
                dest_name = Path(src_name).with_suffix(".mp3").name
                tmp_flac = tmp_path / src_name
                tmp_flac.write_bytes(zf.read(name))
                _transcode_flac_to_mp3(tmp_flac, dest_dir / dest_name)
                count += 1
    except subprocess.CalledProcessError as e:
        return {"filename": filename, "status": "error", "message": f"ffmpeg transcoding failed: {e}"}

    return {"filename": filename, "status": "ok", "artist": artist, "album": album, "tracks_imported": count}


def _extract_bandcamp(filename: str, zf: zipfile.ZipFile, audio_names: list, all_names: list, music_root: Path) -> dict:
    stem = Path(filename).stem
    artist, _, album = stem.partition(" - ")
    artist, album = artist.strip(), album.strip()
    dest_dir = music_root / artist / album
    dest_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for name in audio_names:
        track_name = _strip_bandcamp_prefix(Path(name).name, artist, album)
        (dest_dir / track_name).write_bytes(zf.read(name))
        count += 1

    cover = next((n for n in all_names if Path(n).name.lower() == "cover.jpg"), None)
    if cover:
        (dest_dir / "Folder.jpg").write_bytes(zf.read(cover))

    return {"filename": filename, "status": "ok", "artist": artist, "album": album, "tracks_imported": count}


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}


def _extract_amazon(filename: str, zf: zipfile.ZipFile, audio_names: list, music_root: Path) -> dict:
    first = Path(audio_names[0])
    artist = _decode_amazon(first.parts[0])
    album = _decode_amazon(first.parts[1])
    dest_dir = music_root / artist / album
    dest_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for name in audio_names:
        track_clean = _decode_amazon(Path(name).name)
        (dest_dir / track_clean).write_bytes(zf.read(name))
        count += 1

    # Copy any cover art found in the album directory
    all_names = zf.namelist()
    prefix = f"{first.parts[0]}/{first.parts[1]}/"
    for name in all_names:
        p = Path(name)
        if name.startswith(prefix) and p.suffix.lower() in IMAGE_EXTENSIONS and len(p.parts) == 3:
            dest_name = "Folder.jpg" if p.name.lower() in ("folder.jpg", "cover.jpg") else _decode_amazon(p.name)
            (dest_dir / dest_name).write_bytes(zf.read(name))

    return {"filename": filename, "status": "ok", "artist": artist, "album": album, "tracks_imported": count}


@router.post("/upload")
async def upload_import(
    files: List[UploadFile] = File(...),
    _current_user: models.User = Depends(get_current_user),
):
    music_root = Path(settings.music_root)
    results = []
    for f in files:
        data = await f.read()
        result = _process_zip(f.filename or "unknown", data, music_root)
        results.append(result)
    return {"results": results}
