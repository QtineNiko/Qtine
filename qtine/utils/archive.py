import os
import re
import shutil
import stat
import zipfile
from pathlib import PurePosixPath

MAX_ARCHIVE_FILES = 2000
MAX_ARCHIVE_SIZE = 200 * 1024 * 1024
_PACKAGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def validate_package_name(name: str) -> str:
    if not isinstance(name, str) or not _PACKAGE_NAME.fullmatch(name):
        raise ValueError("Invalid package name")
    if name in {".", ".."}:
        raise ValueError("Invalid package name")
    return name


def safe_extract_zip(
    archive: zipfile.ZipFile,
    destination: str,
    max_files: int = MAX_ARCHIVE_FILES,
    max_size: int = MAX_ARCHIVE_SIZE,
) -> None:
    root = os.path.realpath(destination)
    infos = archive.infolist()
    if len(infos) > max_files:
        raise ValueError("Archive contains too many files")

    total_size = 0
    entries = []
    for info in infos:
        name = info.filename
        if not name or "\\" in name or "\x00" in name:
            raise ValueError("Archive contains an invalid path")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Archive path escapes destination")
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ValueError("Archive symlinks are not allowed")
        if info.flag_bits & 0x1:
            raise ValueError("Encrypted archives are not supported")
        total_size += info.file_size
        if total_size > max_size:
            raise ValueError("Archive is too large when extracted")
        target = os.path.realpath(os.path.join(root, *path.parts))
        if os.path.commonpath((root, target)) != root:
            raise ValueError("Archive path escapes destination")
        entries.append((info, target))

    os.makedirs(root, exist_ok=True)
    for info, target in entries:
        if info.is_dir():
            os.makedirs(target, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with archive.open(info, "r") as source, open(target, "wb") as output:
            shutil.copyfileobj(source, output, length=1024 * 1024)
