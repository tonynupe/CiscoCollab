import sublime
import sublime_plugin
import os
import zipfile
import tarfile
import gzip
import shutil
import threading
import traceback
import subprocess


class ExtractNestedCommand(sublime_plugin.WindowCommand):
    """
    Plugin para Sublime Text 4 que extrae archivos comprimidos (.zip, .tar, .gz)
    y busca archivos comprimidos anidados para extraerlos recursivamente.
    """

    def run(self, paths=None):
        if not paths:
            self.window.run_command("extract_nested_input")
        else:
            for path in paths:
                if self.is_compressed_file(path):
                    thread = threading.Thread(target=self.extract_file, args=(path,))
                    thread.daemon = True
                    thread.start()

    def is_compressed_file(self, path):
        return path.endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.gz'))

    def extract_file(self, file_path):
        try:
            output_dir = self.get_output_directory(file_path)
            sublime.status_message("Extrayendo: " + os.path.basename(file_path))

            self.extract_to_directory(file_path, output_dir)
            self.extract_nested_files(output_dir)

            self.delete_compressed_file(file_path)
            self.clean_macosx_folder(output_dir)

            sublime.status_message("Extraccion completada en: " + output_dir)
            self.show_in_finder(output_dir)

        except Exception as e:
            sublime.error_message("Error: " + str(e))

    def get_output_directory(self, file_path):
        base_name = os.path.basename(file_path)
        clean_name = base_name.replace('.tar.gz', '').replace('.tgz', '').replace('.tar', '').replace('.zip', '').replace('.gz', '')

        parent_dir = os.path.dirname(file_path)
        output_dir = os.path.join(parent_dir, clean_name + "_extracted")

        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def extract_to_directory(self, file_path, output_dir):
        if file_path.endswith('.zip'):
            self.extract_zip(file_path, output_dir)
        elif file_path.endswith(('.tar.gz', '.tgz')):
            self.extract_tar_gz(file_path, output_dir)
        elif file_path.endswith('.tar'):
            self.extract_tar(file_path, output_dir)
        elif file_path.endswith('.gz'):
            self.extract_gz(file_path, output_dir)

    def extract_zip(self, zip_path, output_dir):
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(output_dir)

    def extract_tar(self, tar_path, output_dir):
        with tarfile.open(tar_path, 'r') as tar_ref:
            tar_ref.extractall(output_dir)

    def extract_tar_gz(self, tar_gz_path, output_dir):
        with tarfile.open(tar_gz_path, 'r:gz') as tar_ref:
            tar_ref.extractall(output_dir)

    def extract_gz(self, gz_path, output_dir):
        output_file = os.path.join(output_dir, os.path.basename(gz_path).replace('.gz', ''))
        try:
            with gzip.open(gz_path, 'rb') as f_in:
                with open(output_file, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            print('[ExtractNested] Descomprimido .gz ->', output_file)
        except Exception:
            print('[ExtractNested] Error al descomprimir .gz:', gz_path)
            traceback.print_exc()
            raise

    def extract_nested_files(self, directory, depth=0, max_depth=50):
        if depth >= max_depth:
            return

        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)

                if os.path.isfile(item_path) and self.is_compressed_file(item_path):
                    if item_path.endswith('.gz') and not item_path.endswith('.tar.gz') and not item_path.endswith('.tgz'):
                        nested_output = directory
                    else:
                        nested_output = os.path.join(directory, os.path.splitext(item)[0] + "_nested")
                        os.makedirs(nested_output, exist_ok=True)

                    try:
                        print('[ExtractNested] Extrayendo anidado:', item_path, '->', nested_output)
                        self.extract_to_directory(item_path, nested_output)
                        self.delete_compressed_file(item_path)
                        self.extract_nested_files(nested_output, depth + 1, max_depth)
                    except Exception:
                        print('[ExtractNested] Error al extraer archivo anidado:', item_path)
                        traceback.print_exc()

                elif os.path.isdir(item_path):
                    self.extract_nested_files(item_path, depth + 1, max_depth)

        except Exception:
            pass

    def show_in_finder(self, directory):
        os.system('open "' + directory + '"')

    def delete_compressed_file(self, file_path):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

    def clean_macosx_folder(self, directory):
        try:
            macosx_path = os.path.join(directory, '__MACOSX')
            if os.path.exists(macosx_path) and os.path.isdir(macosx_path):
                shutil.rmtree(macosx_path)
                print('[ExtractNested] Carpeta __MACOSX eliminada')
        except Exception as e:
            print('[ExtractNested] No se pudo eliminar __MACOSX:', str(e))

    def is_enabled(self, paths=None):
        return True


class ExtractNestedBrowseCommand(sublime_plugin.WindowCommand):
    """Comando para abrir diálogo de selección de archivo o carpeta"""

    def run(self):
        script = '''
        tell application "System Events"
            activate
            try
                set theFile to choose file with prompt "Select compressed file(s):" with multiple selections allowed
                set posixPaths to {}
                repeat with f in theFile
                    set end of posixPaths to POSIX path of f
                end repeat
                return posixPaths as string
            on error
                try
                    set theFolder to choose folder with prompt "Or select a folder:"
                    return POSIX path of theFolder
                on error
                    return ""
                end try
            end try
        end tell
        '''

        def worker():
            try:
                process = subprocess.Popen(['osascript', '-e', script],
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
                output, error = process.communicate(timeout=15)
                result = output.decode('utf-8').strip()

                if not result:
                    return

                # Multiple files are comma-separated
                if ", " in result:
                    paths = [p.strip() for p in result.split(", ")]
                else:
                    paths = [result]

                valid_paths = []
                for p in paths:
                    if os.path.isdir(p):
                        for f in os.listdir(p):
                            fp = os.path.join(p, f)
                            if fp.endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.gz')):
                                valid_paths.append(fp)
                    elif os.path.isfile(p) and p.endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.gz')):
                        valid_paths.append(p)

                if valid_paths:
                    self.window.run_command("extract_nested", {"paths": valid_paths})
                else:
                    sublime.error_message("No supported compressed files found")
            except subprocess.TimeoutExpired:
                sublime.error_message("El diálogo tardó demasiado en responder")
            except Exception as e:
                sublime.error_message("Error al abrir diálogo: " + str(e))

        threading.Thread(target=worker, daemon=True).start()


class ExtractNestedInputCommand(sublime_plugin.WindowCommand):
    """Comando para solicitar la ruta del archivo o carpeta a extraer"""

    def run(self):
        self.window.show_input_panel(
            "Path of compressed file or folder:",
            "",
            self.on_done,
            None,
            None
        )

    def on_done(self, path):
        if os.path.exists(path):
            if os.path.isdir(path):
                compressed_files = [
                    os.path.join(path, f)
                    for f in os.listdir(path)
                    if f.endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.gz'))
                ]
                if compressed_files:
                    self.window.run_command("extract_nested", {"paths": compressed_files})
                else:
                    sublime.error_message("No supported compressed files found in folder")
            elif path.endswith(('.zip', '.tar', '.tar.gz', '.tgz', '.gz')):
                self.window.run_command("extract_nested", {"paths": [path]})
            else:
                sublime.error_message("Formato no soportado")
        else:
            sublime.error_message("Archivo o carpeta no encontrada")

    def is_enabled(self):
        return True
