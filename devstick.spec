# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],

    pathex=['.'],

    binaries=[
        # PRoot binary inclusion
        ('proot/arm64/proot', 'proot/arm64'),
        ('proot/x86_64/proot', 'proot/x86_64'),
    ],

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