# Mirada

**Teleprompter para Linux.** Muestra tu guion en una franja pegada al borde superior de la pantalla, justo bajo la cámara, para que leas mientras mantienes contacto visual. El texto avanza mientras hablas y se detiene cuando haces una pausa.

[English](README.en.md) · Licencia [MIT](LICENSE)

<!-- Agrega aquí una captura: docs/captura.png -->

## Características

- **Modo notch:** franja centrada bajo la webcam, siempre encima de las demás ventanas.
- **Modo flotante:** ventana que puedes mover y redimensionar.
- **Seguimiento por voz:** avanza solo mientras hablas (detecta volumen; no envía audio a ningún lado).
- **Secciones:** las líneas que empiezan con `#` se convierten en secciones a las que puedes saltar.
- **Control remoto** desde el teléfono en la misma Wi-Fi (opcional, desactivado por defecto).
- Modo espejo, cuenta regresiva, color y tamaño de letra, opacidad.

## Instalar

### Opción 1: instalador (recomendado)

```bash
git clone https://github.com/USUARIO/mirada.git
cd mirada
bash install.sh
```

Instala todo en tu usuario (`~/.local`), sin sudo, y agrega Mirada al menú de aplicaciones.

### Opción 2: pipx o uv

```bash
pipx install git+https://github.com/USUARIO/mirada.git
# o
uv tool install git+https://github.com/USUARIO/mirada.git
```

### Bibliotecas del sistema

Para el seguimiento por voz hace falta PortAudio, y Qt necesita `xcb-cursor`:

| Distribución | Comando |
|---|---|
| Debian / Ubuntu / Mint / Pop!_OS | `sudo apt install python3-venv libportaudio2 libxcb-cursor0` |
| Fedora | `sudo dnf install portaudio xcb-util-cursor` |
| Arch / Manjaro / CachyOS | `sudo pacman -S portaudio xcb-util-cursor` |
| openSUSE | `sudo zypper install libportaudio2 xcb-util-cursor` |

Sin PortAudio, Mirada funciona igual, pero avanza a velocidad fija.

### Desinstalar

```bash
bash uninstall.sh            # conserva tu configuración y guion
bash uninstall.sh --purge    # borra también ~/.config/mirada
```

## Uso

1. Abre **Mirada** desde el menú o ejecuta `mirada` (`mirada --start` abre directo el prompter).
2. Escribe o pega el guion. Las líneas que empiezan con `#` crean secciones.
3. **▶ Iniciar prompter** (Ctrl+Enter). Hay una cuenta regresiva de 3 s.
4. Habla: el texto avanza mientras hablas. La barra de color arriba muestra el volumen del micrófono.

| Tecla | Acción |
|---|---|
| Espacio | Pausar / reanudar |
| ↑ / ↓ | Más rápido / más lento |
| RePág / AvPág | Sección anterior / siguiente |
| 1-9 | Saltar a la sección N |
| Inicio | Volver al principio |
| V | Activar / desactivar voz |
| N | Alternar modo notch / flotante |
| M | Modo espejo |
| + / − | Tamaño de letra |
| Esc | Cerrar el prompter |

- Pasar el mouse sobre el prompter lo pausa. Clic en el icono ⏸ de la esquina para pausar sin dejar el mouse encima.
- Rueda del mouse: desplazamiento manual. Clic derecho: menú con la lista de secciones.

### Control remoto desde el teléfono

En **Ajustes**, activa **Control remoto**. En la barra inferior del editor aparece una dirección como `http://192.168.1.20:8765/?t=…`. Ábrela en el navegador del teléfono, conectado a la misma Wi-Fi. La dirección lleva un código secreto; sin él, el servidor no responde.

Si usas un firewall, abre el puerto solo para tu red local, por ejemplo con `ufw`:

```bash
sudo ufw allow from 192.168.1.0/24 to any port 8765 proto tcp
```

El tráfico va por HTTP sin cifrar: úsalo solo en redes de confianza.

## Limitaciones en Linux

- **Wayland:** Mirada se ejecuta vía XWayland para poder fijarse arriba y quedar sobre otras ventanas. Funciona en GNOME y KDE. Para forzar Wayland nativo: `MIRADA_WAYLAND=1 mirada` (puede perder el «siempre encima»).
- **Compartir pantalla:** Linux no tiene una forma estándar de ocultar una ventana en capturas. Comparte una ventana concreta, no la pantalla completa.
- **Voz:** detecta si estás hablando por el volumen, no reconoce palabras. Si hay ruido (ventilador, teclado), baja la sensibilidad o usa audífonos.

La configuración y el guion autoguardado están en `~/.config/mirada/`.

## Desarrollo

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
ruff check .
pytest
python -m mirada
```

Lee [CONTRIBUTING.md](CONTRIBUTING.md) antes de enviar cambios.

## Licencia

[MIT](LICENSE). Mirada usa [Qt for Python (PySide6)](https://doc.qt.io/qtforpython/), con licencia LGPL-3.0.
