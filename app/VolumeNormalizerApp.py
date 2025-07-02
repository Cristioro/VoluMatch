import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Menu
import tkinter.ttk as ttk
from pydub import AudioSegment
from mutagen.id3 import ID3, ID3NoHeaderError
from PIL import Image, ImageTk
import os
import numpy as np
import subprocess
import tempfile
import shutil
import sys

# ---------------------- UTILIDAD DE RUTA PORTABLE ----------------------

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

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
        return True
    except Exception as e:
        print(f"Error en loudnorm: {e}")
        return False

# ---------------------- APP PRINCIPAL ----------------------

class VolumeNormalizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VoluMatch — Normalizador LUFS")
        icon_path = resource_path("assets/VoluMatch.ico")
        self.root.iconbitmap(icon_path)
        self.target_paths = []
        self.output_folder = None

        # Estilos
        style = ttk.Style()
        style.configure("TButton", font=("Segoe UI", 10), padding=5)
        style.configure("TLabel", font=("Segoe UI", 10))

        # Botones de gestión
        action_frame = ttk.Frame(root)
        action_frame.pack(pady=5)
        ttk.Button(action_frame, text="🎼 Gestionar canciones", command=self.open_excel_window).pack(side="left", padx=10)
        ttk.Button(action_frame, text="📁 Carpeta de salida", command=self.select_output_folder).pack(side="left", padx=10)

        # LUFS y botón de normalizar
        top_frame = ttk.Frame(root)
        top_frame.pack(pady=10)

        ttk.Label(top_frame, text="LUFS objetivo:").pack(side="left", padx=(0, 5))
        self.lufs_entry = ttk.Entry(top_frame, width=6)
        self.lufs_entry.insert(0, "-16")
        self.lufs_entry.pack(side="left", padx=(0, 5))
        ttk.Button(top_frame, text="ℹ️", width=3, command=self.show_lufs_info).pack(side="left", padx=(0, 15))
        ttk.Button(top_frame, text="🎚️ Normalizar", command=self.normalize).pack(side="left")

        # Barra de progreso
        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=(5, 10))

        # Consola
        console_frame = ttk.LabelFrame(root, text="🖥 Consola")
        console_frame.pack(padx=10, pady=10, fill="both", expand=True)
        self.console = scrolledtext.ScrolledText(console_frame, height=12, width=90, state='disabled', bg="#111", fg="#0f0")
        self.console.configure(font=("Consolas", 10))
        self.console.pack(fill="both", expand=True)

        # Cargar logo (después de la consola)
        self.mostrar_logo()

    def log(self, message):
        self.console.configure(state='normal')
        self.console.insert(tk.END, message + '\n')
        self.console.see(tk.END)
        self.console.configure(state='disabled')
        self.console.update_idletasks()

    def mostrar_logo(self):
        logo_frame = tk.Frame(self.root)
        logo_frame.pack(pady=10)

        try:
            logo_path = resource_path("assets/VoluMatch.png")
            img = Image.open(logo_path)
            img = img.resize((200, 200), Image.Resampling.LANCZOS)  # reemplaza ANTIALIAS
            logo_img = ImageTk.PhotoImage(img)
            label_logo = tk.Label(logo_frame, image=logo_img, bg="white")
            label_logo.image = logo_img
            label_logo.pack()
        except Exception as e:
            self.log(f"⚠ No se pudo cargar el logo: {e}")

    def open_excel_window(self):
        self.excel_win = tk.Toplevel(self.root)
        self.excel_win.title("Canciones a normalizar")
        self.excel_win.grab_set()  # Bloquea la ventana principal (pero permite abrir diálogos normales)

        self.tree = ttk.Treeview(
            self.excel_win, columns=("Archivo", "Duración", "RMS"),
            show="headings", selectmode="extended"
        )
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
        tk.Button(btn_frame, text="Aceptar", command=self.excel_win.destroy).pack(side="left", padx=15)

        self.populate_treeview()


    def populate_treeview(self):
        if not hasattr(self, "tree"):
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        for path in self.target_paths:
            try:
                audio = AudioSegment.from_mp3(path)
                duration = round(len(audio) / 1000, 1)
                rms = round(get_rms(audio), 2)
                self.tree.insert("", "end", values=(path, f"{duration}s", rms))
            except Exception as e:
                self.log(f"Error cargando {path}: {e}")

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
            if f not in self.target_paths:
                self.target_paths.append(f)
        self.populate_treeview()

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

    def remove_from_treeview(self, filepath):
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            if values and values[0] == filepath:
                self.tree.delete(item)
                break


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
        self.progress["maximum"] = total
        self.progress["value"] = 0
        ok = 0
        errores = 0

        # Copia para iterar sin problemas al modificar self.target_paths
        for idx, path in enumerate(self.target_paths.copy(), 1):
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

                    # ➕ Eliminar del TreeView y lista
                    self.remove_from_treeview(path)
                    self.target_paths.remove(path)

                else:
                    raise Exception("ffmpeg falló")

            except Exception as e:
                self.log(f"  ✗ Error en {path}: {e}")
                errores += 1

            self.progress["value"] = idx
            self.progress.update_idletasks()

        self.log("\n🎉 Normalización finalizada.")
        self.log(f"  Archivos exitosos: {ok}")
        self.log(f"  Con errores: {errores}")
        messagebox.showinfo("Finalizado", f"Normalización completada:\n✓ {ok} exitosos\n✗ {errores} errores")


if __name__ == "__main__":
    root = tk.Tk()
    app = VolumeNormalizerApp(root)
    root.mainloop()
