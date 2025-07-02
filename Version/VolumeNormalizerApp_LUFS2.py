import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import tkinter.ttk as ttk
from pydub import AudioSegment
from mutagen.id3 import ID3, ID3NoHeaderError
import os
import numpy as np
import subprocess
import tempfile
import shutil
import re

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
        analyze_cmd = [
            "ffmpeg", "-i", input_path,
            "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-"
        ]
        result = subprocess.run(analyze_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        analysis = result.stderr
        match_input = re.search(r'"input_i"\s*:\s*"?(-?\d+\.\d+)', analysis)
        match_gain = re.search(r'"input_gain"\s*:\s*"?(-?\d+\.\d+)', analysis)
        input_lufs = float(match_input.group(1)) if match_input else None
        gain_db = float(match_gain.group(1)) if match_gain else None

        tmp_out = tempfile.mktemp(suffix=".mp3")
        norm_cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
            "-ar", "44100",
            "-ac", "2",
            "-b:a", "192k",
            tmp_out
        ]
        subprocess.run(norm_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        shutil.move(tmp_out, output_path)

        return input_lufs, gain_db
    except Exception as e:
        print(f"Error en loudnorm: {e}")
        return None, None

# ---------------------- APP PRINCIPAL ----------------------

class VolumeNormalizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Normalizador de Volumen (LUFS)")
        self.target_paths = []
        self.output_folder = None

        lufs_frame = tk.Frame(root)
        lufs_frame.pack(pady=5)
        tk.Label(lufs_frame, text="LUFS objetivo:").pack(side="left")
        self.lufs_entry = tk.Entry(lufs_frame, width=6)
        self.lufs_entry.pack(side="left")
        self.lufs_entry.insert(0, "-16")
        tk.Button(lufs_frame, text="¿Qué valor usar?", command=self.show_lufs_info).pack(side="left", padx=10)

        tk.Button(root, text="Seleccionar canciones a normalizar", command=self.select_targets).pack(pady=5)
        tk.Button(root, text="Seleccionar carpeta de salida", command=self.select_output_folder).pack(pady=5)
        tk.Button(root, text="Normalizar volumen", command=self.normalize).pack(pady=10)

        self.console = scrolledtext.ScrolledText(root, height=12, width=90, state='disabled', bg="#111", fg="#0f0")
        self.console.pack(padx=10, pady=10)

    def log(self, message):
        self.console.configure(state='normal')
        self.console.insert(tk.END, message + '\n')
        self.console.see(tk.END)
        self.console.configure(state='disabled')
        self.console.update_idletasks()

    def select_targets(self):
        files = filedialog.askopenfilenames(filetypes=[("Archivos MP3", "*.mp3")])
        self.target_paths = list(files)
        self.log(f"[Objetivo] {len(files)} canciones seleccionadas")
        messagebox.showinfo("Canciones seleccionadas", f"{len(files)} archivos seleccionados")

    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.log(f"[Salida] Carpeta: {folder}")
            messagebox.showinfo("Carpeta de salida", f"Carpeta seleccionada:\n{folder}")

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
                input_lufs, gain_db = normalize_with_ffmpeg_loudnorm(path, output_path, target_lufs)

                if input_lufs is not None and gain_db is not None:
                    self.log(f"  🎚 LUFS antes: {input_lufs:.1f} → después: {target_lufs:.1f}")
                    self.log(f"  🔊 Corrección aplicada: {gain_db:+.1f} dB")
                else:
                    self.log("  ⚠ No se pudo obtener el análisis LUFS. El archivo fue normalizado sin mostrar valores.")

                apply_metadata(path, output_path)
                self.log(f"  ✓ Guardado: {output_path}")
                ok += 1

            except Exception as e:
                self.log(f"  ✗ Error en {path}: {e}")
                errores += 1

        self.log("\n🎉 Normalización finalizada.")
        self.log(f"  Archivos exitosos: {ok}")
        self.log(f"  Con errores: {errores}")

    def show_lufs_info(self):
        popup = tk.Toplevel(self.root)
        popup.title("Valores LUFS sugeridos")
        popup.geometry("520x360")
        popup.resizable(False, False)

        texto = (
            "🎚️ ¿Qué es LUFS?\n"
            "LUFS (Loudness Units Full Scale) mide el volumen que realmente percibimos.\n"
            "Entre más bajo el número (más negativo), más suave se escucha.\n\n"
            "📏 Ejemplos comunes:\n"
            "  🎬  −23 LUFS   Muy bajo (televisión europea)\n"
            "  🎙️  −18 LUFS   Moderado\n"
            "  🎧  −16 LUFS   Recomendado para música y podcast\n"
            "  🎵  −14 LUFS   Fuerte, ideal para Spotify o YouTube\n"
            "  🔊  −12 LUFS   Muy fuerte\n"
            "  🚨  −10 LUFS   Riesgo de distorsión\n\n"
            "💡 Recomendaciones:\n"
            "✔ Usa −16 LUFS para un sonido natural y balanceado.\n"
            "✔ Usa −14 LUFS si vas a subir a plataformas de streaming.\n"
            "✘ Evitá valores mayores a −10 LUFS, puede sonar saturado."
        )

        label = tk.Label(popup, text=texto, justify="left", font=("Segoe UI", 11), padx=20, pady=20)
        label.pack()
        btn = tk.Button(popup, text="Cerrar", command=popup.destroy)
        btn.pack(pady=10)

if __name__ == "__main__":
    root = tk.Tk()
    app = VolumeNormalizerApp(root)
    root.mainloop()
