"""Security regression: TOTP secrets must never leave this process."""
import ast
import base64
import hashlib
import hmac
from pathlib import Path
import re
import struct
import time
import unittest
from unittest.mock import Mock, patch


class TotpPrivacyTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'glaze_app.py'
        tree = ast.parse(source.read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'generate_totp_rfc6238')
        self.http = Mock()
        scope = dict(base64=base64, hashlib=hashlib, hmac=hmac, re=re, struct=struct, time=time, requests=self.http)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), scope)
        self.generate = scope[node.name]

    def test_rfc6238_vector_without_network(self):
        # RFC 6238 Appendix B, SHA-1, t=59.
        secret = base64.b32encode(b'12345678901234567890').decode()
        with patch.object(time, 'time', return_value=59):
            self.assertEqual(self.generate(secret, digits=8), ('94287082', 1))
        self.assertEqual(self.http.mock_calls, [])

    def test_malformed_secret_never_leaves_process(self):
        self.assertEqual(self.generate('A'), (None, 0))
        self.assertEqual(self.http.mock_calls, [])
