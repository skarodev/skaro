"""Hatch build hook: builds Svelte frontend before packaging."""

import shutil
import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBuildHook(BuildHookInterface):
    PLUGIN_NAME = 'frontend-build'

    def initialize(self, version, build_data):
        frontend_dir = Path(self.root) / 'frontend'
        static_dir = Path(self.root) / 'src' / 'skaro_web' / 'static'

        if not frontend_dir.exists():
            return

        # Check if any frontend source is newer than the last build
        index_html = static_dir / 'index.html'
        if index_html.exists():
            build_time = index_html.stat().st_mtime
            src_dir = frontend_dir / 'src'
            needs_rebuild = False
            for src_file in src_dir.rglob('*'):
                if src_file.is_file() and src_file.stat().st_mtime > build_time:
                    needs_rebuild = True
                    break
            # Also check config files
            for cfg in ('package.json', 'svelte.config.js', 'vite.config.js'):
                cfg_path = frontend_dir / cfg
                if cfg_path.exists() and cfg_path.stat().st_mtime > build_time:
                    needs_rebuild = True
                    break
            if not needs_rebuild:
                return

        # Clean stale build artifacts to prevent hash mismatch
        app_dir = static_dir / '_app'
        if app_dir.exists():
            shutil.rmtree(app_dir)
            print('[frontend-build] Cleaned stale _app directory')

        self._run('npm install', frontend_dir)
        self._run('npm run build', frontend_dir)

    def _run(self, cmd, cwd):
        print(f'[frontend-build] Running: {cmd}')
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            raise RuntimeError(f'[frontend-build] Failed: {cmd}')
