Browse multiplatform:


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
import shlex


# ---------------------------------------------------------
# Minimal Output Panel Logger (safe, non-blocking)
# ---------------------------------------------------------
class ExtractLogger(object):
    def __init__(self, window):
        self.window = window
        self.panel = window.create_output_panel("extract_nested")
        self.panel.set_read_only(False)

    def show(self):
        self.window.run_command("show_panel", {"panel": "output.extract_nested"})

    def log(self, msg):
        def append():
            self.panel.run_command("append", {"characters": msg + "\n"})
        sublime.set_timeout(append, 0)


# ---------------------------------------------------------
# Main Extraction Command
# ---------------------------------------------------------
class ExtractNestedCommand(sublime_plugin.WindowCommand):

    SUPPORTED_EXTENSIONS = ('.zip', '.tar', '.tar.gz', '.tgz', '.gz', '.7z', '.rar')

    def run(self, paths=None):
        self.logger = ExtractLogger(self.window)
        self.logger.show()

        if not paths:
            self.window.run_command("extract_nested_input")
            return

        for path in paths:
            if self.is_compressed_file(path):
                t = threading.Thread(target=self.extract_file, args=(path,))
                t.daemon = True
                t.start()

    def is_compressed_file(self, path):
        return path.lower().endswith(self.SUPPORTED_EXTENSIONS)

    def extract_file(self, file_path):
        try:
            base = os.path.basename(file_path)
            output_dir = self.get_output_directory(file_path)

            # Minimal user-facing messages
            self.logger.log("Starting extraction: " + base)
            sublime.status_message("Extracting: " + base)

            # Extract main file
            self.logger.log("Extracting: " + base)
            self.extract_to_directory(file_path, output_dir)

            # Extract nested files
            self.extract_nested_files(output_dir)

            # Cleanup
            self.delete_compressed_file(file_path)
            self.clean_macosx_folder(output_dir)

            # Final message
            self.logger.log("Completed: " + output_dir)
            sublime.status_message("Extraction completed: " + output_dir)

            self.show_in_finder(output_dir)

        except Exception as e:
            self.logger.log("Error: " + str(e))
            sublime.error_message("Error: " + str(e))

    def get_output_directory(self, file_path):
        base_name = os.path.basename(file_path)
        clean_name = (
            base_name
            .replace('.tar.gz', '')
            .replace('.tgz', '')
            .replace('.tar', '')
            .replace('.zip', '')
            .replace('.7z', '')
            .replace('.rar', '')
            .replace('.gz', '')
        )

        parent_dir = os.path.dirname(file_path)
        output_dir = os.path.join(parent_dir, clean_name)
        if os.path.exists(output_dir):
            output_dir = os.path.join(parent_dir, clean_name + "_extracted")
            os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def extract_to_directory(self, file_path, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        lower_path = file_path.lower()

        if lower_path.endswith('.zip'):
            self.extract_zip(file_path, output_dir)
        elif lower_path.endswith(('.tar.gz', '.tgz')):
            self.extract_tar_gz(file_path, output_dir)
        elif lower_path.endswith('.tar'):
            self.extract_tar(file_path, output_dir)
        elif lower_path.endswith('.7z'):
            self.extract_7z(file_path, output_dir)
        elif lower_path.endswith('.rar'):
            self.extract_rar(file_path, output_dir)
        elif lower_path.endswith('.gz'):
            self.extract_gz(file_path, output_dir)

    def extract_zip(self, zip_path, output_dir):
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(output_dir)

    def extract_tar(self, tar_path, output_dir):
        with tarfile.open(tar_path, 'r') as t:
            t.extractall(output_dir)

    def extract_tar_gz(self, tar_gz_path, output_dir):
        with tarfile.open(tar_gz_path, 'r:gz') as t:
            t.extractall(output_dir)

    def extract_gz(self, gz_path, output_dir):
        output_file = os.path.join(output_dir, os.path.basename(gz_path).replace('.gz', ''))
        try:
            with gzip.open(gz_path, 'rb') as f_in:
                with open(output_file, 'wb') as f_out:
                    # Slightly larger buffer (safe)
                    shutil.copyfileobj(f_in, f_out, length=1024 * 1024)
        except Exception:
            traceback.print_exc()
            raise

    def extract_7z(self, seven_zip_path, output_dir):
        self.extract_with_system_tools(seven_zip_path, output_dir, archive_type='7z')

    def extract_rar(self, rar_path, output_dir):
        self.extract_with_system_tools(rar_path, output_dir, archive_type='rar')

    def get_extractor_commands(self, archive_path, output_dir, archive_type):
        common = [
            ['bsdtar', '-xf', archive_path, '-C', output_dir],
            ['tar', '-xf', archive_path, '-C', output_dir],
            ['7z', 'x', '-y', '-o' + output_dir, archive_path],
            ['7za', 'x', '-y', '-o' + output_dir, archive_path],
            ['7zr', 'x', '-y', '-o' + output_dir, archive_path],
            ['unar', '-q', '-o', output_dir, archive_path],
        ]

        if archive_type == 'rar':
            return common + [['unrar', 'x', '-o+', archive_path, output_dir]]

        return common

    def run_extractor_command(self, command):
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        _, stderr = process.communicate()

        if process.returncode != 0:
            error_text = stderr.decode('utf-8', errors='replace').strip()
            if not error_text:
                error_text = 'Unknown extraction error'
            raise RuntimeError(error_text)

    def extract_with_system_tools(self, archive_path, output_dir, archive_type):
        commands = self.get_extractor_commands(archive_path, output_dir, archive_type)
        available_commands = [c for c in commands if shutil.which(c[0])]

        if not available_commands:
            raise RuntimeError(
                "No system extractor found for .{0}. Tried: {1}".format(
                    archive_type,
                    ', '.join(sorted(set([c[0] for c in commands])))
                )
            )

        last_error = None
        for command in available_commands:
            try:
                self.run_extractor_command(command)
                return
            except Exception as e:
                last_error = "{0}: {1}".format(command[0], str(e))

        raise RuntimeError("Failed to extract .{0} with available system tools. Last error: {1}".format(archive_type, last_error))

    def extract_nested_files(self, directory, depth=0, max_depth=50):
        if depth >= max_depth:
            return

        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)

                # If it's a compressed file
                if os.path.isfile(item_path) and self.is_compressed_file(item_path):

                    # Show filename being processed
                    self.logger.log("Extracting: " + item)

                    # Decide output folder
                    lower_item_path = item_path.lower()
                    if lower_item_path.endswith('.gz') and not lower_item_path.endswith('.tar.gz') and not lower_item_path.endswith('.tgz'):
                        nested_output = directory
                    else:
                        nested_output = os.path.join(directory, os.path.splitext(item)[0] + "_nested")
                        if not os.path.exists(nested_output):
                            os.makedirs(nested_output)

                    try:
                        self.extract_to_directory(item_path, nested_output)
                        self.delete_compressed_file(item_path)
                        self.extract_nested_files(nested_output, depth + 1, max_depth)
                    except Exception:
                        traceback.print_exc()

                # If it's a folder, recurse
                elif os.path.isdir(item_path):
                    self.extract_nested_files(item_path, depth + 1, max_depth)

        except Exception:
            pass

    def show_in_finder(self, directory):
        os.system('open "' + directory + '"')

    def delete_compressed_file(self, file_path):
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    def clean_macosx_folder(self, directory):
        macosx_path = os.path.join(directory, '__MACOSX')
        if os.path.exists(macosx_path):
            try:
                shutil.rmtree(macosx_path)
            except Exception:
                pass

    def is_enabled(self, paths=None):
        return True


# ---------------------------------------------------------
# File Picker (unchanged)
# ---------------------------------------------------------
class ExtractNestedBrowseCommand(sublime_plugin.WindowCommand):
    def run(self):
        def worker():
            try:
                paths = self.pick_paths()
                if not paths:
                    sublime.status_message("No files selected. Falling back to manual path input.")
                    self.window.run_command("extract_nested_input")
                    return

                valid_paths = self.collect_valid_paths(paths)

                if valid_paths:
                    self.window.run_command("extract_nested", {"paths": valid_paths})
                else:
                    sublime.error_message("No supported compressed files were found in the selected location(s).")
            except Exception as e:
                sublime.error_message("Unable to open the file browser: " + str(e))
                self.window.run_command("extract_nested_input")

        threading.Thread(target=worker, daemon=True).start()

    def pick_paths(self):
        platform_name = sublime.platform()

        if platform_name == 'osx':
            return self.pick_paths_macos()
        if platform_name == 'windows':
            return self.pick_paths_windows()
        if platform_name == 'linux':
            return self.pick_paths_linux()

        sublime.status_message("Browse is not supported on this platform. Falling back to manual path input.")
        return []

    def run_capture(self, command):
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        output, _ = process.communicate()
        if process.returncode != 0:
            return []

        return [line.strip() for line in output.decode('utf-8', errors='replace').splitlines() if line.strip()]

    def pick_paths_macos(self):
        file_script = '''
        tell application "System Events"
            activate
            try
                set theFiles to choose file with prompt "Select compressed file(s):" with multiple selections allowed
                set oldDelims to AppleScript's text item delimiters
                set AppleScript's text item delimiters to linefeed
                set outText to ((POSIX path of theFiles) as text)
                set AppleScript's text item delimiters to oldDelims
                return outText
            on error
                return ""
            end try
        end tell
        '''

        folder_script = '''
        tell application "System Events"
            activate
            try
                set theFolder to choose folder with prompt "Select a folder with compressed files:"
                return POSIX path of theFolder
            on error
                return ""
            end try
        end tell
        '''

        file_paths = self.run_capture(['osascript', '-e', file_script])
        if file_paths:
            return file_paths
        return self.run_capture(['osascript', '-e', folder_script])

    def pick_paths_windows(self):
        script = r'''
        Add-Type -AssemblyName System.Windows.Forms
        $ofd = New-Object System.Windows.Forms.OpenFileDialog
        $ofd.Multiselect = $true
        $ofd.Filter = "All files (*.*)|*.*"

        if ($ofd.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            $ofd.FileNames | ForEach-Object { Write-Output $_ }
            exit 0
        }

        $fbd = New-Object System.Windows.Forms.FolderBrowserDialog
        if ($fbd.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            Write-Output $fbd.SelectedPath
            exit 0
        }
        '''

        powershell_cmd = shutil.which('powershell') or shutil.which('pwsh')
        if not powershell_cmd:
            return []

        return self.run_capture([powershell_cmd, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script])

    def pick_paths_linux(self):
        if shutil.which('zenity'):
            file_paths = self.run_capture(['zenity', '--file-selection', '--multiple', '--separator=\n'])
            if file_paths:
                return file_paths
            return self.run_capture(['zenity', '--file-selection', '--directory'])

        if shutil.which('kdialog'):
            process = subprocess.Popen(
                ['kdialog', '--getopenfilename', '.', '*', '--multiple'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            output, _ = process.communicate()
            if process.returncode == 0:
                text = output.decode('utf-8', errors='replace').strip()
                if text:
                    return [p for p in shlex.split(text) if p]

            return self.run_capture(['kdialog', '--getexistingdirectory'])

        return []

    def collect_valid_paths(self, paths):
        valid_paths = []
        for path in paths:
            candidate = path.strip().strip('"')
            if not candidate:
                continue

            if os.path.isdir(candidate):
                for file_name in os.listdir(candidate):
                    file_path = os.path.join(candidate, file_name)
                    if file_path.lower().endswith(ExtractNestedCommand.SUPPORTED_EXTENSIONS):
                        valid_paths.append(file_path)
            elif os.path.isfile(candidate) and candidate.lower().endswith(ExtractNestedCommand.SUPPORTED_EXTENSIONS):
                valid_paths.append(candidate)

        return valid_paths


# ---------------------------------------------------------
# Manual Input Command (unchanged)
# ---------------------------------------------------------
class ExtractNestedInputCommand(sublime_plugin.WindowCommand):
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
                    if f.lower().endswith(ExtractNestedCommand.SUPPORTED_EXTENSIONS)
                ]
                if compressed_files:
                    self.window.run_command("extract_nested", {"paths": compressed_files})
                else:
                    sublime.error_message("No supported compressed files found in folder")
            elif path.lower().endswith(ExtractNestedCommand.SUPPORTED_EXTENSIONS):
                self.window.run_command("extract_nested", {"paths": [path]})
            else:
                sublime.error_message("Unsupported format")
        else:
            sublime.error_message("File or folder not found")

    def is_enabled(self):
        return True


        
