#!/usr/bin/env python3
# Simple CLI for SafeArchive with an "Encrypt & backup folder" option (4).

import os
import sys
import shutil
import tempfile
import time
import getpass
import base64
from pathlib import Path

# Try imports for encryption (cryptography preferred, fall back to pycryptodome)
try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.fernet import Fernet
    CRYPTOGRAPHY_AVAILABLE = True
except Exception:
    CRYPTOGRAPHY_AVAILABLE = False

try:
    from Crypto.Cipher import AES
    from Crypto.Protocol.KDF import PBKDF2 as PBKDF2_CRYPTO
    from Crypto.Random import get_random_bytes
    PYCRYPTO_AVAILABLE = True
except Exception:
    PYCRYPTO_AVAILABLE = False

# Project imports (assumes running from project root)
from Scripts.configs import config
from Scripts.file_utils import create_destination_directory_path

# Load config (safe to call again)
try:
    config.load()
except Exception:
    # If config module uses mapping access before load, ignore here
    pass

DESTINATION_PATH = os.path.join(config.get('destination_path', ''), 'SafeArchive') + os.sep
create_destination_directory_path(DESTINATION_PATH)


def list_source_paths():
    print("\nConfigured source paths:")
    for i, p in enumerate(config.get('source_paths', []), 1):
        print(f"{i}. {p}")
    print("")


def add_source_path():
    path = input("Enter folder path to add: ").strip()
    if not path:
        print("No path entered.")
        return
    p = os.path.abspath(path)
    if not os.path.isdir(p):
        print("Folder not found.")
        return
    if p in config.get('source_paths', []):
        print("Folder already present in source paths.")
        return
    config['source_paths'].append(p)
    try:
        config.save()
        print("Folder added.")
    except Exception:
        print("Folder added (config save failed).")


def remove_source_path():
    list_source_paths()
    idx = input("Enter number of folder to remove: ").strip()
    if not idx.isdigit():
        print("Invalid input.")
        return
    idx = int(idx) - 1
    try:
        removed = config['source_paths'].pop(idx)
        config.save()
        print(f"Removed: {removed}")
    except Exception:
        print("Failed to remove (invalid index or config save error).")


def zip_folder(folder_path, temp_dir):
    base_name = os.path.join(temp_dir, "archive")
    # shutil.make_archive will append .zip
    archive_path = shutil.make_archive(base_name, 'zip', root_dir=folder_path)
    return archive_path  # path to .zip


def encrypt_with_cryptography(data_bytes: bytes, password: str) -> bytes:
    # Derive key from password -> use Fernet (base64 urlsafe 32 bytes)
    salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    f = Fernet(key)
    token = f.encrypt(data_bytes)
    # Store salt + token; caller should write bytes
    return salt + token


def encrypt_with_pycrypto(data_bytes: bytes, password: str) -> bytes:
    # PBKDF2 -> AES-CBC with PKCS7 padding; format: salt(16) + iv(16) + ciphertext
    salt = get_random_bytes(16)
    key = PBKDF2_CRYPTO(password, salt, dkLen=32, count=390000)
    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    # PKCS7 padding
    pad_len = 16 - (len(data_bytes) % 16)
    data_padded = data_bytes + bytes([pad_len]) * pad_len
    ciphertext = cipher.encrypt(data_padded)
    return salt + iv + ciphertext


def perform_encrypt_and_backup():
    folder = input("Enter full path of folder to encrypt & backup: ").strip()
    if not folder:
        print("No folder entered.")
        return
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        print("Folder does not exist.")
        return

    password = getpass.getpass("Enter password to encrypt the archive: ")
    if not password:
        print("No password entered; aborting.")
        return

    print("Creating zip archive...")
    temp_dir = tempfile.mkdtemp(prefix="safearchive_")
    try:
        zip_path = zip_folder(folder, temp_dir)
        with open(zip_path, 'rb') as f:
            zip_bytes = f.read()

        enc_bytes = None
        method = None
        if CRYPTOGRAPHY_AVAILABLE:
            try:
                enc_bytes = encrypt_with_cryptography(zip_bytes, password)
                method = "cryptography (Fernet, PBKDF2)"
            except Exception:
                enc_bytes = None

        if enc_bytes is None and PYCRYPTO_AVAILABLE:
            try:
                enc_bytes = encrypt_with_pycrypto(zip_bytes, password)
                method = "pycryptodome (AES-CBC, PBKDF2)"
            except Exception:
                enc_bytes = None

        timestamp = time.strftime("%Y%m%d%H%M%S")
        folder_name = os.path.basename(os.path.normpath(folder))
        # Use a clear extension for encrypted zip files so users recognize the underlying format
        out_name = f"{folder_name}_{timestamp}.zip.enc"
        out_path = os.path.join(DESTINATION_PATH, out_name)

        if enc_bytes is not None:
            with open(out_path, 'wb') as out_f:
                out_f.write(enc_bytes)
            print(f"Encrypted archive created and moved to: {out_path}")
            print(f"Encryption method used: {method}")
        else:
            # Fallback: just move the zip (no encryption)
            fallback_name = f"{folder_name}_{timestamp}.zip"
            fallback_path = os.path.join(DESTINATION_PATH, fallback_name)
            shutil.move(zip_path, fallback_path)
            print("Warning: No encryption backend available. Archive saved unencrypted.")
            print(f"Archive moved to: {fallback_path}")

    finally:
        # Clean up temp dir
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def decrypt_with_cryptography(enc_bytes: bytes, password: str) -> bytes:
    # stored: salt(16) + token
    salt = enc_bytes[:16]
    token = enc_bytes[16:]
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    f = Fernet(key)
    return f.decrypt(token)


def decrypt_with_pycrypto(enc_bytes: bytes, password: str) -> bytes:
    # stored: salt(16) + iv(16) + ciphertext
    salt = enc_bytes[:16]
    iv = enc_bytes[16:32]
    ciphertext = enc_bytes[32:]
    key = PBKDF2_CRYPTO(password, salt, dkLen=32, count=390000)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = cipher.decrypt(ciphertext)
    pad_len = padded[-1]
    if pad_len < 1 or pad_len > 16:
        raise ValueError("Bad padding, wrong password or corrupted file.")
    return padded[:-pad_len]


def try_decrypt(enc_bytes: bytes, password: str) -> bytes:
    """Try available decryption backends in the same order used for encryption."""
    # Try cryptography first
    if CRYPTOGRAPHY_AVAILABLE:
        try:
            return decrypt_with_cryptography(enc_bytes, password)
        except Exception:
            pass
    if PYCRYPTO_AVAILABLE:
        try:
            return decrypt_with_pycrypto(enc_bytes, password)
        except Exception:
            pass
    raise ValueError("Decryption failed (wrong password or no suitable backend).")


def list_archives_in_destination():
    files = []
    for name in sorted(os.listdir(DESTINATION_PATH)):
        if name.endswith('.zip.enc') or name.endswith('.zip'):
            files.append(name)
    if not files:
        print("No archives found in destination.")
        return []
    print("\nAvailable archives:")
    for i, f in enumerate(files, 1):
        print(f"{i}) {f}")
    return files


def restore_archive():
    files = list_archives_in_destination()
    if not files:
        return
    idx = input("Enter number of archive to restore: ").strip()
    if not idx.isdigit():
        print("Invalid input.")
        return
    idx = int(idx) - 1
    if idx < 0 or idx >= len(files):
        print("Invalid selection.")
        return
    choice_name = files[idx]
    choice_path = os.path.join(DESTINATION_PATH, choice_name)

    temp_dir = tempfile.mkdtemp(prefix="safearchive_restore_")
    try:
        if choice_name.endswith('.zip.enc'):
            password = getpass.getpass("Enter password to decrypt the archive: ")
            if not password:
                print("No password entered; aborting.")
                return
            with open(choice_path, 'rb') as f:
                enc_bytes = f.read()
            try:
                zip_bytes = try_decrypt(enc_bytes, password)
            except Exception as e:
                print(f"Decryption failed: {e}")
                return
            temp_zip_path = os.path.join(temp_dir, "restored.zip")
            with open(temp_zip_path, 'wb') as zf:
                zf.write(zip_bytes)
            zip_to_extract = temp_zip_path
        else:
            # plain zip
            zip_to_extract = choice_path

        dest = input("Enter destination folder to extract to (default: current dir): ").strip() or os.getcwd()
        dest = os.path.abspath(dest)
        os.makedirs(dest, exist_ok=True)
        print(f"Extracting to: {dest}")
        shutil.unpack_archive(zip_to_extract, dest)
        print("Restore complete.")
    finally:
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def main_loop():
    while True:
        print("\nSafeArchive CLI")
        print("1) List configured source folders")
        print("2) Add folder to sources")
        print("3) Remove folder from sources")
        print("4) Encrypt & backup a folder (creates encrypted archive in destination)")
        print("5) Restore an archive from destination (decrypt & extract)")
        print("0) Exit")
        choice = input("Select option: ").strip()
        if choice == "1":
            list_source_paths()
        elif choice == "2":
            add_source_path()
        elif choice == "3":
            remove_source_path()
        elif choice == "4":
            perform_encrypt_and_backup()
        elif choice == "5":
            restore_archive()
        elif choice == "0":
            print("Exiting.")
            break
        else:
            print("Invalid option.")


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nInterrupted; exiting.")
