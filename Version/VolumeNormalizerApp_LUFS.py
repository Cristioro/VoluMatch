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

def get_duration_str(audio):
    sec = int(audio.duration_seconds)
    return f"{sec//60:02}:{sec%60:02}"

def normalize_with_ffmpeg_loudnorm(input_path, output_path, target_lufs=-16.0):
    try:
        # 1️⃣ Primer análisis (no escribe archivo)
        analyze_cmd = [
            "ffmpeg", "-i", input_path,
            "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-"
        ]
        result = subprocess.run(analyze_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        analysis = result.stderr

        # 2️⃣ Buscar LUFS original
        import re
        match = re.search(r'"input_i"\s*:\s*"?(-?\d+\.\d+)', analysis)
        input_lufs = float(match.group(1)) if match else None

        # 3️⃣ Normalizar realmente
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

        return input_lufs  # Devolvemos el LUFS original
    except Exception as e:
        print(f"Error en loudnorm: {e}")
        return None


# --------------------- TABLA DE CANCIONES ----------------------

class SongSelector(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent.root)
        self.title("Seleccionar canciones")
        self.geometry("800x440")
        self.parent = parent
        self.original_data = []

        columns = ("Archivo", "Duración", "RMS")
        self.table = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")
        for col in columns:
            self.table.heading(col, text=col)
            self.table.column(col, anchor="w", width=300 if col == "Archivo" else 80)
        self.table.pack(fill="both", expand=True, padx=10, pady=5)

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Eliminar seleccionados", command=self.delete_selected)
        self.table.bind("<Button-3>", self.show_context_menu)

        # Filtros
        filter_frame = tk.Frame(self)
        filter_frame.pack(pady=5)
        tk.Label(filter_frame, text="Buscar nombre:").pack(side="left")
        self.filter_name = tk.Entry(filter_frame, width=20)
        self.filter_name.pack(side="left", padx=5)
        tk.Label(filter_frame, text="RMS mínimo:").pack(side="left")
        self.filter_rms = tk.Entry(filter_frame, width=6)
        self.filter_rms.pack(side="left", padx=5)
        tk.Button(filter_frame, text="Aplicar filtro", command=self.apply_filters).pack(side="left", padx=5)
        tk.Button(filter_frame, text="Limpiar filtro", command=self.reset_filters).pack(side="left")

        # Botones
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Agregar canciones", command=self.add_files).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Eliminar seleccionados", command=self.delete_selected).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Eliminar todo", command=self.delete_all).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Aceptar", command=self.finish_selection).pack(side="left", padx=5)

        for path in self.parent.target_paths:
            self.insert_file(path)

    def insert_file(self, path):
        try:
            audio = AudioSegment.from_file(path)
            duration = get_duration_str(audio)
            rms_value = get_rms(audio)
            row = (path, duration, f"{rms_value:.2f}")
            self.original_data.append(row)
            self.table.insert("", "end", values=row)
        except Exception as e:
            print(f"No se pudo cargar {path}: {e}")

    def get_all_files(self):
        return [self.table.item(i)["values"][0] for i in self.table.get_children()]

    def add_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Archivos MP3", "*.mp3")])
        existing = self.get_all_files()
        for f in files:
            if f not in existing:
                self.insert_file(f)

    def delete_selected(self):
        selected = self.table.selection()
        for i in selected:
            path = self.table.item(i)["values"][0]
            self.original_data = [row for row in self.original_data if row[0] != path]
            self.table.delete(i)

    def delete_all(self):
        self.table.delete(*self.table.get_children())
        self.original_data = []

    def show_context_menu(self, event):
        row_id = self.table.identify_row(event.y)
        if row_id:
            current_selection = self.table.selection()
            if row_id not in current_selection:
                self.table.selection_set(row_id)
            self.menu.post(event.x_root, event.y_root)

    def apply_filters(self):
        name_filter = self.filter_name.get().lower()
        rms_min = self.filter_rms.get()
        try:
            rms_min = float(rms_min) if rms_min else None
        except ValueError:
            rms_min = None
        self.table.delete(*self.table.get_children())
        for row in self.original_data:
            filename, _, rms = row
            if name_filter and name_filter not in filename.lower():
                continue
            if rms_min is not None and float(rms) < rms_min:
                continue
            self.table.insert("", "end", values=row)

    def reset_filters(self):
        self.filter_name.delete(0, tk.END)
        self.filter_rms.delete(0, tk.END)
        self.table.delete(*self.table.get_children())
        for row in self.original_data:
            self.table.insert("", "end", values=row)

    def finish_selection(self):
        self.parent.target_paths = self.get_all_files()
        self.parent.log(f"[Actualizado] {len(self.parent.target_paths)} canciones seleccionadas.")
        self.destroy()

# --------------------- APP PRINCIPAL ----------------------

class VolumeNormalizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Normalizador de Volumen (LUFS)")
        self.target_paths = []
        self.output_folder = None

        lufs_frame = tk.Frame(root)
        lufs_frame.pack(pady=2)

        tk.Label(lufs_frame, text="LUFS objetivo:").pack(side="left")
        self.lufs_entry = tk.Entry(lufs_frame, width=5)
        self.lufs_entry.pack(side="left")
        self.lufs_entry.insert(0, "-16")
        tk.Button(lufs_frame, text="¿Qué valor usar?", command=self.show_lufs_info).pack(side="left", padx=8)


        tk.Button(root, text="Seleccionar canciones a normalizar", command=self.select_targets).pack(pady=5)
        tk.Button(root, text="Ver tabla", command=self.open_table).pack(pady=2)
        tk.Button(root, text="Seleccionar carpeta de salida", command=self.select_output_folder).pack(pady=5)
        tk.Button(root, text="Normalizar volumen", command=self.normalize).pack(pady=10)

        self.console = scrolledtext.ScrolledText(root, height=10, width=90, state='disabled', bg="#111", fg="#0f0")
        self.console.pack(padx=10, pady=10)

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

    def open_table(self):
        SongSelector(self)

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

        for idx, path in enumerate(self.target_paths, 1):
            try:
                filename = os.path.basename(path)
                self.log(f"\n[{idx}/{len(self.target_paths)}] {filename}")
                output_path = os.path.join(self.output_folder, filename)

                self.log("  Normalizando con loudnorm (LUFS)...")
                input_lufs = normalize_with_ffmpeg_loudnorm(path, output_path, target_lufs)

                if input_lufs is not None:
                    self.log(f"  🎚 LUFS antes: {input_lufs:.1f}  →  después: {target_lufs:.1f}")
                    apply_metadata(path, output_path)
                    self.log(f"  ✓ Guardado: {output_path}")
                else:
                    self.log(f"  ✗ Error procesando {filename}")
                if success:
                    apply_metadata(path, output_path)
                    self.log(f"  ✓ Guardado: {output_path}")
                else:
                    self.log(f"  ✗ Error procesando {filename}")
            except Exception as e:
                self.log(f"  ✗ Error en {path}: {e}")

        self.log("\n✔ Proceso completo.")
        messagebox.showinfo("Listo", "¡Canciones normalizadas!")

# --------------------- EJECUTAR APP ----------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = VolumeNormalizerApp(root)
    root.mainloop()
