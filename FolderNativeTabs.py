import sublime
import sublime_plugin
import os


PLUGIN_NAME = "FolderNativeTabs"

# Files currently being moved/opened by the plugin.
_processing = set()


def normalize(path):
    if not path:
        return None

    return os.path.realpath(os.path.normpath(path))


def get_project_folder(view):
    """
    Determine which project folder contains this file.
    The most specific matching folder wins.
    """

    filename = normalize(view.file_name())

    if not filename:
        return None

    window = view.window()

    if not window:
        return None

    matches = []

    for folder in window.folders():

        folder = normalize(folder)

        if not folder:
            continue

        try:
            common = os.path.commonpath([filename, folder])
        except ValueError:
            continue

        if common == folder:
            matches.append(folder)

    if not matches:
        return None

    return max(matches, key=len)


def get_folder_window(folder):

    folder = normalize(folder)

    for window in sublime.windows():

        assigned = window.settings().get(
            "folder_native_tab_root"
        )

        if normalize(assigned) == folder:
            return window

    return None


class FolderNativeTabsListener(sublime_plugin.EventListener):

    def on_load(self, view):
        """
        Handles files opened from Search in Folder,
        Finder, plugins, etc.
        """

        self.schedule_process(view)

    def on_activated(self, view):
        """
        Handles files opened/activated from the sidebar
        and other Sublime UI elements.
        """

        self.schedule_process(view)

    def schedule_process(self, view):

        filename = view.file_name()

        if not filename:
            return

        filename = normalize(filename)

        # Avoid scheduling the same file multiple times.
        if filename in _processing:
            return

        _processing.add(filename)

        # Give Sublime time to finish opening/activating
        # the file before we move it.
        sublime.set_timeout(
            lambda: self.process_view(view, filename),
            150
        )

    def process_view(self, view, filename):

        try:

            # View may have disappeared while waiting.
            if not view:
                return

            current_window = view.window()

            if not current_window:
                return

            # If this file was opened by our plugin,
            # don't process it again.
            if view.settings().get(
                "folder_native_tabs_plugin_opened"
            ):
                return

            # Don't process the plugin itself.
            if filename.endswith("FolderNativeTabs.py"):
                return

            folder = get_project_folder(view)

            if not folder:
                return

            # If this window already belongs to this folder,
            # everything is already correct.
            assigned_folder = current_window.settings().get(
                "folder_native_tab_root"
            )

            if normalize(assigned_folder) == normalize(folder):
                return

            # Does a dedicated Native Tab already exist?
            target_window = get_folder_window(folder)

            if target_window:

                if target_window.id() == current_window.id():
                    return

                print(
                    "{}: moving file to existing tab: {}".format(
                        PLUGIN_NAME,
                        folder
                    )
                )

                new_view = target_window.open_file(filename)

                if new_view:
                    new_view.settings().set(
                        "folder_native_tabs_plugin_opened",
                        True
                    )

                target_window.focus()

                # Close the original view after the new view
                # has been created.
                sublime.set_timeout(
                    lambda: self.close_original_view(view),
                    200
                )

                return

            # No dedicated tab exists yet.
            print(
                "{}: creating tab for: {}".format(
                    PLUGIN_NAME,
                    folder
                )
            )

            old_window_ids = {
                w.id()
                for w in sublime.windows()
            }

            sublime.run_command("new_window")

            sublime.set_timeout(
                lambda: self.setup_new_window(
                    filename,
                    folder,
                    old_window_ids,
                    view
                ),
                300
            )

        finally:

            _processing.discard(filename)

    def setup_new_window(
        self,
        filename,
        folder,
        old_window_ids,
        original_view
    ):

        new_window = None

        for window in sublime.windows():

            if window.id() not in old_window_ids:
                new_window = window
                break

        if not new_window:
            print(
                "{}: could not find new window".format(
                    PLUGIN_NAME
                )
            )
            return

        # Remember which folder this Native Tab represents.
        new_window.settings().set(
            "folder_native_tab_root",
            folder
        )

        # This window represents only this project folder.
        new_window.set_project_data({
            "folders": [
                {
                    "path": folder
                }
            ]
        })

        new_view = new_window.open_file(filename)

        if new_view:
            new_view.settings().set(
                "folder_native_tabs_plugin_opened",
                True
            )

        new_window.focus()

        print(
            "{}: created tab for {}".format(
                PLUGIN_NAME,
                folder
            )
        )

        sublime.set_timeout(
            lambda: self.close_original_view(original_view),
            250
        )

    def close_original_view(self, view):

        if not view:
            return

        window = view.window()

        if not window:
            return

        # Never automatically close modified files.
        if view.is_dirty():
            print(
                "{}: keeping modified file open".format(
                    PLUGIN_NAME
                )
            )
            return

        window.run_command("close_file")