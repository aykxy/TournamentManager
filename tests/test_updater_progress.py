"""Regression tests for background update download progress."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import updater


class FakeResponse:
    def __init__(self, data, length=True):
        self.stream = io.BytesIO(data)
        self.headers = {'Content-Length': str(len(data))} if length else {}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.stream.close()
    def geturl(self):
        return 'https://objects.githubusercontent.com/download'
    def read(self, size):
        return self.stream.read(size)


class UpdaterProgressTests(unittest.TestCase):
    def test_download_reports_progress(self):
        payload = b'abc' * 100
        events = []
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'package.zip'
            with patch('updater.urllib.request.urlopen', return_value=FakeResponse(payload)):
                updater._download('https://github.com/example/release', target, 1000,
                                  lambda current, total: events.append((current, total)))
            self.assertEqual(target.read_bytes(), payload)
        self.assertEqual(events[0], (0, len(payload)))
        self.assertEqual(events[-1], (len(payload), len(payload)))

    def test_download_without_content_length(self):
        payload = b'xyz'
        events = []
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'package.zip'
            with patch('updater.urllib.request.urlopen', return_value=FakeResponse(payload, False)):
                updater._download('https://github.com/example/release', target, 1000,
                                  lambda current, total: events.append((current, total)))
        self.assertEqual(events[-1], (3, None))

    def test_download_enforces_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('updater.urllib.request.urlopen', return_value=FakeResponse(b'oversized')):
                with self.assertRaisesRegex(ValueError, 'exceeds limit'):
                    updater._download('https://github.com/example/release',
                                      Path(directory) / 'package.zip', 3)

    def test_download_rejects_untrusted_host(self):
        with self.assertRaisesRegex(ValueError, 'Untrusted'):
            updater._download('https://example.com/release', 'unused', 1000)


if __name__ == '__main__':
    unittest.main()
