"""Regression checks for installer recovery, writer exclusion and source readiness."""

from pathlib import Path
from unittest.mock import patch
import hashlib
import io
import os
import runpy
import shutil
import subprocess
import tempfile
import unittest
import zipfile

import install_tools
import support


class RuntimeChecks(unittest.TestCase):
    def test_corrupt_cached_archive_is_downloaded_again(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("mongo/bin/mongod.exe", b"fixture")
        complete = buffer.getvalue()
        digest = hashlib.sha256(complete).hexdigest().encode()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "mongodb.zip").write_bytes(b"interrupted assembly")
            def download(url, archive):
                archive.write_bytes(complete)
            with patch.object(install_tools, "ROOT", root), \
                 patch.object(install_tools, "download_mongodb", side_effect=download) as fetch, \
                 patch.object(install_tools.urllib.request, "urlopen", side_effect=lambda *a, **k: io.BytesIO(digest)):
                install_tools.install(("mongodb", "https://example.invalid/mongodb.zip", "sha256"))
                self.assertEqual(fetch.call_count, 1)
                self.assertTrue((root / "mongodb/.installed").exists())

    def test_interrupted_assembly_is_not_a_completed_archive(self):
        class Response(io.BytesIO):
            headers = {"Content-Range": "bytes 0-4/5"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "mongodb.zip"
            copy = shutil.copyfileobj
            def interrupted(source, target, *args, **kwargs):
                if str(target.name).endswith(".assembling"):
                    target.write(b"partial")
                    raise OSError("simulated interruption")
                return copy(source, target, *args, **kwargs)
            with patch.object(install_tools, "ROOT", root), \
                 patch.object(install_tools.urllib.request, "urlopen", side_effect=lambda *a, **k: Response(b"12345")), \
                 patch.object(install_tools.shutil, "copyfileobj", side_effect=interrupted):
                with self.assertRaisesRegex(OSError, "simulated interruption"):
                    install_tools.download_mongodb("https://example.invalid", archive)
                self.assertFalse(archive.exists())

    def test_owner_alignment_obeys_the_pipeline_writer_lock(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(support, "ROOT", Path(temporary)), \
             patch.object(support, "require_ready", side_effect=AssertionError("entered writer")), \
             patch("sys.argv", ["align_owners.py"]):
            with support.writer_lock():
                with self.assertRaisesRegex(RuntimeError, "Another pipeline writer"):
                    runpy.run_path(str(Path(__file__).with_name("align_owners.py")), run_name="__main__")

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "Windows PowerShell required")
    def test_open_port_does_not_prove_mongodb_is_ready(self):
        source = Path(__file__).resolve().parents[1] / "database/start.ps1"
        script = source.read_text()
        project_line = "$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path"
        script = script.replace(project_line, "$project = 'audit-project'")
        script = script.replace("$python = Join-Path $project '.venv/Scripts/python.exe'", "$python = 'Invoke-AuditPython'")
        mocks = """
function Get-ChildItem { [pscustomobject]@{ FullName = 'unused.exe' } }
function New-Item { }
function Test-Path { $true }
function Test-NetConnection { $true }
function Start-Process { throw 'Must not start real services' }
function Start-Sleep { }
function Invoke-RestMethod { @{cluster_name='dmi-79189';status='green'} }
function Invoke-AuditPython { $global:LASTEXITCODE = 1 }
"""
        command = mocks + "\ntry { & {\n" + script + "\n} -WaitSeconds 0 -SkipQwen; exit 1 } catch { Write-Output $_; exit 0 }"
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Sources did not start", result.stdout)
        self.assertNotIn("MongoDB: mongodb://", result.stdout)


if __name__ == "__main__":
    unittest.main()
