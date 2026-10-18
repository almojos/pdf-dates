import io
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pikepdf
import pdf_dates_app as app

class ReviewTests(unittest.TestCase):
    def test_rechaza_xmp_danado(self):
        pdf = pikepdf.Pdf.new()
        pdf.add_blank_page()
        pdf.Root.Metadata = pikepdf.Stream(pdf, b'<x:xmpmeta xmlns:x="adobe:ns:meta/">contenido roto <')
        pdf.Root.Metadata.Type = pikepdf.Name.Metadata
        pdf.Root.Metadata.Subtype = pikepdf.Name.XML
        out = io.BytesIO()
        pdf.save(out, fix_metadata_version=False)
        with pikepdf.open(io.BytesIO(out.getvalue())) as check:
            self.assertIn(b'contenido roto', check.Root.Metadata.read_bytes())
        with self.assertRaises(ValueError):
            app.read_xmp(out.getvalue())

    def test_ahora_guarda_el_valor_confirmado(self):
        import tkinter as tk
        from datetime import datetime, timezone, timedelta
        from unittest.mock import patch
        from pypdf import PdfWriter, PdfReader
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'origen.pdf'
            dest = Path(folder) / 'salida.pdf'
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            writer.write(source)
            root = tk.Tk()
            root.withdraw()
            gui = app.PdfDatesApp(root)
            try:
                gui.load_file(source)
                gui.with_xmp.set(False)
                gui.sync_file.set(False)
                row = gui.rows['/CreationDate']
                row.mode.set('Ahora')
                first = datetime(2026, 1, 22, 10, 0, 0, tzinfo=timezone.utc)
                values = [first + timedelta(seconds=i) for i in range(10)]
                with patch.object(row, 'value', side_effect=values) as value_mock, \
                     patch.object(app.filedialog, 'asksaveasfilename', return_value=str(dest)), \
                     patch.object(app.messagebox, 'askyesno', return_value=True), \
                     patch.object(app.messagebox, 'showinfo'), \
                     patch.object(app.messagebox, 'showerror') as error:
                    gui.save_clicked()
                    error.assert_not_called()
                    self.assertEqual(value_mock.call_count, 1)
                self.assertEqual(PdfReader(dest).metadata['/CreationDate'], "D:20260122100000+00'00'")
            finally:
                root.destroy()

    def test_backup_conserva_fechas_del_archivo(self):
        import os
        from datetime import datetime, timezone
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'original.pdf'
            source.write_bytes(b'contenido de prueba')
            app.core.sincronizar_fechas_archivo(source, {
                '/CreationDate': datetime(2020, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
                '/ModDate': datetime(2021, 2, 3, 4, 5, 6, tzinfo=timezone.utc),
            })
            before = source.stat()
            backup = app.create_backup(source)
            after = backup.stat()
            self.assertEqual(after.st_birthtime_ns, before.st_birthtime_ns)
            self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
            self.assertEqual(backup.read_bytes(), source.read_bytes())

    def test_autoprueba_rechaza_carpeta_no_vacia(self):
        with tempfile.TemporaryDirectory() as folder:
            sentinel = Path(folder) / 'cifrado.pdf'
            sentinel.write_bytes(b'NO REEMPLAZAR')
            with self.assertRaises(ValueError):
                app.run_self_test(Path(folder))
            self.assertEqual(sentinel.read_bytes(), b'NO REEMPLAZAR')

    def test_ventana_admite_altura_reducida(self):
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            gui = app.PdfDatesApp(root)
            self.assertLessEqual(root.minsize()[1], 550)
            self.assertTrue(hasattr(gui, 'scroll_canvas'))
        finally:
            root.destroy()

if __name__ == '__main__':
    unittest.main(verbosity=2)
