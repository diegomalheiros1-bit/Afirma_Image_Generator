"""Run local tests with external network blocked and isolated logger output."""
import contextlib
from datetime import datetime
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT)]
work = ROOT / 'output' / 'local-tests' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
work.mkdir(parents=True, exist_ok=False)
os.chdir(work)
original_connect = socket.socket.connect
original_connect_ex = socket.socket.connect_ex

def guard(method):
    def connect(instance, address):
        if not isinstance(address, tuple) or address[0] not in {'127.0.0.1', 'localhost', '::1'}:
            raise AssertionError('External network forbidden in local tests')
        return method(instance, address)
    return connect

with patch.object(socket.socket, 'connect', guard(original_connect)), \
        patch.object(socket.socket, 'connect_ex', guard(original_connect_ex)):
    with (work / 'tests.log').open('w', encoding='utf-8') as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
print(f'{result.testsRun} tests; failures={len(result.failures)}; errors={len(result.errors)}; '
      f'external network blocked; log={work / "tests.log"}')
raise SystemExit(0 if result.wasSuccessful() else 1)
