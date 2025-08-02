import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, Menu
import tkinter.ttk as ttk
from pydub import AudioSegment
from mutagen.id3 import ID3, ID3NoHeaderError
from PIL import Image, ImageTk
import os
import numpy as np
import tempfile
import shutil
import sys
import subprocess
import json
# ---------------------- CARGA DE IDIOMA ----------------------
def load_language(lang_code="es"):
    try:
        with open(resource_path("lang.json"), "r", encoding="utf-8") as f:
            langs = json.load(f)
            return langs.get(lang_code, langs["es"])
    except Exception as e:
        print(f"⚠ Error cargando idioma: {e}")
        return {}

# Parche universal para ocultar la terminal en Windows
if sys.platform == "win32":
    original_popen = subprocess.Popen

    class PopenNoConsole(subprocess.Popen):
        def __init__(self, *args, **kwargs):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    subprocess.Popen = PopenNoConsole



# ---------------------- UTILIDAD DE RUTA PORTABLE ----------------------

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

# ---------------------- FUNCIONES DE AUDIO ----------------------

def get_rms(audio):
    samples = np.array(audio.get_array_of_samples())
    return np.sqrt(np.mean(samples.astype(np.float64) ** 2))

def analyze_lufs(path):
    try:
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-i", path,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = result.stderr

        # Buscar el bloque JSON que contiene los resultados
        start = output.find("{")
        end = output.rfind("}")
        if start != -1 and end != -1:
            data = json.loads(output[start:end+1])
            return round(float(data.get("input_i", -99)), 2)
        return None
    except Exception as e:
        print(f"Error analyzing LUFS: {e}")
        return None
    
def analyze_lufs_rms(path):
    try:
        # Obtener LUFS usando ffmpeg
        cmd = [
            "ffmpeg", "-hide_banner", "-nostats", "-i", path,
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-"
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = result.stderr

        # Extraer JSON
        start = output.find("{")
        end = output.rfind("}")
        lufs = None
        if start != -1 and end != -1:
            data = json.loads(output[start:end+1])
            lufs = round(float(data.get("input_i", -99)), 2)

        # Obtener RMS con pydub
        audio = AudioSegment.from_mp3(path)
        rms = round(get_rms(audio), 4)

        return lufs, rms
    except Exception as e:
        print(f"Error analyzing LUFS and RMS: {e}")
        return None, None


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
        print(f"Error copying metadata: {e}")

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
        startup_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run(norm_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, creationflags=startup_flags)
        shutil.move(tmp_out, output_path)
        return True
    except Exception as e:
        print(f"Error in loudnorm: {e}")
        return False

# ---------------------- APP PRINCIPAL ----------------------

class VolumeNormalizerApp:
    def __init__(self, root):
        self.root = root
        self.lang_code = "en"  # o "es"
        self.current_lang = self.lang_code
        self.lang = load_language(self.lang_code)
        self.root.title(self.lang["title"])

        
        
        # ✅ Usar PNG como ícono
        try:
            icon_path = resource_path("../assets/VoluMatch.png")
            icon_img = ImageTk.PhotoImage(Image.open(icon_path))
            self.root.iconphoto(True, icon_img)
        except Exception as e:
            print(f"No se pudo cargar el ícono: {e}")

        self.target_paths = []
        self.output_folder = None

        # Estilos
        style = ttk.Style()
        style.configure("TButton", font=("Segoe UI", 10), padding=5)
        style.configure("TLabel", font=("Segoe UI", 10))

        # Botón de cambio de idioma
        ttk.Button(root, text="🌐 Change Language", command=self.toggle_language).pack(pady=(0, 10))

        # Botones de gestión
        action_frame = ttk.Frame(root)
        action_frame.pack(pady=5)
        ttk.Button(action_frame, text=self.lang["manage_songs"], command=self.open_excel_window).pack(side="left", padx=10)
        ttk.Button(action_frame, text=self.lang["output_folder"], command=self.select_output_folder).pack(side="left", padx=10)

        # LUFS y botón de normalizar
        top_frame = ttk.Frame(root)
        top_frame.pack(pady=10)

        ttk.Label(top_frame, text=self.lang["lufs_label"]).pack(side="left", padx=(0, 5))
        self.lufs_entry = ttk.Entry(top_frame, width=6)
        self.lufs_entry.insert(0, "-16")
        self.lufs_entry.pack(side="left", padx=(0, 5))
        ttk.Button(top_frame, text="ℹ️", width=3, command=self.show_lufs_info).pack(side="left", padx=(0, 15))
        ttk.Button(top_frame, text=self.lang["normalize"], command=self.normalize).pack(side="left")

        # Barra de progreso
        self.progress = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate")
        self.progress.pack(pady=(5, 10))

        # Consola
        console_frame = ttk.LabelFrame(root, text=self.lang["console_title"], padding=(10, 5))
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
            img = img.resize((200, 200), Image.Resampling.LANCZOS)
            logo_img = ImageTk.PhotoImage(img)
            label_logo = tk.Label(logo_frame, image=logo_img, bg="white")
            label_logo.image = logo_img
            label_logo.pack()
        except Exception as e:
            self.log(f"⚠ No se pudo cargar el logo: {e}")

    def toggle_language(self):
        self.current_lang = "es" if self.lang_code == "en" else "en"
        self.lang_code = self.current_lang
        self.lang = load_language(self.lang_code)
        self.refresh_texts()

    def refresh_texts(self):
        self.root.title(self.lang["title"])

        # Destruir ventana secundaria antes de modificar widgets ligados a ella
        if hasattr(self, "excel_win") and self.excel_win.winfo_exists():
            self.excel_win.destroy()
            # Al destruirla, también se destruye self.tree
            del self.tree

        # Actualizar texto de botones
        for widget in self.root.winfo_children():
            self.update_widget_texts(widget)

        # Ya no intentes acceder a self.tree directamente aquí
        # (la nueva ventana lo hará al abrirse nuevamente)


    def update_widget_texts(self, parent):
        for widget in parent.winfo_children():
            if isinstance(widget, ttk.Button):
                text_map = {
                    "🎼": self.lang["manage_songs"],
                    "📁": self.lang["output_folder"],
                    "🎚️": self.lang["normalize"],
                    "🌐": "🌐 Cambiar idioma",
                    "Aceptar": self.lang["excel_page"]["accept"]
                }
                for prefix, new_text in text_map.items():
                    if widget["text"].startswith(prefix):
                        widget.config(text=new_text)
            elif isinstance(widget, ttk.LabelFrame):
                if widget["text"].startswith("🖥"):
                    widget.config(text=self.lang["console_title"])
            elif isinstance(widget, ttk.Label):
                if self.lang["lufs_label"].split(":")[0] in widget["text"]:
                    widget.config(text=self.lang["lufs_label"])
            self.update_widget_texts(widget)




    def open_excel_window(self):
        self.excel_win = tk.Toplevel(self.root)
        self.excel_win.title(self.lang["excel_page"]["title"])
        self.excel_win.grab_set()

        self.tree = ttk.Treeview(
            self.excel_win, columns=(self.lang["excel_page"]["archive"], self.lang["excel_page"]["duration"], "RMS", "LUFS"),
            show="headings", selectmode="extended"
        )
        for col in (self.lang["excel_page"]["archive"], self.lang["excel_page"]["duration"], "RMS", "LUFS"):


            self.tree.heading(col, text=col)
            self.tree.column(col, width=250 if col == self.lang["excel_page"]["archive"] else 100)
        self.tree.pack(expand=True, fill="both")
        self.tree.bind("<Button-3>", self.show_context_menu)

        btn_frame = tk.Frame(self.excel_win)
        btn_frame.pack(pady=5)

        tk.Button(btn_frame, text=self.lang["excel_page"]["aggregate"], command=self.select_targets).pack(side="left", padx=5)
        tk.Button(btn_frame, text=self.lang["excel_page"]["delete selected"], command=self.delete_selected).pack(side="left", padx=5)
        tk.Button(btn_frame, text=self.lang["excel_page"]["delete all"], command=self.clear_all).pack(side="left", padx=5)
        tk.Button(btn_frame, text=self.lang["excel_page"]["accept"], command=self.excel_win.destroy).pack(side="left", padx=15)

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
                lufs = analyze_lufs(path)
                self.tree.insert("", "end", values=(path, f"{duration}s", rms, f"{lufs} LUFS" if lufs else "N/A"))
                self.log(f"🎵 {os.path.basename(path)}")
                self.log(f"   ⏱ {self.lang['excel_page']['duration']}: {duration}s")
                self.log(f"   🔊 RMS: {rms}")
                self.log(f"   📉 LUFS real: {lufs if lufs is not None else 'Error'}")

            except Exception as e:
                self.log(f"{self.lang['error charging']} {path}: {e}")


    def show_context_menu(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        menu = Menu(self.excel_win, tearoff=0)
        menu.add_command(label="Eliminar", command=self.delete_selected)
        menu.post(event.x_root, event.y_root)

    def select_targets(self):
        files = filedialog.askopenfilenames(filetypes=[(self.lang["mp3"], "*.mp3")])
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
        if not hasattr(self, "tree"):
            return
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            if values and values[0] == filepath:
                self.tree.delete(item)
                break

    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.log(f"{self.lang['output_folder']}: {folder}")
            messagebox.showinfo(self.lang["output_folder"], f"{self.lang['selected_folder']}:\n{folder}")

    def show_lufs_info(self):
        popup = tk.Toplevel(self.root)
        popup.title(self.lang["lufs_info"]["title"])
        popup.geometry("520x360")
        popup.resizable(False, False)

        texto = self.lang["lufs_info"]["text"]

        text_widget = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=("Segoe UI", 11))
        text_widget.insert(tk.END, texto.strip())
        text_widget.config(state="disabled")
        text_widget.pack(expand=True, fill="both", padx=10, pady=10)
        tk.Button(popup, text="OK", command=popup.destroy).pack(pady=10)


    def normalize(self):
        if not self.target_paths or not self.output_folder:
            messagebox.showerror(self.lang["messagebox_error"], self.lang["messagebox_error_text"])
            return

        total = len(self.target_paths)
        self.progress["maximum"] = total
        self.progress["value"] = 0
        ok = 0
        errores = 0

        for idx, path in enumerate(self.target_paths.copy(), 1):
            try:
                filename = os.path.basename(path)
                self.log(f"\n[{idx}/{total}] {filename}")
                output_path = os.path.join(self.output_folder, filename)

                try:
                    target_lufs = float(self.lufs_entry.get())
                except ValueError:
                    self.log(self.lang["invalid_lufs"])
                    target_lufs = -16.0

                # ➤ LUFS y RMS antes
                original_lufs = analyze_lufs(path)
                audio = AudioSegment.from_mp3(path)
                original_rms = round(get_rms(audio), 2)

                self.log("  Normalizando con loudnorm (LUFS)...")
                self.log(f"  {self.lang['lufs_before']}: {original_lufs} | {self.lang['rms_before']}: {original_rms}")
                success = normalize_with_ffmpeg_loudnorm(path, output_path, target_lufs)
                if success:
                    # ➤ LUFS y RMS después
                    new_lufs = analyze_lufs(output_path)
                    audio_new = AudioSegment.from_mp3(output_path)
                    new_rms = round(get_rms(audio_new), 2)

                    self.log(f"  {self.lang['lufs_after']}: {new_lufs} | {self.lang['rms_after']}: {new_rms}")

                    apply_metadata(path, output_path)
                    self.log(f"  ✓ Guardado: {output_path}")
                    ok += 1

                    # ➕ Eliminar del TreeView y lista
                    if hasattr(self, "tree") and self.tree.winfo_exists():
                        self.remove_from_treeview(path)
                    self.target_paths.remove(path)
                else:
                    raise Exception("ffmpeg failed")

            except Exception as e:
                self.log(f"  ✗ Error en {path}: {e}")
                errores += 1

            self.progress["value"] = idx
            self.progress.update_idletasks()

        self.log(f"\n\n{self.lang['normalization_complete']}")
        self.log(f"  {self.lang['success_files']}: {ok}")
        self.log(f"  {self.lang['error_files']}: {errores}")
        messagebox.showinfo(self.lang['finalized'], f"{self.lang['normalization_complete']}:\n✓ {ok} exitosos\n✗ {errores} errores")




if __name__ == "__main__":
    root = tk.Tk()
    app = VolumeNormalizerApp(root)
    root.mainloop()

