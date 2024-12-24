# -*- mode: python ; coding: utf-8 -*-
import os
import site
from pathlib import Path

block_cipher = None

def find_hcl2_grammar():
    # First try site-packages
    for site_pkg in site.getsitepackages():
        possible_path = os.path.join(site_pkg, 'hcl2', 'hcl2.lark')
        if os.path.exists(possible_path):
            return possible_path
            
    # Fall back to package location
    import hcl2
    package_path = os.path.dirname(hcl2.__file__)
    possible_path = os.path.join(package_path, 'hcl2.lark')
    if os.path.exists(possible_path):
        return possible_path
        
    raise FileNotFoundError("Could not find hcl2.lark in any expected location")

# Get the grammar file path
hcl2_grammar = find_hcl2_grammar()
print(f"Found hcl2 grammar at: {hcl2_grammar}")

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
        'lark',
        'click',
        'yaml',
        'rich',
        'rich.console',
        'rich.table',
        'rich.progress'
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
    ],
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
    strip=True,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)