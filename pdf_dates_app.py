"""PDF Dates: editor local de fechas PDF y propiedades de Windows."""
from __future__ import annotations

import ctypes
import io
import json
import os
import sys
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timezone
from pathlib import Path

import pikepdf
import pdf_dates_core as core

TITLE = 'PDF Dates'
VERSION = '1.0.0'
MODES = ('Conservar', 'Editar', 'Ahora')
LABELS = {'/CreationDate': 'Creación', '/ModDate': 'Modificación', 'xmp:MetadataDate': 'Metadatos XMP'}


def parse_date(text, offset):
    """Interpreta la hora escrita y asigna el offset; no convierte la hora."""
    zone = core.parse_offset(offset)
    for fmt in core.FORMATOS:
        try:
            return datetime.strptime(text.strip(), fmt).replace(tzinfo=zone)
        except ValueError:
            pass
    raise ValueError('Fecha no válida. Usa AAAA-MM-DD HH:MM:SS, por ejemplo 2026-01-22 11:24:03.')


def offset_text(date):
    if date is None or date.utcoffset() is None:
        return 'UTC'
    value = date.strftime('%z')
    return value[:3] + ':' + value[3:5]


def parse_xmp(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')) if value else None
    except ValueError:
        return None


def read_pdf_dates(reader):
    info = reader.metadata
    result = {}
    for key, attr in (('/CreationDate', 'creation_date'), ('/ModDate', 'modification_date')):
        try:
            result[key] = getattr(info, attr) if info is not None else None
        except (TypeError, ValueError, OverflowError):
            result[key] = None
    return result


def read_xmp(data):
    with pikepdf.open(io.BytesIO(data)) as pdf:
        core.validar_xmp(pdf)
        with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False, strict=True) as meta:
            return {key: str(meta[key]) for key in core.CLAVES_XMP if key in meta}


def restore_file_times(path, state):
    """Conserva las marcas originales del respaldo, con precisión nativa de Windows."""
    if os.name != 'nt':
        os.utime(path, ns=(state.st_atime_ns, state.st_mtime_ns))
        return
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.SetFileTime.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                  ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
    kernel.SetFileTime.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    def ft(ns):
        ticks = ns // 100 + 116444736000000000
        return wintypes.FILETIME(ticks & 0xffffffff, ticks >> 32)
    created, accessed, modified = (ft(value) for value in
        (state.st_birthtime_ns, state.st_atime_ns, state.st_mtime_ns))
    handle = kernel.CreateFileW(str(path.resolve()), 0x100, 0x7, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel.SetFileTime(handle, ctypes.byref(created), ctypes.byref(accessed), ctypes.byref(modified)):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)
    after = path.stat()
    if after.st_birthtime_ns != state.st_birthtime_ns or after.st_mtime_ns != state.st_mtime_ns:
        raise OSError('No se pudieron conservar las fechas originales de la copia de seguridad.')


def create_backup(path):
    """Copia de seguridad exclusiva: nunca reemplaza una copia previa."""
    state = path.stat()
    content = path.read_bytes()
    for index in range(1, 10001):
        suffix = '.bak' if index == 1 else f'.bak{index}'
        candidate = path.with_name(path.name + suffix)
        try:
            with candidate.open('xb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            continue
        if candidate.read_bytes() != content:
            raise OSError('La copia de seguridad no coincide con el archivo original.')
        restore_file_times(candidate, state)
        return candidate
    raise OSError('No se pudo reservar un nombre para la copia de seguridad.')


class DateRow:
    def __init__(self, parent, key, index):
        self.key = key
        self.mode = tk.StringVar(value='Conservar')
        self.text = tk.StringVar()
        self.zone = tk.StringVar(value='UTC')
        self.current = tk.StringVar(value='—')
        self.frame = ttk.Frame(parent, padding=(12, 8))
        self.frame.grid(row=index, column=0, sticky='ew', pady=(0, 2))
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(2, weight=1)
        ttk.Label(self.frame, text=LABELS[key], style='Field.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(self.frame, textvariable=self.current, style='Muted.TLabel').grid(row=1, column=0, sticky='w', pady=(5, 0))
        self.combo = ttk.Combobox(self.frame, textvariable=self.mode, values=MODES, state='readonly', width=12)
        self.combo.grid(row=0, column=1, rowspan=2, padx=12)
        self.entry = ttk.Entry(self.frame, textvariable=self.text, width=23)
        self.entry.grid(row=0, column=2, rowspan=2, sticky='ew')
        self.offset = ttk.Combobox(self.frame, textvariable=self.zone, values=('UTC', '+01:00', '+02:00', '-05:00', '-05:30'), width=9)
        self.offset.grid(row=0, column=3, rowspan=2, padx=(12, 0))
        self.mode.trace_add('write', lambda *_: self.refresh())
        self.refresh()

    def refresh(self):
        self.entry.configure(state='normal' if self.mode.get() == 'Editar' else 'disabled')
        self.offset.configure(state='disabled' if self.mode.get() == 'Conservar' else 'normal')

    def load(self, date, raw=None):
        self.mode.set('Conservar')
        self.current.set(core.fmt_date(date) if date is not None else str(raw or '(sin fecha)'))
        self.text.set(date.strftime('%Y-%m-%d %H:%M:%S') if date else '')
        self.zone.set(offset_text(date))

    def value(self):
        if self.mode.get() == 'Conservar':
            return None
        if self.mode.get() == 'Ahora':
            return datetime.now(core.parse_offset(self.zone.get())).replace(microsecond=0)
        return parse_date(self.text.get(), self.zone.get())


class PdfDatesApp:
    def __init__(self, root):
        self.root = root
        self.path = None
        self.data = None
        self.reader = None
        self.originals = {}
        self.xmp = {}
        self.loading = False
        root.title(f'{TITLE} · Editor de fechas')
        icon = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'assets' / 'pdfdates.ico'
        if icon.is_file():
            root.iconbitmap(str(icon))
        root.geometry(f'{min(1120, max(700, root.winfo_screenwidth()-80))}x{min(850, max(450, root.winfo_screenheight()-100))}')
        root.minsize(700, 450)
        root.configure(background='#f4f6f7')
        root.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), background='#f4f6f7', foreground='#202b32')
        style.configure('TEntry', fieldbackground='white', padding=7)
        style.configure('TCombobox', padding=6)
        style.configure('TButton', padding=(14, 8))
        style.configure('Accent.TButton', background='#176c62', foreground='white', padding=(18, 9))
        style.map('Accent.TButton', background=[('active', '#11574f'), ('disabled', '#ccd8d5')])
        style.configure('Title.TLabel', font=('Segoe UI Semibold', 21))
        style.configure('Field.TLabel', font=('Segoe UI Semibold', 11))
        style.configure('Muted.TLabel', foreground='#596872', font=('Segoe UI', 9))
        style.configure('Warning.TLabel', foreground='#79511b', font=('Segoe UI', 9))
        shell = ttk.Frame(root)
        shell.pack(fill='both', expand=True)
        shell.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)
        canvas = self.scroll_canvas = tk.Canvas(shell, highlightthickness=0, background='#f4f6f7')
        canvas.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(shell, orient='vertical', command=canvas.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(shell, orient='horizontal', command=canvas.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        body = ttk.Frame(canvas, padding=18)
        self.scroll_window = canvas.create_window(0, 0, window=body, anchor='nw')
        def resize(event):
            canvas.itemconfigure(self.scroll_window, width=max(960, event.width),
                                 height=max(body.winfo_reqheight(), event.height))
            canvas.configure(scrollregion=canvas.bbox('all'))
        canvas.bind('<Configure>', resize)
        body.bind('<Configure>', lambda _: canvas.configure(scrollregion=canvas.bbox('all')))
        def wheel(event):
            if not isinstance(event.widget, (ttk.Combobox, ttk.Entry)):
                canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        root.bind('<MouseWheel>', wheel, add='+')
        body.columnconfigure(0, weight=1)
        ttk.Label(body, text='PDF Dates', style='Title.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(body, text='Fechas del documento y del archivo. Todo se procesa en este equipo.', style='Muted.TLabel').grid(row=1, column=0, sticky='w', pady=(3, 12))
        pick = ttk.Frame(body)
        pick.grid(row=2, column=0, sticky='ew')
        pick.columnconfigure(0, weight=1)
        self.path_text = tk.StringVar(value='Selecciona un PDF para empezar')
        ttk.Entry(pick, textvariable=self.path_text, state='readonly').grid(row=0, column=0, sticky='ew', padx=(0, 12))
        self.open_button = ttk.Button(pick, text='Abrir PDF…', command=self.choose_file)
        self.open_button.grid(row=0, column=1)
        self.summary = tk.StringVar(value='Sin documento abierto')
        ttk.Label(body, textvariable=self.summary, style='Muted.TLabel').grid(row=3, column=0, sticky='w', pady=(6, 12))
        head = ttk.Frame(body, padding=(12, 0))
        head.grid(row=4, column=0, sticky='ew')
        ttk.Label(head, text='FECHA ACTUAL → NUEVA FECHA', style='Muted.TLabel').pack(side='left')
        ttk.Label(head, text='AAAA-MM-DD HH:MM:SS     ·     ZONA HORARIA', style='Muted.TLabel').pack(side='right')
        rows = ttk.Frame(body)
        rows.grid(row=5, column=0, sticky='ew', pady=(7, 8))
        rows.columnconfigure(0, weight=1)
        self.rows = {key: DateRow(rows, key, index) for index, key in enumerate(LABELS)}
        ttk.Label(body, text='Cada fecha tiene su propia zona. «Editar» guarda la hora escrita, sin convertirla.', style='Muted.TLabel').grid(row=6, column=0, sticky='w')
        self.with_xmp = tk.BooleanVar(value=True)
        self.sync_file = tk.BooleanVar(value=True)
        ttk.Checkbutton(body, text='Actualizar también XMP de las fechas de creación y modificación que edites', variable=self.with_xmp, command=self.options_changed).grid(row=7, column=0, sticky='w', pady=(12, 3))
        ttk.Checkbutton(body, text='Sincronizar «Creado» y «Modificado» de Windows con las fechas INFO finales', variable=self.sync_file).grid(row=8, column=0, sticky='w')
        ttk.Label(body, text='Windows muestra las horas en su zona local. «Último acceso» no se sincroniza.', style='Muted.TLabel').grid(row=9, column=0, sticky='w', pady=(3, 10))
        self.details = tk.StringVar(value='XMP actual: —\nArchivo actual: —')
        ttk.Label(body, textvariable=self.details, style='Muted.TLabel', justify='left', wraplength=1010).grid(row=10, column=0, sticky='ew', pady=(0, 12))
        ttk.Label(body, text='Aviso: reescribir un PDF puede invalidar firmas digitales. Al sobrescribir se crea una copia .bak.', style='Warning.TLabel', wraplength=1010).grid(row=11, column=0, sticky='w')
        body.rowconfigure(12, weight=1)
        actions = ttk.Frame(body)
        actions.grid(row=13, column=0, sticky='ew', pady=(16, 8))
        self.reset_button = ttk.Button(actions, text='Restablecer cambios', command=self.reset)
        self.reset_button.pack(side='left')
        self.overwrite_button = ttk.Button(actions, text='Sobrescribir original…', command=lambda: self.save_clicked(True))
        self.overwrite_button.pack(side='right', padx=(10, 0))
        self.copy_button = ttk.Button(actions, text='Guardar copia…', style='Accent.TButton', command=lambda: self.save_clicked(False))
        self.copy_button.pack(side='right')
        self.status = tk.StringVar(value='Listo. Los documentos no se suben a ningún servidor.')
        ttk.Separator(body).grid(row=14, column=0, sticky='ew', pady=(8, 9))
        ttk.Label(body, textvariable=self.status, style='Muted.TLabel', wraplength=1010).grid(row=15, column=0, sticky='w')
        self.set_enabled(False)
        root.bind('<Control-o>', lambda _: self.choose_file())

    def set_enabled(self, enabled):
        for widget in (self.copy_button, self.overwrite_button, self.reset_button):
            widget.configure(state='normal' if enabled else 'disabled')

    def options_changed(self):
        if not self.with_xmp.get():
            self.rows['xmp:MetadataDate'].mode.set('Conservar')
        self.rows['xmp:MetadataDate'].combo.configure(state='readonly' if self.with_xmp.get() else 'disabled')

    def dirty(self):
        return any(row.mode.get() != 'Conservar' for row in self.rows.values())

    def close(self):
        if self.dirty() and not messagebox.askyesno('Salir', 'Hay cambios sin guardar. ¿Quieres salir sin guardarlos?', parent=self.root):
            return
        self.root.destroy()

    def choose_file(self):
        if self.dirty() and not messagebox.askyesno('Cambiar documento', 'Se descartarán los cambios sin guardar. ¿Continuar?', parent=self.root):
            return
        filename = filedialog.askopenfilename(parent=self.root, title='Abrir un PDF', filetypes=[('Documentos PDF', '*.pdf')])
        if filename:
            try:
                self.load_file(Path(filename))
            except Exception as exc:
                messagebox.showerror('No se pudo abrir el PDF', str(exc), parent=self.root)

    def load_file(self, path):
        path = Path(path).resolve()
        data = path.read_bytes()
        reader = core.abrir_pdf(data)
        originals = read_pdf_dates(reader)
        xmp = read_xmp(data)
        stat = path.stat()
        self.path, self.data, self.reader = path, data, reader
        self.originals, self.xmp = originals, xmp
        self.path_text.set(str(path))
        self.summary.set(f'{len(reader.pages)} página(s) · {len(data):,} bytes · {path.name}')
        for key in ('/CreationDate', '/ModDate'):
            self.rows[key].load(originals[key], reader.metadata.get(key) if reader.metadata else None)
        self.rows['xmp:MetadataDate'].load(parse_xmp(xmp.get('xmp:MetadataDate')), xmp.get('xmp:MetadataDate'))
        created = datetime.fromtimestamp(stat.st_birthtime).astimezone() if hasattr(stat, 'st_birthtime') else None
        modified = datetime.fromtimestamp(stat.st_mtime).astimezone()
        self.details.set('XMP actual: creación ' + xmp.get('xmp:CreateDate', '(sin fecha)') + '\n'
                         '                     modificación ' + xmp.get('xmp:ModifyDate', '(sin fecha)') + '\n'
                         '                     metadatos ' + xmp.get('xmp:MetadataDate', '(sin fecha)') + '\n'
                         f'Archivo (hora local): Creado {core.fmt_date(created)} · Modificado {core.fmt_date(modified)}')
        self.set_enabled(True)
        self.options_changed()
        self.status.set('PDF abierto. Edita las fechas que quieras cambiar; la sincronización del archivo usa las fechas INFO finales.')

    def reset(self):
        if self.path:
            try:
                self.load_file(self.path)
            except Exception as exc:
                messagebox.showerror('No se pudo restablecer', str(exc), parent=self.root)

    def collect_changes(self):
        changes = {}
        for key in ('/CreationDate', '/ModDate'):
            try:
                value = self.rows[key].value()
            except ValueError as exc:
                raise ValueError(f'{LABELS[key]}: {exc}') from exc
            if value is not None:
                changes[key] = value
        metadata_date = None
        if self.with_xmp.get():
            try:
                metadata_date = self.rows['xmp:MetadataDate'].value()
            except ValueError as exc:
                raise ValueError(f'Metadatos XMP: {exc}') from exc
        final_dates = {**self.originals, **changes}
        if self.sync_file.get():
            for key in ('/CreationDate', '/ModDate'):
                date = final_dates.get(key)
                if date is None or date.utcoffset() is None:
                    raise ValueError(f'Para sincronizar Windows necesitas una fecha de {LABELS[key].lower()} con zona horaria. Edítala o desmarca la sincronización.')
                if date.astimezone(timezone.utc) <= datetime(1601, 1, 1, tzinfo=timezone.utc):
                    raise ValueError('Las fechas del archivo en Windows deben ser posteriores a 1601-01-01 UTC.')
        return changes, metadata_date, final_dates

    def save_document(self, destination, overwrite_approved=False, plan=None):
        if not self.path:
            raise ValueError('Abre primero un PDF.')
        destination = Path(destination).resolve()
        if destination.suffix.lower() != '.pdf':
            raise ValueError('El archivo de salida debe tener extensión .pdf.')
        if not destination.parent.is_dir():
            raise ValueError('No existe la carpeta de destino.')
        if destination.exists() and not overwrite_approved:
            raise ValueError('Debes confirmar antes de reemplazar un archivo existente.')
        if self.path.read_bytes() != self.data:
            raise ValueError('El PDF original ha cambiado desde que lo abriste. Vuelve a abrirlo antes de guardar.')
        before = destination.read_bytes() if destination.exists() else None
        changes, metadata_date, final_dates = plan if plan is not None else self.collect_changes()
        output = core.preparar_pdf(self.reader, changes, self.with_xmp.get(), metadata_date)
        # Comprobación de disco antes de reemplazar. No se interpreta un guardado parcial como éxito.
        if destination.exists() != (before is not None) or (before is not None and destination.read_bytes() != before):
            raise ValueError('El destino ha cambiado durante la preparación. No se ha reemplazado.')
        backup = create_backup(destination) if before is not None else None
        core.guardar_seguro(destination, output)
        try:
            # Reabrir desde disco y verificar antes de asignar las fechas de Windows.
            disk_data = destination.read_bytes()
            if disk_data != output:
                raise OSError('El contenido guardado no coincide con el resultado preparado.')
            core.verificar_resultado(disk_data, self.reader, changes, self.with_xmp.get(), metadata_date)
            if self.sync_file.get():
                core.sincronizar_fechas_archivo(destination, final_dates)
        except Exception as exc:
            raise OSError(f'El PDF se ha guardado en {destination}, pero falló la comprobación final o la sincronización. '
                          f'Copia de seguridad: {backup or "no era necesaria"}. Detalle: {exc}') from exc
        # No se lee de nuevo el contenido tras SetFileTime; stat no altera las fechas asignadas.
        return {'path': str(destination), 'backup': str(backup) if backup else None,
                'file_times': self.sync_file.get(), 'changes': list(changes), 'xmp': self.with_xmp.get()}

    def save_clicked(self, overwrite=False):
        if self.path is None:
            return
        try:
            plan = self.collect_changes()
            if overwrite:
                destination = self.path
            else:
                filename = filedialog.asksaveasfilename(parent=self.root, title='Guardar una copia',
                    initialdir=str(self.path.parent), initialfile=self.path.stem + '.copia.pdf',
                    defaultextension='.pdf', filetypes=[('Documentos PDF', '*.pdf')], confirmoverwrite=False)
                if not filename:
                    return
                destination = Path(filename)
            approved = False
            if destination.exists():
                approved = messagebox.askyesno('Confirmar reemplazo',
                    f'Se reemplazará:\n{destination}\n\nSe creará una copia .bak antes de guardar.\n¿Continuar?', parent=self.root)
                if not approved:
                    return
            if not messagebox.askyesno('Confirmar guardado', self.preview(destination, plan), parent=self.root):
                return
            self.root.configure(cursor='watch')
            self.status.set('Preparando y verificando el PDF…')
            self.root.update_idletasks()
            result = self.save_document(destination, approved, plan)
            self.load_file(destination)
            text = f'Guardado y verificado: {destination}'
            if result['file_times']:
                text += '\nCreado y Modificado de Windows: sincronizados y comprobados.'
            if result['backup']:
                text += f'\nCopia de seguridad: {result["backup"]}'
            self.status.set(text)
            messagebox.showinfo('Guardado correcto', text, parent=self.root)
        except Exception as exc:
            self.status.set(f'No se ha completado la operación: {exc}')
            messagebox.showerror('No se pudo completar el guardado', str(exc), parent=self.root)
        finally:
            self.root.configure(cursor='')

    def preview(self, destination, plan=None):
        changes, metadata_date, final_dates = plan if plan is not None else self.collect_changes()
        lines = [f'Destino: {destination}', '']
        for key, date in changes.items():
            lines.append(f'{LABELS[key]}: {core.fmt_date(date)}')
        if metadata_date is not None:
            lines.append(f'Metadatos XMP: {core.fmt_date(metadata_date)}')
        lines.append('XMP: ' + ('se actualizará; MetadataDate se conserva salvo cambio explícito' if self.with_xmp.get() else 'no se actualizará'))
        if self.sync_file.get():
            lines.extend(['', 'Propiedades de Windows (hora local):',
                f'Creado: {core.fmt_date(final_dates["/CreationDate"].astimezone())}',
                f'Modificado: {core.fmt_date(final_dates["/ModDate"].astimezone())}'])
        lines.extend(['', 'Reescribir el PDF puede invalidar sus firmas digitales. ¿Guardar?'])
        return '\n'.join(lines)


def run_self_test(folder):
    """Prueba de integración de la GUI y el mismo motor incluido en el ejecutable."""
    from pypdf import PdfWriter, PdfReader
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if any(folder.iterdir()):
        raise ValueError('La carpeta de pruebas debe estar vacía para no sobrescribir documentos.')
    source = folder / 'prueba-original.pdf'
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_metadata({'/CreationDate': "D:20200102030405+01'00'", '/ModDate': "D:20210102030405+01'00'", '/Title': 'Prueba PDF Dates'})
    writer.write(source)
    original = source.read_bytes()
    original_stat = source.stat()
    root = tk.Tk()
    root.withdraw()
    app = PdfDatesApp(root)
    report = {'version': VERSION}
    try:
        app.load_file(source)
        for key, date, offset in (
            ('/CreationDate', '2026-01-22 11:24:03', 'UTC'),
            ('/ModDate', '2026-01-22 11:24:03', '+02:00'),
            ('xmp:MetadataDate', '2026-01-22 11:24:03', '-05:30'),
        ):
            row = app.rows[key]
            row.mode.set('Editar')
            row.text.set(date)
            row.zone.set(offset)
        root.update_idletasks()
        dest = folder / 'prueba-resultado.pdf'
        app.save_document(dest)
        stat = dest.stat()
        expected_created = parse_date('2026-01-22 11:24:03', 'UTC').timestamp()
        expected_modified = parse_date('2026-01-22 11:24:03', '+02:00').timestamp()
        assert abs(stat.st_birthtime - expected_created) < 0.001
        assert abs(stat.st_mtime - expected_modified) < 0.001
        report['file_times_verified'] = True
        reader = PdfReader(dest)
        assert reader.metadata['/CreationDate'] == "D:20260122112403+00'00'"
        assert reader.metadata['/ModDate'] == "D:20260122112403+02'00'"
        assert reader.metadata['/Title'] == 'Prueba PDF Dates'
        assert len(reader.pages) == 1
        xmp = read_xmp(dest.read_bytes())
        assert xmp['xmp:CreateDate'] == '2026-01-22T11:24:03+00:00'
        assert xmp['xmp:ModifyDate'] == '2026-01-22T11:24:03+02:00'
        assert xmp['xmp:MetadataDate'] == '2026-01-22T11:24:03-05:30'
        assert source.read_bytes() == original
        assert source.stat().st_birthtime_ns == original_stat.st_birthtime_ns
        assert source.stat().st_mtime_ns == original_stat.st_mtime_ns
        report['source_unchanged'] = True
        app.load_file(dest)
        app.rows['/CreationDate'].mode.set('Editar')
        app.rows['/CreationDate'].text.set('2026-02-30')
        try:
            app.save_document(folder / 'invalido.pdf')
        except ValueError:
            report['invalid_date_rejected'] = not (folder / 'invalido.pdf').exists()
        else:
            raise AssertionError('Se aceptó una fecha inválida.')
        app.rows['/CreationDate'].text.set('2026-01-23 10:00:00')
        app.rows['/CreationDate'].zone.set('+02:00')
        previous = dest.read_bytes()
        previous_state = dest.stat()
        result = app.save_document(dest, overwrite_approved=True)
        assert Path(result['backup']).read_bytes() == previous
        backup_state = Path(result['backup']).stat()
        assert backup_state.st_birthtime_ns == previous_state.st_birthtime_ns
        assert backup_state.st_mtime_ns == previous_state.st_mtime_ns
        report['backup_verified'] = True
        # Un fallo de validación de sincronización tampoco debe crear el destino.
        app.load_file(source)
        app.rows['/CreationDate'].mode.set('Editar')
        app.rows['/CreationDate'].text.set('1500-01-01')
        app.rows['/CreationDate'].zone.set('UTC')
        try:
            app.save_document(folder / 'fuera-rango.pdf')
        except ValueError:
            report['out_of_range_rejected'] = not (folder / 'fuera-rango.pdf').exists()
        else:
            raise AssertionError('Se aceptó una fecha Windows fuera de rango.')
        app.load_file(source)
        altered = folder / 'cambio-externo.pdf'
        altered.write_bytes(original)
        app.load_file(altered)
        altered.write_bytes(original + b'\n% cambio externo')
        try:
            app.save_document(folder / 'no-guardar.pdf')
        except ValueError:
            report['external_change_rejected'] = not (folder / 'no-guardar.pdf').exists()
        else:
            raise AssertionError('No se detectó un cambio externo.')
        encrypted = folder / 'cifrado.pdf'
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt('solo-prueba')
        writer.write(encrypted)
        try:
            app.load_file(encrypted)
        except ValueError:
            report['encrypted_rejected'] = True
        else:
            raise AssertionError('No se rechazó un PDF cifrado.')
        damaged = folder / 'xmp-danado.pdf'
        with pikepdf.Pdf.new() as pdf:
            pdf.add_blank_page()
            pdf.Root.Metadata = pikepdf.Stream(pdf, b'<x:xmpmeta xmlns:x="adobe:ns:meta/">roto <')
            pdf.Root.Metadata.Type = pikepdf.Name.Metadata
            pdf.Root.Metadata.Subtype = pikepdf.Name.XML
            pdf.save(damaged, fix_metadata_version=False)
        try:
            app.load_file(damaged)
        except ValueError:
            report['damaged_xmp_rejected'] = True
        else:
            raise AssertionError('No se rechazaron los metadatos XMP dañados.')
        report['ok'] = all(report.get(key) for key in ('source_unchanged', 'file_times_verified', 'backup_verified',
            'invalid_date_rejected', 'external_change_rejected', 'encrypted_rejected', 'out_of_range_rejected', 'damaged_xmp_rejected'))
        report['output'] = str(dest)
        return report
    finally:
        root.destroy()


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        import tempfile
        parent = Path(sys.argv[2]).resolve()
        parent.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix='PDFDates-pruebas-', dir=parent))
        try:
            result = run_self_test(folder)
            code = 0 if result['ok'] else 1
        except Exception:
            result = {'ok': False, 'error': traceback.format_exc()}
            code = 1
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / 'resultado-pruebas.json').open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        return code
    if os.name == 'nt':
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (OSError, AttributeError):
            pass
    root = tk.Tk()
    app = PdfDatesApp(root)
    if len(sys.argv) == 2:
        try:
            app.load_file(Path(sys.argv[1]))
        except Exception as exc:
            messagebox.showerror('No se pudo abrir el PDF', str(exc), parent=root)
    root.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
