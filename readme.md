# 🎧 VoluMatch — Normalizador de Volumen LUFS

**VoluMatch** es una aplicación de escritorio para Windows que ajusta automáticamente el volumen de tus canciones MP3, asegurando que todas suenen a un mismo nivel. Utiliza el estándar **LUFS (Loudness Units Full Scale)** para una normalización auditiva profesional.

---

## 🔑 Características principales

- 🎵 Normalización de volumen auditiva (LUFS)
- 🎚️ Ajuste del nivel objetivo (por defecto −16 LUFS)
- 🖼️ Conserva metadatos y carátula de los MP3
- 📋 Interfaz tipo Excel para gestionar archivos
- 🖱️ Menú contextual para eliminar canciones
- 🧾 Consola integrada para ver el proceso

---

## 📸 Capturas de pantalla

![VoluMatch UI](assets/logo.png) <!-- reemplaza por una captura real si tienes -->

---

## 🚀 Cómo usar

1. Abre la app `VoluMatch.exe`
2. Gestiona tus canciones (agrega, elimina, revisa)
3. Selecciona carpeta de salida
4. Elige tu nivel de volumen objetivo (LUFS)
5. Haz clic en “Normalizar volumen”

---

## 🛠 Compilación del `.exe`

Si quieres compilar tú mismo:

```bash
py -3.11 -m pip install pyinstaller
py -3.11 -m PyInstaller --onefile --noconsole --name "VoluMatch" --icon volumatch.ico --add-binary "ffmpeg.exe;." VolumeNormalizerApp.py
