import io
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pypdf import PdfReader, PdfWriter
import pikepdf

class AppTests(unittest.TestCase):
    def test_fecha_y_zona_independientes(self):
        from pdf_dates_app import parse_date
        self.assertEqual(parse_date('2026-01-22 11:24:03', '+02:00').isoformat(), '2026-01-22T11:24:03+02:00')
        self.assertEqual(parse_date('2026-01-22 11:24:03', 'UTC').isoformat(), '2026-01-22T11:24:03+00:00')
        with self.assertRaises(ValueError):
            parse_date('2026-02-30', '+02:00')
        with self.assertRaises(ValueError):
            parse_date('2026-02-20', '+24:00')

    def test_gui_guardado_completo(self):
        from pdf_dates_app import run_self_test
        with tempfile.TemporaryDirectory() as folder:
            report = run_self_test(Path(folder))
            self.assertTrue(report['ok'])
            self.assertTrue(report['source_unchanged'])
            self.assertTrue(report['file_times_verified'])
            self.assertTrue(report['backup_verified'])
            self.assertTrue(report['encrypted_rejected'])
            self.assertTrue(report['invalid_date_rejected'])
            self.assertTrue(report['external_change_rejected'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
