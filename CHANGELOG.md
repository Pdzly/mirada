# Cambios

## 0.2.0 — 2026-11-25

- Código abierto con licencia MIT; Qt pasa de PyQt6 a PySide6 (LGPL).
- Código separado en módulos e instalable como paquete (`pip`, `pipx`, `uv`).
- Configuración validada al cargar: un archivo dañado ya no impide abrir Mirada.
- Guardado atómico de la configuración.
- Control remoto: código secreto más largo, comparación en tiempo constante y solo comandos conocidos.
- Instalador: se corrige el falso aviso de bibliotecas faltantes; se agrega `uninstall.sh` e icono propio.
- Opciones `--version` y `--help`.
- Tests e integración continua en GitHub Actions.

## 0.1.0

- Primera versión: modo notch y flotante, seguimiento por voz, secciones y control remoto.
