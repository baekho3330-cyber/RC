# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import playwright

pw_driver = Path(playwright.__file__).parent / 'driver'

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('icon.ico', '.'),
        (str(pw_driver), 'playwright/driver'),
    ],
    hiddenimports=[
        'crawler',
        'ohou_analyzer',
        'hanssem_crawler',
        'analyze',
        'playwright.sync_api',
        'playwright._impl._browser',
        'playwright._impl._browser_context',
        'playwright._impl._page',
        'openpyxl.styles',
        'openpyxl.styles.alignment',
        'openpyxl.styles.fonts',
        'openpyxl.styles.fills',
        'openpyxl.cell',
        'anthropic',
        'pandas',
    ],
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
    [],
    exclude_binaries=True,
    name='ReviewFetch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ReviewFetch',
)
