#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Editor interactivo de fechas de metadatos PDF.
Requiere pypdf.
pikepdf es opcional para leer y actualizar XMP.
Avisos:
- Reescribir un PDF puede invalidar sus firmas digitales.
- Opcionalmente sincroniza Creado y Modificado del archivo en Windows.
- Si no sincronizas, guardar puede cambiar las fechas del archivo igualmente.
- Windows muestra las fechas del archivo en su zona local, no en el offset del PDF.
- Ultimo acceso no se sincroniza con los metadatos PDF.
- Los offsets son fijos: no calculan el horario de verano.
"""
import io
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    raise SystemExit("Falta pypdf en el Python que ejecuta este programa.")
try:
    import pikepdf
except ImportError:
    pikepdf = None
FORMATOS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
)
CLAVES_XMP = (
    "xmp:CreateDate",
    "xmp:ModifyDate",
    "xmp:MetadataDate",
    "dc:created",
    "dcterms:created",
    "dcterms:modified",
)
def pedir_opcion(texto, opciones):
    while True:
        respuesta = input(texto).strip().lower()
        if respuesta in opciones:
            return respuesta
        print("Opcion no valida.")
def confirmar(texto):
    respuesta = pedir_opcion(
        f"{texto} [s/N]: ",
        {"", "s", "n"},
    )
    return respuesta == "s"
def limpiar_ruta(texto):
    texto = texto.strip()
    if (
        len(texto) >= 2
        and texto[0] == texto[-1]
        and texto[0] in ("'", '"')
    ):
        texto = texto[1:-1]
    if not texto:
        raise ValueError("La ruta esta vacia.")
    return Path(texto).expanduser()
def parse_offset(texto):
    texto = texto.strip().upper()
    if texto in ("UTC", "GMT", "Z"):
        return timezone.utc
    if not re.fullmatch(r"[+-]\d{2}:\d{2}", texto):
        raise ValueError("Usa UTC, +01:00, -05:30, etc.")
    horas, minutos = map(int, texto[1:].split(":"))
    if horas > 23 or minutos > 59:
        raise ValueError(
            "Horas entre 00 y 23; minutos entre 00 y 59."
        )
    signo = 1 if texto[0] == "+" else -1
    return timezone(
        signo * timedelta(hours=horas, minutes=minutos)
    )
def pedir_zona(anterior):
    while True:
        entrada = input(
            f"Offset [UTC / +01:00 / -05:30; vacio = {anterior}]: "
        ).strip()
        if not entrada:
            return anterior
        try:
            return parse_offset(entrada)
        except ValueError as exc:
            print(f"Error: {exc}")
def pedir_fecha(etiqueta):
    while True:
        entrada = input(
            f"{etiqueta} "
            "(YYYY-MM-DD HH:MM:SS; vacio = sin cambio): "
        ).strip()
        if not entrada:
            return None
        for formato in FORMATOS:
            try:
                return datetime.strptime(entrada, formato)
            except ValueError:
                pass
        print("Fecha no valida. Ejemplo: 2026-06-01 09:30:00")
def fmt_date(fecha):
    if fecha is None:
        return "(sin fecha)"
    if fecha.tzinfo is None or fecha.utcoffset() is None:
        return fecha.strftime(
            "%Y-%m-%d %H:%M:%S (sin zona)"
        )
    return fecha.strftime("%Y-%m-%d %H:%M:%S %z")
def pdf_date(fecha):
    if fecha.tzinfo is None or fecha.utcoffset() is None:
        raise ValueError("La fecha debe tener zona horaria.")
    offset = fecha.strftime("%z")
    return (
        f"D:{fecha:%Y%m%d%H%M%S}"
        f"{offset[:3]}'{offset[3:5]}'"
    )
def aplicar_zona(fecha, original, zona_elegida):
    if fecha is None:
        return None
    # La zona elegida explicitamente nunca se sustituye por la antigua.
    return fecha.replace(tzinfo=zona_elegida)


def pedir_fecha_con_zona(etiqueta, original=None):
    fecha = pedir_fecha(etiqueta)
    if fecha is None:
        return None
    anterior = (original.tzinfo if original is not None and original.utcoffset() is not None
                else timezone.utc)
    print(f"Zona horaria para {etiqueta}:")
    zona = pedir_zona(anterior)
    return aplicar_zona(fecha, original, zona)
def abrir_pdf(datos):
    reader = PdfReader(io.BytesIO(datos))
    if reader.is_encrypted:
        raise ValueError(
            "El PDF esta cifrado. Este programa no procesa "
            "PDFs cifrados ni solicita contrasenas."
        )
    return reader

def mostrar_info(reader):
    info = reader.metadata
    originales = {}
    for etiqueta, atributo, clave in (
        ("Creacion", "creation_date", "/CreationDate"),
        ("Modificacion", "modification_date", "/ModDate"),
    ):
        fecha = None
        try:
            if info is not None:
                fecha = getattr(info, atributo)
            print(f"  {etiqueta} (INFO): {fmt_date(fecha)}")
        except (ValueError, TypeError, OverflowError) as exc:
            print(f"  {etiqueta} (INFO): fecha no interpretable: {info.get(clave)!r} ({exc})")
        originales[clave] = fecha
    return originales


def mostrar_xmp(datos):
    if pikepdf is None:
        print("  XMP: no consultado (pikepdf no esta instalado).")
        return
    try:
        with pikepdf.open(io.BytesIO(datos)) as pdf:
            validar_xmp(pdf)
            with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False, strict=True) as meta:
                encontrados = False
                for clave in CLAVES_XMP:
                    if clave in meta:
                        encontrados = True
                        print(f"  {clave}: {meta[clave]}")
                if not encontrados:
                    print("  XMP: no contiene las fechas consultadas.")
    except Exception as exc:
        print(f"  Aviso: no se pudo consultar XMP: {exc}")


def leer_fecha_metadatos(datos):
    if pikepdf is None:
        raise ValueError("Para consultar XMP se necesita pikepdf.")
    with pikepdf.open(io.BytesIO(datos)) as pdf:
        validar_xmp(pdf)
        with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False, strict=True) as meta:
            return meta.get("xmp:MetadataDate")


def pedir_fecha_metadatos(datos):
    anterior = leer_fecha_metadatos(datos)
    print(f"\nxmp:MetadataDate actual: {anterior or '(sin fecha)'}")
    print("  [m] Introducir una fecha manual")
    print("  [a] Usar la fecha y hora actuales")
    print("  [c] Conservar la existente (opcion predeterminada)")
    opcion = pedir_opcion("> ", {"m", "a", "c", ""})
    if opcion in ("c", ""):
        return None
    original = None
    if anterior:
        try:
            original = datetime.fromisoformat(str(anterior).replace("Z", "+00:00"))
        except ValueError:
            pass
    if opcion == "a":
        anterior = (original.tzinfo if original is not None and original.utcoffset() is not None
                    else timezone.utc)
        print("Zona horaria para la fecha y hora actuales de METADATOS XMP:")
        zona = pedir_zona(anterior)
        return datetime.now(zona).replace(microsecond=0)
    return pedir_fecha_con_zona("Nueva fecha de METADATOS XMP", original)


def validar_xmp(pdf):
    """Impide que la recuperación de XML elimine metadatos dañados silenciosamente."""
    if "/Metadata" not in pdf.Root:
        return
    from lxml import etree
    try:
        raw = pdf.Root.Metadata.read_bytes()
        parser = etree.XMLParser(recover=False, resolve_entities=False, load_dtd=False, no_network=True)
        root = etree.fromstring(raw, parser=parser)
        if root.getroottree().docinfo.doctype:
            raise ValueError("XMP con DTD no admitido.")
        if not any(True for _ in root.iter("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF")):
            raise ValueError("Falta la estructura RDF de XMP.")
    except Exception as exc:
        raise ValueError("El PDF contiene XMP dañado o no admitido. No se modificará para evitar perder metadatos. " + str(exc)) from exc


def actualizar_xmp(datos, cambios, fecha_metadatos=None):
    if pikepdf is None:
        raise ValueError("Para actualizar XMP se necesita pikepdf.")
    salida = io.BytesIO()
    with pikepdf.open(io.BytesIO(datos)) as pdf:
        validar_xmp(pdf)
        with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False, strict=True) as meta:
            if "/CreationDate" in cambios:
                valor = cambios["/CreationDate"].isoformat()
                meta["xmp:CreateDate"] = valor
                for clave in ("dc:created", "dcterms:created"):
                    if clave in meta:
                        meta[clave] = valor
            if "/ModDate" in cambios:
                valor = cambios["/ModDate"].isoformat()
                meta["xmp:ModifyDate"] = valor
                if "dcterms:modified" in meta:
                    meta["dcterms:modified"] = valor
            if fecha_metadatos is not None:
                meta["xmp:MetadataDate"] = fecha_metadatos.isoformat()
        pdf.save(salida)
    return salida.getvalue()


def verificar_resultado(datos, original, cambios, con_xmp, fecha_metadatos=None):
    resultado = abrir_pdf(datos)
    if len(resultado.pages) != len(original.pages):
        raise ValueError("La verificacion del numero de paginas ha fallado.")
    info = resultado.metadata
    if info is None:
        raise ValueError("El resultado no contiene los metadatos esperados.")
    for clave, fecha in cambios.items():
        if info.get(clave) != pdf_date(fecha):
            raise ValueError(f"La verificacion de {clave} ha fallado.")
    info_original = original.metadata
    for clave in ("/CreationDate", "/ModDate"):
        if clave not in cambios:
            anterior = info_original.get(clave) if info_original is not None else None
            if info.get(clave) != anterior:
                raise ValueError(f"Se ha alterado una fecha no seleccionada: {clave}")
    if con_xmp:
        esperado = (fecha_metadatos.isoformat() if fecha_metadatos is not None
                    else leer_fecha_metadatos(original.stream.getvalue()))
        if leer_fecha_metadatos(datos) != esperado:
            raise ValueError("La verificacion de xmp:MetadataDate ha fallado.")
        with pikepdf.open(io.BytesIO(datos)) as pdf:
            validar_xmp(pdf)
            with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False, strict=True) as meta:
                for clave_info, clave_xmp in (
                    ("/CreationDate", "xmp:CreateDate"),
                    ("/ModDate", "xmp:ModifyDate"),
                ):
                    if clave_info in cambios and meta.get(clave_xmp) != cambios[clave_info].isoformat():
                        raise ValueError(f"La verificacion de {clave_xmp} ha fallado.")

def preparar_pdf(reader, cambios, con_xmp, fecha_metadatos=None):
    writer = PdfWriter(clone_from=reader)
    salida = io.BytesIO()
    try:
        # No se asignan cadenas directamente a writer.metadata.
        # add_metadata realiza la conversion a objetos PDF.
        writer.add_metadata({
            clave: pdf_date(fecha)
            for clave, fecha in cambios.items()
        })
        writer.write(salida)
    finally:
        writer.close()
    datos = salida.getvalue()
    if con_xmp:
        datos = actualizar_xmp(datos, cambios, fecha_metadatos)
    verificar_resultado(datos, reader, cambios, con_xmp, fecha_metadatos)
    return datos
def elegir_destino(origen):
    print("\nDonde guardar?")
    print("  [1] Sobrescribir el mismo archivo")
    print("  [2] Archivo nuevo")
    print("  [c] Cancelar")
    opcion = pedir_opcion("> ", {"1", "2", "c"})
    if opcion == "c":
        return None
    if opcion == "1":
        destino = origen
    else:
        entrada = input(
            "Ruta o nombre de salida "
            "(vacio = cancelar): "
        ).strip()
        if not entrada:
            return None
        destino = limpiar_ruta(entrada)
        if not destino.is_absolute():
            destino = origen.parent / destino
        if destino.suffix.lower() != ".pdf":
            destino = Path(str(destino) + ".pdf")
        destino = destino.resolve()
    if not destino.parent.is_dir():
        raise ValueError(
            f"No existe la carpeta: {destino.parent}"
        )
    if destino.exists():
        if not destino.is_file():
            raise ValueError("El destino no es un archivo.")
        print(f"\nEl archivo ya existe:\n  {destino}")
        if not confirmar("Confirmas que quieres sobrescribirlo?"):
            return None
    return destino
def guardar_seguro(destino, datos):
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".pdf_dates_",
            suffix=".tmp",
            dir=destino.parent,
            delete=False,
        ) as archivo:
            temporal = Path(archivo.name)
            archivo.write(datos)
            archivo.flush()
            os.fsync(archivo.fileno())
        # El destino solo se sustituye cuando la escritura
        # del archivo temporal ha terminado.
        os.replace(temporal, destino)
        temporal = None
    finally:
        if temporal is not None:
            try:
                temporal.unlink(missing_ok=True)
            except OSError as exc:
                print(
                    "Aviso: no se pudo eliminar el temporal "
                    f"{temporal}: {exc}"
                )
def sincronizar_fechas_archivo(destino, fechas):
    """Actualiza y comprueba Creado/Modificado en Windows; no asigna Ultimo acceso."""
    if os.name != "nt":
        raise OSError("La sincronizacion de Creado/Modificado requiere Windows.")
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.HANDLE]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.SetFileTime.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                    ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
    kernel32.SetFileTime.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    def convertir(fecha):
        if fecha is None:
            return None
        if fecha.tzinfo is None or fecha.utcoffset() is None:
            raise ValueError("No se sincronizan fechas del archivo sin zona horaria.")
        delta = fecha.astimezone(timezone.utc) - datetime(1601, 1, 1, tzinfo=timezone.utc)
        ticks = ((delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds) * 10
        if ticks <= 0 or ticks >= 2**63:
            raise ValueError("Fecha fuera del rango admitido por Windows (posterior a 1601).")
        return wintypes.FILETIME(ticks & 0xffffffff, ticks >> 32)

    creacion = fechas.get("/CreationDate")
    modificacion = fechas.get("/ModDate")
    ft_creacion = convertir(creacion)
    ft_modificacion = convertir(modificacion)
    if ft_creacion is None and ft_modificacion is None:
        raise ValueError("No hay fechas PDF con zona horaria que sincronizar.")
    handle = kernel32.CreateFileW(str(Path(destino).resolve()), 0x100, 0x7,
                                  None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel32.SetFileTime(handle,
                                   ctypes.byref(ft_creacion) if ft_creacion is not None else None,
                                   None,
                                   ctypes.byref(ft_modificacion) if ft_modificacion is not None else None):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel32.CloseHandle(handle)
    estado = Path(destino).stat()
    for etiqueta, fecha, valor in (("Creado", creacion, estado.st_birthtime),
                                   ("Modificado", modificacion, estado.st_mtime)):
        if fecha is not None and abs(valor - fecha.timestamp()) > 0.001:
            raise OSError(f"Windows no ha conservado la fecha solicitada para {etiqueta}.")


def main():
    print("=" * 62)
    print("  PDF Dates - Editor de fechas de metadatos")
    print("=" * 62)
    print(
        "Aviso: modificar un PDF puede invalidar "
        "sus firmas digitales."
    )
    print("Prueba primero con una copia.")
    while True:
        entrada = input(
            "\nRuta del PDF (o 'salir'): "
        ).strip()
        if not entrada or entrada.lower() == "salir":
            return 0
        try:
            ruta = limpiar_ruta(entrada).resolve()
            if not ruta.is_file():
                raise ValueError(
                    f"No encuentro el archivo: {ruta}"
                )
            datos_originales = ruta.read_bytes()
            reader = abrir_pdf(datos_originales)
            print(
                "\n-- Fechas INFO y campos XMP consultados --"
            )
            originales = mostrar_info(reader)
            mostrar_xmp(datos_originales)
            print("\nCada fecha tiene su propia zona horaria.")
            print("Al editarla, escribe la fecha y despues su offset (ejemplo: +02:00).")
            print("Enter en el offset conserva la zona de esa fecha; si no tiene, usa UTC.")
            print("La hora manual se guarda tal como la escribas, sin convertirla.")
            print("\nQue quieres cambiar?")
            print("  [c] Fecha de creacion")
            print("  [m] Fecha de modificacion")
            print("  [t] Creacion y modificacion")
            if pikepdf is not None:
                print("  [d] Solo xmp:MetadataDate")
            print("  [s] Salir")
            opcion = pedir_opcion(
                "> ",
                {"c", "m", "t", "d", "s"} if pikepdf is not None else {"c", "m", "t", "s"},
            )
            if opcion == "s":
                return 0
            cambios = {}
            campos = (
                (
                    "c",
                    "/CreationDate",
                    "Nueva fecha de CREACION",
                ),
                (
                    "m",
                    "/ModDate",
                    "Nueva fecha de MODIFICACION",
                ),
            )
            for letra, clave, etiqueta in campos:
                if opcion in (letra, "t"):
                    fecha = pedir_fecha_con_zona(etiqueta, originales.get(clave))
                    if fecha is not None:
                        cambios[clave] = fecha
            if not cambios and opcion != "d":
                print(
                    "No has introducido ninguna fecha. Cancelado."
                )
                continue
            con_xmp = opcion == "d"
            fecha_metadatos = None
            if pikepdf is not None and opcion != "d":
                con_xmp = confirmar(
                    "Actualizar tambien las fechas XMP?"
                )
            if not con_xmp:
                print(
                    "Aviso: XMP no se actualizara y puede "
                    "mostrar fechas distintas."
                )
            else:
                fecha_metadatos = pedir_fecha_metadatos(datos_originales)
                if fecha_metadatos is None:
                    print("xmp:MetadataDate: se conserva sin cambios.")
            if not cambios and fecha_metadatos is None:
                print("No hay cambios. Cancelado.")
                continue
            print("\nCambios solicitados:")
            for clave, fecha in cambios.items():
                print(f"  {clave}: {fmt_date(fecha)}")
            if fecha_metadatos is not None:
                print(f"  xmp:MetadataDate: {fmt_date(fecha_metadatos)}")
            print(
                "\nUn nombre de salida sin carpeta se guardara junto al PDF original."
            )
            destino = elegir_destino(ruta)
            if destino is None:
                print("Guardado cancelado.")
                continue
            fechas_archivo = {}
            for clave in ("/CreationDate", "/ModDate"):
                fecha = cambios.get(clave, originales.get(clave))
                if fecha is not None and fecha.utcoffset() is not None:
                    fechas_archivo[clave] = fecha
            sincronizar = False
            if os.name == "nt" and fechas_archivo:
                print("\nFechas de Propiedades del archivo (Windows):")
                for clave, etiqueta in (("/CreationDate", "Creado"), ("/ModDate", "Modificado")):
                    if clave in fechas_archivo:
                        fecha = fechas_archivo[clave]
                        print(f"  {etiqueta}: {fmt_date(fecha)}; hora local de Windows: {fmt_date(fecha.astimezone())}")
                    else:
                        print(f"  {etiqueta}: sin fecha PDF con zona; no se sincronizara.")
                print("Ultimo acceso no se sincroniza. Windows muestra las horas en su zona local.")
                sincronizar = confirmar("Sincronizar tambien Creado y Modificado con las fechas INFO del PDF?")
            resultado = preparar_pdf(
                reader,
                cambios,
                con_xmp,
                fecha_metadatos,
            )
            guardar_seguro(destino, resultado)
            if sincronizar:
                try:
                    sincronizar_fechas_archivo(destino, fechas_archivo)
                except Exception as exc:
                    print(f"\n[ERROR] El PDF se ha guardado en {destino}, pero no se pudo completar o verificar la sincronizacion del archivo: {exc}")
                    print("Las fechas del archivo pueden haber quedado parcialmente actualizadas.")
                    return 1
                print("Fechas del archivo: actualizadas y verificadas.")
            print(f"\n[OK] Guardado en: {destino}")
            print(
                "El resultado se ha reabierto y las fechas "
                "se han verificado antes de guardarlo."
            )
            if con_xmp:
                print("XMP: actualizado.")
            else:
                print("XMP: no actualizado.")
        except Exception as exc:
            print(
                f"\n[ERROR] {type(exc).__name__}: {exc}"
            )
            print(
                "Se detiene la operacion. "
                "Revisa el error antes de continuar."
            )
            return 1
if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("\nInterrumpido.")
        raise SystemExit(130)
