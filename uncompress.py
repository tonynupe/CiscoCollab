import sublime
import sublime_plugin
import os
import shutil
import zipfile
import tarfile
import tempfile
import subprocess

class ExtractAnyArchiveCommand(sublime_plugin.WindowCommand):
    def run(self, paths=[]):
        for path in paths:
            if not os.path.isfile(path):
                continue

            ext = os.path.splitext(path)[1].lower()
            extract_path = os.path.splitext(path)[0]

            try:
                os.makedirs(extract_path, exist_ok=True)
                self.extract_archive(path, extract_path)

                # Limpiar __MACOSX
                self.remove_macosx_folder(extract_path)

                # Borra el archivo original principal
                os.remove(path)
                
                sublime.message_dialog(f"Archivo extraído en:\n{extract_path}")

            except Exception as e:
                sublime.error_message(f"Error al extraer {os.path.basename(path)}:\n{e}")

    # ← Aquí la indentación correcta: 1 nivel dentro de la clase
    def remove_macosx_folder(self, extract_path):
        macosx_path = os.path.join(extract_path, "__MACOSX")
        if os.path.exists(macosx_path):
            try:
                shutil.rmtree(macosx_path)
            except Exception:
                pass

    def extract_archive(self, filepath, dest):
        ext = os.path.splitext(filepath)[1].lower()

        # ZIP
        if ext == ".zip":
            with zipfile.ZipFile(filepath, 'r') as zf:
                zf.extractall(dest)

        # TAR / TAR.GZ
        elif ext in [".tar", ".gz", ".tgz", ".tar.gz"]:
            with tarfile.open(filepath, 'r:*') as tf:
                tf.extractall(dest)

        # RAR
        elif ext == ".rar":
            subprocess.run(["unrar", "x", "-o+", filepath, dest], check=True)

        # 7Z
        elif ext in [".7z"]:
            subprocess.run(["7z", "x", "-y", f"-o{dest}", filepath], check=True)

        else:
            raise Exception("Formato no soportado")

        # Descompresión recursiva
        for root, dirs, files in os.walk(dest):
            for f in files:
                inner_path = os.path.join(root, f)
                inner_ext = os.path.splitext(inner_path)[1].lower()
                if inner_ext in [".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".tar.gz"]:
                    inner_dest = os.path.splitext(inner_path)[0]
                    self.extract_archive(inner_path, inner_dest)
                    try:
                        os.remove(inner_path)
                    except Exception:
                        pass

    def is_visible(self, paths=[]):
        if len(paths) != 1:
            return False
        ext = os.path.splitext(paths[0])[1].lower()
        return ext in [".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".tar.gz"]

    def is_enabled(self, paths=[]):
        return self.is_visible(paths)
