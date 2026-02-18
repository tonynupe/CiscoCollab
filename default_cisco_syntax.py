import sublime
import sublime_plugin
import re


class SetDefaultSyntax(sublime_plugin.EventListener):

    def on_new(self, view):
        # Aplicar sintaxis por defecto
        view.set_syntax_file("Packages/CiscoCollab/CiscoCollab.sublime-syntax")

        # Resetear flags
        view.settings().set("auto_named_final", False)

    def on_load(self, view):
        # Aplicar a archivos Plain Text
        if view.settings().get('syntax') == "Packages/Text/Plain text.sublime-syntax":
            view.set_syntax_file("Packages/CiscoCollab/CiscoCollab.sublime-syntax")

        # Resetear flags al cargar
        view.settings().set("auto_named_final", False)

    def on_modified_async(self, view):

        # Solo aplicar si es archivo nuevo sin guardar (Untitled)
        if view.file_name() is not None:
            return

        # Si ya fue confirmado, no seguir actualizando
        if view.settings().get("auto_named_final"):
            return

        # Obtener primera línea
        first_line_region = view.line(0)
        first_line = view.substr(first_line_region).strip()

        # Si está vacía → nombre temporal
        if not first_line:
            view.set_name("Untitled")
            return

        # Limpiar caracteres inválidos
        clean_name = re.sub(r'[\\/*?:"<>|]', "", first_line)

        if not clean_name:
            view.set_name("Untitled")
            return

        # Actualizar nombre dinámicamente
        view.set_name(clean_name)

    def on_selection_modified_async(self, view):

        # Solo aplicar en archivos sin guardar
        if view.file_name() is not None:
            return

        for sel in view.sel():
            row, _ = view.rowcol(sel.begin())

            # Si está en primera línea → permitir renombrado
            if row == 0:
                view.settings().set("auto_named_final", False)
                return

            # Si salió → bloquear
            if row > 0:
                view.settings().set("auto_named_final", True)
                return
