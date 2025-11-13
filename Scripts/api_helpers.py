# api_helpers.py
"""
Headless helper functions for SafeArchive.
Provides functions to create encrypted ZIP archives from a list of paths,
save encrypted backups to a backup store, and decrypt stored backups.
"""
import os
import tempfile
import shutil
import pyzipper
from typing import List, Optional

# Try to import project config if available
try:
    from Scripts.configs import config
except Exception:
    config = None

# Backup storage directory (inside container). Can be overridden by env var.
BACKUP_STORE = os.environ.get("SAFEARCHIVE_BACKUP_DIR", os.path.join(tempfile.gettempdir(), "safearchive_backups"))
os.makedirs(BACKUP_STORE, exist_ok=True)


def _get_compression_method_by_key(key: Optional[str]):
    mapping = {
        "ZIP_STORED": pyzipper.ZIP_STORED,
        "ZIP_DEFLATED": pyzipper.ZIP_DEFLATED,
        "ZIP_BZIP2": pyzipper.ZIP_BZIP2,
        "ZIP_LZMA": pyzipper.ZIP_LZMA,
    }
    return mapping.get(key, pyzipper.ZIP_DEFLATED)


def zip_paths_to_file(
    source_paths: List[str],
    out_zip_path: str,
    password: Optional[bytes] = None,
    compression_method_key: Optional[str] = None,
    compression_level: int = 6,
    allow_zip64: bool = True,
):
    """
    Create a zip archive at out_zip_path containing files and folders listed in source_paths.
    If password is provided (bytes), AES encryption (WZ_AES) will be used.

    This function is headless and does not depend on GUI components.
    """
    # choose compression method
    if compression_method_key is None and config is not None:
        compression_method_key = config.get("compression_method", "ZIP_DEFLATED")
    compression_method = _get_compression_method_by_key(compression_method_key)

    if compression_level is None and config is not None:
        compression_level = int(config.get("compression_level", 6))

    # determine if we should use encryption
    use_encryption = False
    if password:
        use_encryption = True

    encryption = pyzipper.WZ_AES if use_encryption else None

    # ensure output directory exists
    os.makedirs(os.path.dirname(out_zip_path), exist_ok=True)

    with pyzipper.AESZipFile(
        file=out_zip_path,
        mode="w",
        compression=compression_method,
        encryption=encryption,
        allowZip64=allow_zip64,
        compresslevel=int(compression_level),
    ) as zipObj:
        if use_encryption and password is not None:
            try:
                zipObj.setpassword(password)
            except Exception:
                pass

        # iterate and add files/dirs
        for item in source_paths:
            if os.path.isfile(item):
                arcname = os.path.basename(item)
                zipObj.write(item, arcname=arcname)
            elif os.path.isdir(item):
                for root, dirs, files in os.walk(item):
                    for dirname in dirs:
                        dirpath = os.path.join(root, dirname)
                        arcname = os.path.relpath(dirpath, start=os.path.dirname(item))
                        zipObj.write(dirpath, arcname=arcname)
                    for filename in files:
                        filepath = os.path.join(root, filename)
                        arcname = os.path.relpath(filepath, start=os.path.dirname(item))
                        zipObj.write(filepath, arcname=arcname)
            else:
                # ignore missing items silently
                continue


def create_zip_from_uploaded_files(
    uploaded_file_paths: List[str],
    password: Optional[bytes] = None,
    prefix: str = "safearchive_",
) -> str:
    """
    Given a list of local filesystem paths (uploaded files saved to tempdir),
    create a zip archive and return the path to the zip file.

    The caller is responsible for cleaning up the uploaded_file_paths if needed.
    """
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    try:
        zip_name = f"{prefix}{os.path.basename(tmpdir)}.zip"
        zip_path = os.path.join(tempfile.gettempdir(), zip_name)
        # ensure unique zip path
        i = 0
        base_zip = zip_path
        while os.path.exists(zip_path):
            i += 1
            zip_path = f"{base_zip.rstrip('.zip')}_{i}.zip"

        # call core zipping function
        zip_paths_to_file(
            source_paths=uploaded_file_paths,
            out_zip_path=zip_path,
            password=password,
        )

        return zip_path
    finally:
        # do not remove uploaded files here; caller may manage cleanup
        pass


def save_and_encrypt_backup(source_paths: List[str], backup_name: str, password: Optional[bytes]) -> str:
    """
    Create zip from source_paths and store it encrypted (AES) under BACKUP_STORE.
    Returns full path to stored backup file.
    """
    safe_name = "".join(c for c in backup_name if c.isalnum() or c in ("-", "_")).strip() or "backup"
    zip_path = os.path.join(tempfile.gettempdir(), f"tmp_{safe_name}_{os.getpid()}.zip")

    # create plain zip first
    zip_paths_to_file(source_paths, zip_path, password=None)

    if password:
        stored_path = os.path.join(BACKUP_STORE, f"{safe_name}.enc.zip")
        with pyzipper.AESZipFile(stored_path, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf_out:
            with open(zip_path, "rb") as fin:
                data = fin.read()
            try:
                zf_out.setpassword(password)
            except Exception:
                pass
            zf_out.writestr(f"{safe_name}.zip", data)
    else:
        stored_path = os.path.join(BACKUP_STORE, f"{safe_name}.zip")
        shutil.move(zip_path, stored_path)

    # cleanup tmp zip
    try:
        if os.path.exists(zip_path):
            os.remove(zip_path)
    except Exception:
        pass

    return stored_path


def decrypt_backup_to_zip(stored_backup_path: str, password: Optional[bytes]) -> str:
    """
    Given stored encrypted backup path (or plain zip), decrypt/extract and return a path to a restored zip
    ready for download. The returned file is a plain zip of the original contents.
    """
    if not os.path.exists(stored_backup_path):
        raise FileNotFoundError("backup not found")

    tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp_out.close()

    # if file is plain zip (not .enc.zip), just copy
    if stored_backup_path.endswith(".zip") and not stored_backup_path.endswith(".enc.zip"):
        shutil.copyfile(stored_backup_path, tmp_out.name)
        return tmp_out.name

    # Otherwise assume AES-encrypted archive containing the original zip as named entry
    with pyzipper.AESZipFile(stored_backup_path, 'r') as zf:
        if password:
            try:
                zf.setpassword(password)
            except Exception:
                pass
        namelist = zf.namelist()
        if not namelist:
            raise RuntimeError("encrypted archive empty")
        first = namelist[0]
        data = zf.read(first)
        with open(tmp_out.name, "wb") as f:
            f.write(data)
    return tmp_out.name
