import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import tkinter.ttk as ttk
from pydub import AudioSegment
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
from mutagen.mp3 import MP3
import os
import numpy as np

# ----------------------------- FUNCIONES AUDIO -----------------------------

def get_rms(audio):
    samples = np.array(audio.get_array_of_samples())
    return np.sqrt(np.mean(samples.astype(np.float64) ** 2))

def match_volume(target_rms, audio):
    audio_rms = get_rms(audio)
    if audio_rms == 0:
        return audio
    change_in_dB = 20 * np.log10(target_rms / audio_rms)
    return audio.apply_gain(change_in_dB)

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

# --------------------------- VENTANA EXCEL (TABLA) -------------------------

class SongSelector(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent.root)
        self.title("Seleccionar canciones")
        self.geometry("800x440")
        self.parent = parent

        self.original_data = []  # Guarda todos los datos sin filtrar

        columns = ("Archivo", "Duración", "RMS")
        self.table = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")
        for col in columns:
            self.table.heading(col, text=col)
            self.table.column(col, anchor="w", width=300 if col == "Archivo" else 80)
        self.table.pack(fill="both", expand=True, padx=10, pady=5)

        # Menú contextual
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

        # Botones inferiores
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
            rms = f"{rms_value:.2f}"
            row = (path, duration, rms)
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
        if not row_id:
            return

        # Evita borrar selección múltiple si ya hay varias
        if row_id not in self.table.selection():
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

    def __init__(self, parent):
        super().__init__(parent.root)
        self.title("Seleccionar canciones")
        self.geometry("720x340")
        self.parent = parent

        columns = ("Archivo", "Duración", "RMS")
        self.table = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended")
        for col in columns:
            self.table.heading(col, text=col)
            self.table.column(col, anchor="w", width=200 if col == "Archivo" else 80)
        self.table.pack(fill="both", expand=True, padx=10, pady=10)

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Eliminar", command=self.delete_selected)
        self.table.bind("<Button-3>", self.show_context_menu)

        tk.Button(self, text="Agregar canciones", command=self.add_files).pack(pady=5)
        tk.Button(self, text="Aceptar", command=self.finish_selection).pack()

        for path in self.parent.target_paths:
            self.insert_file(path)

    def insert_file(self, path):
        try:
            audio = AudioSegment.from_file(path)
            duration = get_duration_str(audio)
            rms = f"{get_rms(audio):.2f}"
            self.table.insert("", "end", values=(path, duration, rms))
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
            self.table.delete(i)

    def show_context_menu(self, event):
        row_id = self.table.identify_row(event.y)
        if row_id:
            self.table.selection_set(row_id)
            self.menu.post(event.x_root, event.y_root)

    def finish_selection(self):
        self.parent.target_paths = self.get_all_files()
        self.parent.log(f"[Actualizado] {len(self.parent.target_paths)} canciones seleccionadas.")
        self.destroy()

# ------------------------------ APP PRINCIPAL ------------------------------

class VolumeNormalizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Normalizador de Volumen")
        self.target_paths = []
        self.reference_path = None
        self.output_folder = None

        tk.Button(root, text="Seleccionar canción de referencia", command=self.select_reference).pack(pady=5)

        frame = tk.Frame(root)
        frame.pack(pady=5)
        tk.Button(frame, text="Seleccionar canciones a normalizar", command=self.select_targets).pack(side="left", padx=5)
        tk.Label(frame, text="⇨").pack(side="left")
        tk.Button(frame, text="Ver tabla", command=self.open_table).pack(side="left", padx=5)

        tk.Button(root, text="Seleccionar carpeta de salida", command=self.select_output_folder).pack(pady=5)
        tk.Button(root, text="Normalizar Volumen", command=self.normalize).pack(pady=10)

        self.console = scrolledtext.ScrolledText(root, height=10, width=85, state='disabled', bg="#111", fg="#0f0")
        self.console.pack(padx=10, pady=10)

    def log(self, message):
        self.console.configure(state='normal')
        self.console.insert(tk.END, message + '\n')
        self.console.see(tk.END)
        self.console.configure(state='disabled')
        self.console.update_idletasks()

    def select_reference(self):
        path = filedialog.askopenfilename(filetypes=[("Archivos MP3", "*.mp3")])
        if path:
            self.reference_path = path
            self.log(f"[Referencia] {path}")
            messagebox.showinfo("Referencia seleccionada", f"Canción de referencia:\n{path}")

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
        if not self.reference_path or not self.target_paths or not self.output_folder:
            messagebox.showerror("Faltan datos", "Por favor selecciona todos los elementos.")
            return

        self.log("Calculando volumen de referencia...")
        ref_audio = AudioSegment.from_file(self.reference_path)
        ref_rms = get_rms(ref_audio)
        self.log(f"Volumen de referencia: {ref_rms:.2f} RMS")

        for idx, path in enumerate(self.target_paths, 1):
            try:
                filename = os.path.basename(path)
                self.log(f"\n[{idx}/{len(self.target_paths)}] {filename}")
                audio = AudioSegment.from_file(path)
                original_rms = get_rms(audio)
                self.log(f"  RMS original: {original_rms:.2f}")

                adjusted_audio = match_volume(ref_rms, audio)
                final_rms = get_rms(adjusted_audio)
                dB_change = 20 * np.log10(ref_rms / original_rms) if original_rms != 0 else 0
                self.log(f"  Ganancia aplicada: {dB_change:+.2f} dB")
                self.log(f"  RMS final: {final_rms:.2f}")

                output_path = os.path.join(self.output_folder, filename)
                adjusted_audio.export(output_path, format="mp3", bitrate="192k")
                apply_metadata(path, output_path)

                self.log(f"  ✓ Guardado: {output_path}")
            except Exception as e:
                self.log(f"  ✗ Error en {path}: {e}")

        self.log("\n✔ Proceso completo.")
        messagebox.showinfo("Listo", "¡Canciones normalizadas!")

# ------------------------------ EJECUTAR APP -------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    app = VolumeNormalizerApp(root)
    root.mainloop()
