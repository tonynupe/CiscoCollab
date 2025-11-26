import sublime
import sublime_plugin
import os
import shutil
import zipfile
import tarfile

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

                self.remove_macosx_folder(extract_path)
                os.remove(path)

                sublime.message_dialog(f"Archivo extraído en:\n{extract_path}")
            except Exception as e:
                sublime.error_message(f"Error al extraer {os.path.basename(path)}:\n{e}")

    def extract_archive(self, filepath, dest):
        ext = os.path.splitext(filepath)[1].lower()

        if ext == ".zip":
            with zipfile.ZipFile(filepath, 'r') as zf:
                zf.extractall(dest)

        elif ext in [".tar", ".gz", ".tgz", ".tar.gz"]:
            with tarfile.open(filepath, 'r:*') as tf:
                tf.extractall(dest)

        else:
            raise Exception("Formato no soportado")

        # Extracción recursiva
        for root, dirs, files in os.walk(dest):
            for f in files:
                inner_path = os.path.join(root, f)
                inner_ext = os.path.splitext(inner_path)[1].lower()
                if inner_ext in [".zip", ".tar", ".gz", ".tgz", ".tar.gz"]:
                    inner_dest = os.path.splitext(inner_path)[0]
                    self.extract_archive(inner_path, inner_dest)
                    try:
                        os.remove(inner_path)
                    except Exception:
                        pass

    def remove_macosx_folder(self, extract_path):
        macosx_path = os.path.join(extract_path, "__MACOSX")
        if os.path.exists(macosx_path):
            try:
                shutil.rmtree(macosx_path)
            except Exception:
                pass

    def is_visible(self, paths=[]):
        if not paths or len(paths) != 1:
            return False
        ext = os.path.splitext(paths[0])[1].lower()
        return ext in [".zip", ".tar", ".gz", ".tgz", ".tar.gz"]

    def is_enabled(self, paths=[]):
        return self.is_visible(paths)
