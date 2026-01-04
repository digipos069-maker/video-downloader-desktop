# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all
import sys
import os
from playwright.sync_api import sync_playwright

# Increase recursion limit for deep imports in yt_dlp
sys.setrecursionlimit(5000)

# Collect all yt_dlp submodules (extractors)
yt_dlp_hidden_imports = collect_submodules('yt_dlp')

# Collect Playwright package data (browsers are usually external, but we need the driver)
# Note: Playwright browsers are large. Standard practice is to install them on target machine
# or bundle them manually. Here we try to collect package data.
datas, binaries, hiddenimports = collect_all('playwright')

# Add resources
datas.append(('app/resources', 'app/resources'))

# Check for ffmpeg in current environment to bundle it (optional but recommended)
ffmpeg_path = None
# You might want to point this to a specific ffmpeg.exe if you have one in your project
if os.path.exists('ffmpeg.exe'):
    binaries.append(('ffmpeg.exe', '.'))

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=yt_dlp_hidden_imports + hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VideoDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True, # Set to False to hide console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/resources/images/logo.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VideoDownloader',
)
