# -*- mode: python ; coding: utf-8 -*-
import os
import site
from pathlib import Path

block_cipher = None

# Find hcl2 package location
site_packages = site.getsitepackages()[0]
hcl2_path = os.path.join(site_packages, 'hcl2')
hcl2_grammar = os.path.join(hcl2_path, 'hcl2.lark')

a = Analysis(
    ['CLI/cloud_cli.py'],
    pathex=[],
    binaries=[],
    datas=[(hcl2_grammar, 'hcl2')],
    hiddenimports=[
        'CLI', 
        'CLI.executors', 
        'CLI.utils', 
        'CLI.error_mapping', 
        'transpiler', 
        'converter',
        'hcl2',
        'lark'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'PIL',
        'scipy',
        'numpy',
        'pandas',
        'IPython',
        'notebook'
    ],  # Exclude unused large packages
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='cloud-cli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip symbols to reduce size
    upx=False,   # Disable UPX compression
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)