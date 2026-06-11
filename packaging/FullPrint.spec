# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller para o FullPrint.

Invocar a partir da RAIZ do repositorio:
    pyinstaller packaging/FullPrint.spec --noconfirm

Gera one-folder em `dist/FullPrint/` (mais rapido e estavel que one-file para
apps com Tkinter + OCR). O Inno Setup empacota essa pasta + Tesseract embutido.
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = []
# Assets do CustomTkinter / tkinterdnd2 (temas, dll do drag-and-drop).
datas += collect_data_files("customtkinter")
datas += collect_data_files("tkinterdnd2")
# Configuracao e template ZPL do separador.
datas += [
    ("src/config/config.yaml", "src/config"),
    ("src/core/templates/separador.zpl", "src/core/templates"),
]

hiddenimports = []
hiddenimports += collect_submodules("pyzbar")
hiddenimports += [
    "win32print",
    "win32ui",
    "pytesseract",
    "PIL._tkinter_finder",
]

block_cipher = None

a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name="FullPrint",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # app GUI -- sem janela de console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="packaging/fullprint.ico",  # adicionar quando houver .ico
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FullPrint",
)
