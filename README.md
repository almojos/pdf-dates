# PDF Dates

Aplicación portable para Windows que permite editar las fechas internas de un PDF y, opcionalmente, sincronizar las fechas **Creado** y **Modificado** de su archivo.

## Descargar y usar

En **Releases → v1.0.0**, descarga `PDF-Dates-1.0.0-Windows.zip`, pulsa **Extraer todo** y abre `PDF Dates.exe`.

No requiere instalar Python, servidor ni cuenta. Los documentos se procesan localmente.

Autoría del código propio: **almojos**. Licencia: **MIT**. Las dependencias conservan sus propias licencias.

## Funciones

- Fechas de creación y modificación INFO.
- Actualización opcional de las fechas XMP equivalentes.
- `xmp:MetadataDate` independiente.
- Fecha, hora y offset propios en cada campo.
- Modos **Conservar**, **Editar** y **Ahora**.
- Sincronización opcional de **Creado** y **Modificado** de Windows con las fechas INFO finales.
- Guardado como copia o sobrescritura confirmada con respaldo `.bak` exclusivo.
- Verificación del PDF guardado, de los respaldos y de las fechas sincronizadas.
- Rechazo de PDFs cifrados y paquetes XMP dañados.

**Advertencia:** reescribir un PDF puede invalidar sus firmas digitales. Prueba primero con una copia. Windows muestra las fechas del archivo en la zona local del equipo; los offsets del PDF son fijos. «Último acceso» no se sincroniza.

## Estructura

| Archivo | Contenido |
| --- | --- |
| `pdf_dates_app.py` | Interfaz gráfica Tk/ttk y operaciones de guardado |
| `pdf_dates_core.py` | Lectura, escritura y comprobación de metadatos y fechas Windows |
| `tests/` | Pruebas con documentos generados, nunca documentos personales |
| `PDF Dates.spec` | Receta de PyInstaller |
| `build_windows.cmd` | Compilación desde la carpeta del proyecto |
| `requirements.txt` | Versiones de dependencias utilizadas |
| `LEEME.txt` | Instrucciones de uso |
| `THIRD_PARTY_LICENSES.txt` | Avisos y licencias de las dependencias |
| `VERIFICACION.json` | Resultado de comprobación de la versión 1.0.0 y hash del ejecutable |

Los ejecutables, ZIPs, PDFs y archivos temporales no forman parte del historial Git. La aplicación compilada se distribuye como un archivo adjunto de la release.

## Desarrollo y compilación (Windows)

La versión 1.0.0 se construyó y probó con Python 3.14.7 de 64 bits, Tk 9 y las dependencias de `requirements.txt`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --distpath dist --workpath build "PDF Dates.spec"
```

El ejecutable queda en `dist/PDF Dates.exe`. No está firmado con un certificado comercial.

El modo diagnóstico `--self-test CARPETA` crea sus documentos y su informe únicamente dentro de una **subcarpeta nueva**, sin reemplazar los archivos que ya existan en la carpeta indicada. Es una comprobación adicional del ejecutable, no una certificación de todos los PDFs ni de todas las versiones de Windows.

## Verificación de la versión 1.0.0

- Siete pruebas del código superadas en Windows 11 x64.
- Ejecutable extraído del ZIP comprobado con PATH mínimo y sin las variables de desarrollo Python/Tcl.
- Guardado y reapertura, INFO/XMP, fechas del archivo, respaldos, entradas inválidas y cambios externos comprobados.
- Integridad ZIP y hash del ejecutable comprobados.

Consulta `LEEME.txt` para las limitaciones y las precauciones completas.

## Licencia

El código propio de PDF Dates se publica bajo **MIT**, con `Copyright (c) 2026 almojos`; consulta [LICENSE](LICENSE). Esto incluye el código propio de la versión 1.0.0 desde su revisión inicial.

La licencia MIT **no sustituye** las de las bibliotecas, el runtime ni otros componentes ajenos. Conserva [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt) y [THIRD_PARTY_SOURCES.md](THIRD_PARTY_SOURCES.md) al redistribuir la aplicación.

El ZIP portable incorpora la licencia propia, los avisos de terceros y la distribución de fuentes original de **pikepdf 10.17.0**, componente MPL-2.0, en `Fuentes-terceros/pikepdf-10.17.0.tar.gz`. Los enlaces a sus fuentes y su hash están en `THIRD_PARTY_SOURCES.md`.

Esta revisión del paquete añade documentación de licencias y fuentes de terceros; **el ejecutable y su funcionamiento no cambian**. La etiqueta original `v1.0.0` conserva su commit histórico, y la documentación actual de licencias se facilita en este repositorio y en el ZIP actualizado de la release.
