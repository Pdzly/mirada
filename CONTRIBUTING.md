# Cómo contribuir

¡Gracias por tu interés! Las contribuciones son bienvenidas: errores, ideas, traducciones y código.

## Reportar un error

Abre un *issue* con:

- Distribución y versión (por ejemplo, Ubuntu 24.04, Fedora 41).
- Escritorio y sesión: GNOME/KDE/otro, Wayland o X11 (`echo $XDG_SESSION_TYPE`).
- Versión de Mirada (`mirada --version`).
- Qué hiciste, qué esperabas y qué pasó. Si hay un error en la terminal, pégalo.

## Enviar cambios

1. Haz un *fork* y crea una rama: `git checkout -b mi-mejora`.
2. Prepara el entorno:
   ```bash
   python3 -m venv .venv && . .venv/bin/activate
   pip install -e '.[dev]'
   ```
3. Antes de abrir el *pull request*, comprueba que todo pasa:
   ```bash
   ruff check .
   pytest
   ```
4. Describe qué cambia y por qué. Si cambia la interfaz, agrega una captura.

## Estructura

| Archivo | Contenido |
|---|---|
| `src/mirada/config.py` | Configuración, validación y utilidades sin Qt |
| `src/mirada/audio.py` | Detección de voz por volumen |
| `src/mirada/remote.py` | Servidor del control remoto |
| `src/mirada/prompter.py` | Ventana del prompter |
| `src/mirada/settings.py` | Diálogo de ajustes |
| `src/mirada/app.py` | Ventana principal y punto de entrada |

## Estilo

- Código y comentarios en español o inglés; mantén el idioma del archivo que editas.
- Líneas de hasta 120 caracteres (lo revisa `ruff`).
- La lógica que no depende de Qt va en funciones pequeñas con tests.
