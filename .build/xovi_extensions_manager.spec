# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['xovi_extensions_manager.py'],
    pathex=[],
    binaries=[],
    datas=[('translations.json', '.')],
    hiddenimports=[],
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
    name='Xovi Extensions Manager',
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
    icon='icon.icns',
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name='Xovi Extensions Manager.app',
    icon='icon.icns',
    bundle_identifier=None,
)
