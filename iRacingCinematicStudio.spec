# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files

datas = []
datas += collect_data_files('certifi')


a = Analysis(
    ['C:/Users/zizek/Documents/iRacing-AI-Cinematic-Studio/app/main.py'],
    pathex=['C:/Users/zizek/Documents/iRacing-AI-Cinematic-Studio'],
    binaries=[],
    datas=datas,
    hiddenimports=['irsdk', 'ai.providers.openai_compat', 'utils.secrets', 'keyring.backends.Windows'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='iRacingCinematicStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
