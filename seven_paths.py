# filepath: seven_paths.py
# description: Centralized path resolution for dev mode vs installed mode.
#              Every file that reads/writes data MUST use these paths.
#              Dev mode: paths relative to project root
#              Installed mode: code in Program Files, data in AppData/Roaming

"""
=============================================================================
PROJECT SEVEN — seven_paths.py
Centralized Path Resolution

PURPOSE:
    In dev mode:  everything is relative to project root
    Installed:    code lives in Program Files, data in AppData/Roaming/SEVEN

USAGE:
    from seven_paths import paths
    config_file = paths.config          # → config.json (correct location)
    data_dir    = paths.data_dir        # → data/ folder (correct location)
    db_path     = paths.license_db      # → data/license.db
=============================================================================
"""

import os
import sys
import shutil


def _is_installed():
    """
    Detect if running from an installed location vs dev.
    Installed = running from Program Files or via packaged Electron.
    """
    # Check Electron packaged mode
    if os.environ.get('SEVEN_ELECTRON_MODE') == '1':
        # Check if we're in a typical install directory
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        if 'Program Files' in exe_dir or 'AppData' in exe_dir:
            return True
        # Check for resources/app structure (electron-builder)
        if 'resources' in exe_dir:
            return True

    # Check if frozen (PyInstaller — future-proofing)
    if getattr(sys, 'frozen', False):
        return True

    return False


def _get_app_dir():
    """
    Where the application CODE lives.
    Dev:       M:/Manikanta/Apps/MK-Projects/SEVEN/
    Installed: C:/Program Files/SEVEN/resources/app/
    """
    if _is_installed():
        # In packaged Electron, Python files are in resources/app/
        # electron-builder extraResources copies them there
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        # Walk up to find the resources/app directory
        # main.py could be at: resources/app/main.py
        if os.path.exists(os.path.join(exe_dir, 'main.py')):
            return exe_dir

        # Or it could be launched from the electron dir
        app_dir = os.path.join(exe_dir, '..', 'resources', 'app')
        if os.path.exists(app_dir):
            return os.path.abspath(app_dir)

        return exe_dir
    else:
        # Dev mode: project root (where this file lives)
        return os.path.dirname(os.path.abspath(__file__))


def _get_data_dir():
    """
    Where USER DATA lives (config, databases, memories).
    Dev:       ./  (project root, same as app dir)
    Installed: C:/Users/{user}/AppData/Roaming/SEVEN/
    """
    if _is_installed():
        appdata = os.environ.get('APPDATA',
                                 os.path.expanduser('~\\AppData\\Roaming'))
        data_dir = os.path.join(appdata, 'SEVEN')
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    else:
        return os.path.dirname(os.path.abspath(__file__))


class SevenPaths:
    """
    Single source of truth for all file paths in Seven.

    Attributes:
        app_dir      — where code lives (read-only in production)
        data_dir     — where user data lives (read-write)
        config       — config.json path
        license_db   — data/license.db
        telemetry_db — data/telemetry.db
        device_id    — data/device_id.txt
        email_file   — data/email.txt
        memory_dir   — seven_data/memory/
        knowledge_dir— seven_data/knowledge/
        python_dir   — embedded Python runtime (installed mode only)
        is_installed — bool: are we running from install?
    """

    def __init__(self):
        self.is_installed = _is_installed()
        self.app_dir = _get_app_dir()
        self.data_dir = _get_data_dir()

        # ── User data paths (writable) ──
        self.config = os.path.join(self.data_dir, 'config.json')

        # data/ subfolder
        self._data_sub = os.path.join(self.data_dir, 'data')
        os.makedirs(self._data_sub, exist_ok=True)

        self.license_db = os.path.join(self._data_sub, 'license.db')
        self.telemetry_db = os.path.join(self._data_sub, 'telemetry.db')
        self.device_id = os.path.join(self._data_sub, 'device_id.txt')
        self.email_file = os.path.join(self._data_sub, 'email.txt')

        # seven_data/ subfolder
        self._seven_data = os.path.join(self.data_dir, 'seven_data')
        self.memory_dir = os.path.join(self._seven_data, 'memory')
        self.knowledge_dir = os.path.join(self._seven_data, 'knowledge')
        os.makedirs(self.memory_dir, exist_ok=True)
        os.makedirs(self.knowledge_dir, exist_ok=True)

        # ── App code paths (read-only in production) ──
        self.requirements = os.path.join(self.app_dir, 'requirements.txt')
        self.main_py = os.path.join(self.app_dir, 'main.py')

        # ── Embedded Python (installed mode) ──
        if self.is_installed:
            self.python_dir = os.path.join(
                os.path.dirname(self.app_dir), 'python'
            )
            self.python_exe = os.path.join(
                self.python_dir, 'python.exe'
            )
        else:
            self.python_dir = None
            self.python_exe = 'python'  # system Python in dev

        # ── First-run: copy default config if missing ──
        self._init_defaults()

    def _init_defaults(self):
        """
        On first install, copy default config.json from app dir
        to data dir if it doesn't exist yet.
        """
        if self.is_installed and not os.path.exists(self.config):
            src = os.path.join(self.app_dir, 'config.json')
            if os.path.exists(src):
                shutil.copy2(src, self.config)
                print(f'[PATHS] Copied default config to {self.config}')

    def resolve(self, relative_path):
        """
        Resolve a path that could be app-relative or data-relative.
        Data files (config, db, memory) → data_dir
        Code files (*.py, ears/, hands/) → app_dir
        """
        # Known data patterns
        data_patterns = [
            'config.json', 'data/', 'seven_data/',
            'license.db', 'telemetry.db',
            'device_id.txt', 'email.txt',
        ]
        for pattern in data_patterns:
            if pattern in relative_path:
                return os.path.join(self.data_dir, relative_path)

        return os.path.join(self.app_dir, relative_path)

    def __repr__(self):
        mode = 'INSTALLED' if self.is_installed else 'DEV'
        return (
            f'SevenPaths({mode})\n'
            f'  app_dir:  {self.app_dir}\n'
            f'  data_dir: {self.data_dir}\n'
            f'  config:   {self.config}\n'
            f'  python:   {self.python_exe}'
        )


# ── Singleton — import this everywhere ──
paths = SevenPaths()