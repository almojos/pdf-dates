# Licencias y código fuente de terceros

## Alcance de MIT

El código original de **PDF Dates** se ofrece bajo la licencia MIT de `LICENSE`, con el aviso:

```text
Copyright (c) 2026 almojos
```

Esta autorización comprende el código propio de la versión 1.0.0, incluida la revisión inicial `a01600346604c18699c6b06f5284e9fd0940a0e4`. No cambia las licencias ni los avisos de los componentes ajenos, sus datos, el intérprete o las bibliotecas nativas incluidos en el ejecutable.

## pikepdf 10.17.0 — MPL-2.0

El ejecutable redistribuye pikepdf 10.17.0, sin modificaciones propias de su código fuente. pikepdf conserva la licencia **Mozilla Public License 2.0**. Su texto y los avisos de sus componentes están en `THIRD_PARTY_LICENSES.txt`.

El código fuente correspondiente puede obtenerse de estas formas, sin registro:

- En el ZIP portable de PDF Dates: **`Fuentes-terceros/pikepdf-10.17.0.tar.gz`**.
- Distribución de fuentes original de PyPI: <https://files.pythonhosted.org/packages/b8/c3/8fc5695947a711263e17786c1d913b0cea660a1b174a9e0e944ad037732c/pikepdf-10.17.0.tar.gz>.
- Página de la versión: <https://pypi.org/project/pikepdf/10.17.0/#files>.
- Proyecto: <https://github.com/pikepdf/pikepdf>.

SHA-256 de la distribución de fuentes:

```text
de4ccaae83628e86c1fd473b384c09c6ff1dd35a583a8dacbf61d2aa4bea843b
```

El archivo de fuentes se distribuye sin modificar, con sus instrucciones de compilación, licencias y avisos originales. La licencia MIT de PDF Dates no reemplaza las condiciones MPL de estos archivos. Al redistribuir el paquete, conserva la información sobre el acceso a estas fuentes y los avisos correspondientes.

## Otros componentes

`requirements.txt` identifica las versiones de las dependencias Python utilizadas para construir esta distribución. `THIRD_PARTY_LICENSES.txt` reúne los textos aportados por sus distribuciones y por el runtime utilizado, incluidos los avisos de componentes nativos.

Entre los componentes se encuentran pypdf, Pillow, lxml, packaging, pikepdf y sus bibliotecas nativas, Python/Tcl/Tk y el cargador de PyInstaller. **No se afirma que todos estén bajo MIT.** Los derechos, condiciones y excepciones de cada componente son los de sus propios avisos.

Las fuentes de las dependencias Python se publican en las fichas de PyPI de las versiones fijadas en `requirements.txt`; las condiciones y componentes concretos de la distribución de pikepdf se describen además en sus avisos originales incluidos.
