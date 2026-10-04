"""
Pulse — Single-File Executable Builder.
Compiles Pulse into a standalone, commercial-grade Windows .exe with no console window.
Embeds static assets (HTML/CSS/JS/icons) and config templates using PyInstaller.
"""

import os
import sys
import subprocess

# Project root directory (parent of scripts/)
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPTS_DIR)


def build():
    print("=" * 60)
    print(" Building Pulse Standalone Single-File Executable (.exe)")
    print("=" * 60)

    # 1. Verify / generate icon.ico
    ico_path = os.path.join(ROOT_DIR, "assets", "icon.ico")
    png_path = os.path.join(ROOT_DIR, "assets", "icon.png")
    if not os.path.exists(ico_path) and os.path.exists(png_path):
        from PIL import Image
        print("[Build] Generating icon.ico from assets/icon.png...")
        img = Image.open(png_path)
        sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        img.save(ico_path, format="ICO", sizes=sizes)

    # 2. PyInstaller command arguments
    static_data = f"{os.path.join(ROOT_DIR, 'static')};static"
    config_example_data = f"{os.path.join(ROOT_DIR, 'config.example.json')};."
    version_file_path = os.path.join(SCRIPTS_DIR, "file_version_info.txt")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name", "Pulse",
        "--icon", ico_path,
        "--add-data", static_data,
        "--add-data", config_example_data,
        "--paths", os.path.join(ROOT_DIR, "src"),
        "--collect-all", "webview",
        "--hidden-import", "urllib3",
        "--hidden-import", "requests",
        "--clean",
        "-y",
    ]

    if os.path.exists(version_file_path):
        cmd.extend(["--version-file", version_file_path])

    cmd.append(os.path.join(ROOT_DIR, "src", "app.py"))

    print("[Build] Running PyInstaller command:")
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT_DIR)

    if result.returncode == 0:
        exe_path = os.path.join(ROOT_DIR, "dist", "Pulse.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print("=" * 60)
            print(f" Build Successful!")
            print(f" Output Executable: {exe_path}")
            print(f" Executable Size:   {size_mb:.2f} MB")
            print("=" * 60)
            return 0
    print("[Build] Build failed with return code:", result.returncode)
    return result.returncode


if __name__ == "__main__":
    sys.exit(build())
