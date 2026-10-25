"""
Pulse — Single-File Executable Builder.
Compiles Pulse into a standalone Windows .exe with no console window.
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

    import webview
    import pythonnet

    webview_lib = os.path.join(os.path.dirname(webview.__file__), "lib")
    webview_data = f"{webview_lib};."
    win_x64_data = f"{os.path.join(webview_lib, 'runtimes', 'win-x64', 'native')};win-x64"
    win_x86_data = f"{os.path.join(webview_lib, 'runtimes', 'win-x86', 'native')};win-x86"
    win_arm64_data = f"{os.path.join(webview_lib, 'runtimes', 'win-arm64', 'native')};win-arm64"
    pythonnet_runtime = os.path.join(os.path.dirname(pythonnet.__file__), "runtime")
    pythonnet_data = f"{pythonnet_runtime};."

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
        "--add-data", webview_data,
        "--add-data", win_x64_data,
        "--add-data", win_x86_data,
        "--add-data", win_arm64_data,
        "--add-data", pythonnet_data,
        "--paths", os.path.join(ROOT_DIR, "src"),
        "--collect-all", "webview",
        "--collect-all", "pythonnet",
        "--collect-all", "apscheduler",
        "--collect-all", "google.genai",
        "--hidden-import", "google.genai",
        "--hidden-import", "clr",
        "--hidden-import", "pythonnet",
        "--hidden-import", "urllib3",
        "--hidden-import", "requests",
        "--hidden-import", "win32gui",
        "--hidden-import", "win32api",
        "--hidden-import", "win32con",
        "--hidden-import", "win32process",
        "--hidden-import", "win32com",
        "--hidden-import", "win32com.client",
        "--hidden-import", "pyautogui",
        "--hidden-import", "psutil",
        "--exclude-module", "numpy",
        "--exclude-module", "pandas",
        "--exclude-module", "scipy",
        "--exclude-module", "torch",
        "--exclude-module", "PyQt5",
        "--exclude-module", "PyQt6",
        "--exclude-module", "PySide2",
        "--exclude-module", "PySide6",
        "--exclude-module", "matplotlib",
        "--exclude-module", "cv2",
        "--exclude-module", "IPython",
        "--exclude-module", "pygame",
        "--exclude-module", "tkinter",
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
        root_exe = os.path.join(ROOT_DIR, "Pulse.exe")
        if os.path.exists(exe_path):
            import shutil
            try:
                shutil.copy2(exe_path, root_exe)
            except Exception as e:
                print(f"[Build] Warning copying to root: {e}")

            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print("=" * 60)
            print(f" Build Successful!")
            print(f" Output Executable: {exe_path}")
            print(f" Root Shortcut:     {root_exe}")
            print(f" Executable Size:   {size_mb:.2f} MB")
            print("=" * 60)
            return 0
    print("[Build] Build failed with return code:", result.returncode)
    return result.returncode


if __name__ == "__main__":
    sys.exit(build())
