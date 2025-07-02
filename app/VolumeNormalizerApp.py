import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Menu
import tkinter.ttk as ttk
from pydub import AudioSegment
from mutagen.id3 import ID3, ID3NoHeaderError
import os
import numpy as np
import subprocess
import tempfile
import shutil
import sys

# ---------------------- RUTA DE FFMPEG ----------------------

def get_ffmpeg_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'ffmpeg.exe')
    else:
        return os.path.abspath("ffmpeg.exe")

# ---------------------- FUNCIONES DE AUDIO ----------------------

def get_rms(audio):
    samples = np.array(audio.get_array_of_samples())
    return np.sqrt(np.mean(samples.astype(np.float64) ** 2))

def apply_metadata(src_path, dst_path):
    try:
        src_tags = ID3(src_path)
        try:
            dst_tags = ID3(dst_path)
        except ID3NoHeaderError:
            dst_tags = ID3()
        dst_tags.clear()
        for frame in src_tags.values():
            dst_tags.add(frame)
        dst_tags.save(dst_path)
    except Exception as e:
        print(f"Error copiando metadatos: {e}")

def normalize_with_ffmpeg_loudnorm(input_path, output_path, target_lufs=-16.0):
    try:
        tmp_out = tempfile.mktemp(suffix=".mp3")
        norm_cmd = [
            get_ffmpeg_path(), "-y",
            "-i", input_path,
            "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
            "-ar", "44100",
            "-ac", "2",
            "-b:a", "192k",
            tmp_out
        ]
        subprocess.run(norm_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        shutil.move(tmp_out, output_path)
        return True
    except Exception as e:
        print(f"Error en loudnorm: {e}")
        return False

# ---------------------- APP PRINCIPAL ----------------------

class VolumeNormalizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎧 VoluMatch — Normalizador de Volumen LUFS")
        self.target_paths = []
        self.output_folder = None

        lufs_frame = tk.Frame(root)
        lufs_frame.pack(pady=5)
        lufs_container = tk.Frame(lufs_frame)
        lufs_container.pack()
        tk.Label(lufs_container, text="LUFS objetivo:").pack(side="left")
        self.lufs_entry = tk.Entry(lufs_container, width=6)
        self.lufs_entry.pack(side="left", padx=(5, 5))
        self.lufs_entry.insert(0, "-16")
        tk.Button(lufs_container, text="ℹ️", width=2, command=self.show_lufs_info).pack(side="left", padx=(5, 0))

        tk.Button(root, text="Gestionar canciones", command=self.open_excel_window).pack(pady=5)
        tk.Button(root, text="Seleccionar carpeta de salida", command=self.select_output_folder).pack(pady=5)
        tk.Button(root, text="Normalizar volumen", command=self.normalize).pack(pady=10)

        self.console = scrolledtext.ScrolledText(root, height=12, width=90, state='disabled', bg="#111", fg="#0f0")
        self.console.pack(padx=10, pady=10)
        self.console.configure(font=("Consolas", 10))

    def log(self, message):
        self.console.configure(state='normal')
        self.console.insert(tk.END, message + '\n')
        self.console.see(tk.END)
        self.console.configure(state='disabled')
        self.console.update_idletasks()

    def open_excel_window(self):
        self.excel_win = tk.Toplevel(self.root)
        self.excel_win.title("Canciones a normalizar")

        self.tree = ttk.Treeview(self.excel_win, columns=("Archivo", "Duración", "RMS"), show="headings", selectmode="extended")
        for col in ("Archivo", "Duración", "RMS"):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=250 if col == "Archivo" else 100)
        self.tree.pack(expand=True, fill="both")

        self.tree.bind("<Button-3>", self.show_context_menu)

        btn_frame = tk.Frame(self.excel_win)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Agregar canciones", command=self.select_targets).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Eliminar seleccionadas", command=self.delete_selected).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Eliminar todo", command=self.clear_all).pack(side="left", padx=5)

    def show_context_menu(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        menu = Menu(self.excel_win, tearoff=0)
        menu.add_command(label="Eliminar", command=self.delete_selected)
        menu.post(event.x_root, event.y_root)

    def select_targets(self):
        files = filedialog.askopenfilenames(filetypes=[("Archivos MP3", "*.mp3")])
        for f in files:
            try:
                audio = AudioSegment.from_mp3(f)
                duration = round(len(audio) / 1000, 1)
                rms = round(get_rms(audio), 2)
                self.tree.insert("", "end", values=(f, f"{duration}s", rms))
                self.target_paths.append(f)
            except Exception as e:
                self.log(f"Error cargando {f}: {e}")

    def delete_selected(self):
        selected = self.tree.selection()
        for item in selected:
            path = self.tree.item(item)['values'][0]
            if path in self.target_paths:
                self.target_paths.remove(path)
            self.tree.delete(item)

    def clear_all(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.target_paths.clear()

    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.log(f"[Salida] Carpeta: {folder}")
            messagebox.showinfo("Carpeta de salida", f"Carpeta seleccionada:\n{folder}")

    def show_lufs_info(self):
        popup = tk.Toplevel(self.root)
        popup.title("Valores LUFS sugeridos")
        popup.geometry("520x360")
        popup.resizable(False, False)

        texto = """🎚️ ¿Qué es LUFS?
LUFS (Loudness Units Full Scale) mide el volumen que realmente percibimos.
Entre más bajo el número (más negativo), más suave se escucha.

📏 Ejemplos comunes:
  🎬  −23 LUFS   Muy bajo (televisión europea)
  🎙️  −18 LUFS   Moderado
  🎧  −16 LUFS   Recomendado para música y podcast
  🎵  −14 LUFS   Fuerte, ideal para Spotify o YouTube
  🔊  −12 LUFS   Muy fuerte
  🚨  −10 LUFS   Riesgo de distorsión

💡 Recomendaciones:
✔ Usa −16 LUFS para un sonido natural y balanceado.
✔ Usa −14 LUFS si vas a subir a plataformas de streaming.
✘ Evitá valores mayores a −10 LUFS, puede sonar saturado."""

        text_widget = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=("Segoe UI", 11))
        text_widget.insert(tk.END, texto.strip())
        text_widget.config(state="disabled")
        text_widget.pack(expand=True, fill="both", padx=10, pady=10)
        tk.Button(popup, text="Cerrar", command=popup.destroy).pack(pady=10)

    def normalize(self):
        if not self.target_paths or not self.output_folder:
            messagebox.showerror("Faltan datos", "Por favor selecciona canciones y carpeta de salida.")
            return

        total = len(self.target_paths)
        ok = 0
        errores = 0

        for idx, path in enumerate(self.target_paths, 1):
            try:
                filename = os.path.basename(path)
                self.log(f"\n[{idx}/{total}] {filename}")
                output_path = os.path.join(self.output_folder, filename)

                try:
                    target_lufs = float(self.lufs_entry.get())
                except ValueError:
                    self.log("  ✗ LUFS inválido, usando −16 por defecto.")
                    target_lufs = -16.0

                self.log("  Normalizando con loudnorm (LUFS)...")
                success = normalize_with_ffmpeg_loudnorm(path, output_path, target_lufs)
                if success:
                    apply_metadata(path, output_path)
                    self.log(f"  ✓ Guardado: {output_path}")
                    ok += 1
                else:
                    raise Exception("ffmpeg falló")

            except Exception as e:
                self.log(f"  ✗ Error en {path}: {e}")
                errores += 1

        self.log("\n🎉 Normalización finalizada.")
        self.log(f"  Archivos exitosos: {ok}")
        self.log(f"  Con errores: {errores}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VolumeNormalizerApp(root)
    root.mainloop()
