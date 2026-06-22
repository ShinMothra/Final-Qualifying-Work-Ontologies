# -*- mode: python ; coding: utf-8 -*-
#
# Сборка: pyinstaller konstruktor_ontologiy.spec
#
# Структура после сборки (--onedir):
#   dist/КонструкторОнтологий/
#       КонструкторОнтологий.exe
#       _internal/
#           resources/        <- сюда PyInstaller 6.x кладёт datas в onedir-режиме;
#                                  main.py находит эту папку через sys._MEIPASS
#           ...                  (библиотеки PySide6, matplotlib, owlready2 и т.д.)
#
# Для передачи на другой компьютер — копировать ВСЮ папку dist/КонструкторОнтологий/.

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None
PROJECT_ROOT = Path(SPECPATH)

owlready2_datas = collect_data_files('owlready2')

a = Analysis(
    ['main.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        (str(PROJECT_ROOT / 'resources'), 'resources'),
    ] + owlready2_datas,
    hiddenimports=[
        # matplotlib SVG backend — используется только программно через
        # savefig(format='svg'), PyInstaller иногда не подхватывает его
        # автоматически без явного backend.use("Agg") + этого hidden import
        'matplotlib.backends.backend_svg',
        'matplotlib.backends.backend_agg',
        # owlready2 — динамические импорты внутри пакета (quadstore/sqlite)
        'owlready2',
        # sympy — формульный модуль; latex-парсинг иногда тянет под-модули
        # лениво (importlib), что PyInstaller не всегда видит статическим анализом
        'sympy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Эти GUI-тулкиты явно не используются 
        'tkinter',
        'PyQt5',
        'PyQt6',
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='КонструкторОнтологий',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # без консольного окна (GUI-приложение)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icons/app_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='КонструкторОнтологий',
)
