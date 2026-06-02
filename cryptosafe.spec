# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec (спринт 8)

import os

block_cipher = None
root = os.path.abspath(SPECPATH)
assets_dir = os.path.join(root, "assets")
_icon_ico = os.path.join(assets_dir, "icon.ico")
_datas = []
if os.path.isdir(assets_dir):
    _datas.append((assets_dir, "assets"))

a = Analysis(
    [os.path.join(root, "run.py")],
    pathex=[os.path.join(root, "src")],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        "argon2",
        "cryptography",
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
    ],
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
    name="CryptoSafeManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon_ico if os.path.isfile(_icon_ico) else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CryptoSafeManager",
)
