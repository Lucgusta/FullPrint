# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller para o FullPrint.

Invocar a partir da RAIZ do repositorio:
    pyinstaller packaging/FullPrint.spec --noconfirm

Gera one-folder em `dist/FullPrint/` (mais rapido e estavel que one-file para
apps com Tkinter + OCR). O Inno Setup empacota essa pasta + Tesseract embutido.
"""
import os

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# Caminhos do .spec sao resolvidos relativos a pasta do spec (packaging/);
# ancoramos tudo na RAIZ do repo (um nivel acima) para invocar a partir dela.
ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))

datas = []
# Assets do CustomTkinter / tkinterdnd2 (temas, dll do drag-and-drop).
datas += collect_data_files("customtkinter")
datas += collect_data_files("tkinterdnd2")
# Configuracao e template ZPL da etiqueta.
datas += [
    (os.path.join(ROOT, "src/config/config.yaml"), "src/config"),
    (os.path.join(ROOT, "src/core/templates/etiqueta_produto_2up.zpl"), "src/core/templates"),
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

# O pyzbar carrega libzbar-64.dll (e a dependencia libiconv.dll) em runtime via
# ctypes, a partir da PROPRIA pasta do pacote (os.path.dirname(__file__)).
# collect_submodules so traz os .py -- sem as DLLs o app quebra em maquinas
# limpas com "Could not find module 'libiconv.dll'". collect_dynamic_libs as
# coleta e mantem o destino na subpasta pyzbar/, onde o pyzbar as procura.
binaries = collect_dynamic_libs("pyzbar")

a = Analysis(
    [os.path.join(ROOT, "src/main.py")],
    pathex=[ROOT],
    binaries=binaries,
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
    # UPX pode corromper DLLs nativas; nao comprimir as do zbar/iconv.
    upx_exclude=["libzbar-64.dll", "libiconv.dll"],
    name="FullPrint",
)
