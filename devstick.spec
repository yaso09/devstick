# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules
from glob import glob
import os

block_cipher = None

binary_files = []

for path in glob("pyproot/binaries/*"):
    if os.path.isfile(path):
        binary_files.append((path, "pyproot/binaries"))

a = Analysis(
    ['main.py'],

    pathex=['.'],

    binaries=binary_files,

    datas=[
        # Rootfs included as runtime data
        ('rootfs', 'rootfs'),
    ],

    hiddenimports=[],

    hookspath=[],

    runtime_hooks=[],

    excludes=[
        'tkinter',
        'pytest',
        'unittest',
    ],

    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,

    name='devstick',

    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,

    console=True
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,

    strip=False,
    upx=True,

    name='devstick'
)
