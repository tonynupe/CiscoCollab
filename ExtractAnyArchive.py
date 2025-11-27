import sublime
import sublime_plugin
import os
import shutil
import zipfile
import tarfile

class ExtractAnyArchiveCommand(sublime_plugin.WindowCommand):
    SUPPORTED_SUFFIXES = (".zip", ".tar", ".gz", ".tgz", ".tar.gz")

    def run(self, paths=None):
        if paths is None:
            paths = []

        # If nothing passed, show a message
        if not paths:
            sublime.status_message("No files selected to extract")
            return

        for path in paths:
            if not os.path.isfile(path):
                continue

            try:
                extract_path = self._compute_extract_path(path)
                os.makedirs(extract_path, exist_ok=True)
                self.extract_archive(path, extract_path)

                self.remove_macosx_folder(extract_path)

                # remove original archive (keep if you prefer)
                try:
                    os.remove(path)
                except Exception:
                    pass

                sublime.message_dialog(f"Archivo extraído en:\n{extract_path}")
            except Exception as e:
                sublime.error_message(f"Error al extraer {os.path.basename(path)}:\n{e}")

    def _compute_extract_path(self, filepath):
        # For files like file.tar.gz we want "file" not "file.tar"
        base = os.path.basename(filepath)
        for suffix in (".tar.gz", ".tgz"):
            if base.lower().endswith(suffix):
                return os.path.join(os.path.dirname(filepath), base[:-len(suffix)])
        # fallback: remove single extension
        return os.path.splitext(filepath)[0]

    def extract_archive(self, filepath, dest):
        filepath_lower = filepath.lower()

        if filepath_lower.endswith(".zip"):
            with zipfile.ZipFile(filepath, 'r') as zf:
                zf.extractall(dest)

        elif filepath_lower.endswith((".tar", ".gz", ".tgz", ".tar.gz")):
            # tarfile can handle gz, tgz, tar.gz and plain tar
            with tarfile.open(filepath, 'r:*') as tf:
                tf.extractall(dest)

        else:
            raise Exception("Formato no soportado")

        # Recursively extract nested archives found inside the extracted tree
        for root, dirs, files in os.walk(dest):
            for f in files:
                inner_path = os.path.join(root, f)
                if self._is_supported_archive(inner_path):
                    inner_dest = self._compute_extract_path(inner_path)
                    os.makedirs(inner_dest, exist_ok=True)
                    try:
                        self.extract_archive(inner_path, inner_dest)
                        os.remove(inner_path)
                    except Exception:
                        # ignore nested extraction errors and continue
                        pass

    def remove_macosx_folder(self, extract_path):
        macosx_path = os.path.join(extract_path, "__MACOSX")
        if os.path.exists(macosx_path):
            try:
                shutil.rmtree(macosx_path)
            except Exception:
                pass

    def _is_supported_archive(self, path):
        if not os.path.isfile(path):
            return False
        lower = path.lower()
        # check multi-extension first
        if lower.endswith(".tar.gz") or lower.endswith(".tgz"):
            return True
        # then single-extension checks
        return any(lower.endswith(s) for s in (".zip", ".tar", ".gz"))

    # Show the menu item only when at least one selected item is a supported archive
    def is_visible(self, paths=None):
        if not paths:
            return False
        for p in paths:
            if self._is_supported_archive(p):
                return True
        return False

    def is_enabled(self, paths=None):
        return self.is_visible(paths)
