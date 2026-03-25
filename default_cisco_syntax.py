import sublime
import sublime_plugin
import re


SYNTAX_FILE_NAME = "CiscoCollab.sublime-syntax"
SYNTAX_FALLBACK_PATH = "Packages/CiscoCollab/CiscoCollab.sublime-syntax"
SYNTAX_APPLIED_FLAG = "cisco_syntax_applied"


def _resolve_cisco_syntax_path():
    # Fast path for common package name.
    try:
        sublime.load_resource(SYNTAX_FALLBACK_PATH)
        return SYNTAX_FALLBACK_PATH
    except Exception:
        pass

    # Fallback when the package folder has a different name/version.
    for resource in sublime.find_resources(SYNTAX_FILE_NAME):
        if resource.endswith("/" + SYNTAX_FILE_NAME):
            return resource

    return None


def _is_supported_view(view):
    settings = view.settings()

    if settings.get("is_widget"):
        return False

    if settings.get("panel"):
        return False

    return True


def _apply_cisco_syntax(view):
    if not _is_supported_view(view):
        return

    syntax_path = _resolve_cisco_syntax_path()
    if not syntax_path:
        return

    if view.settings().get("syntax") == syntax_path:
        view.settings().set(SYNTAX_APPLIED_FLAG, True)
        return

    view.set_syntax_file(syntax_path)
    view.settings().set(SYNTAX_APPLIED_FLAG, True)


class SetDefaultSyntax(sublime_plugin.EventListener):

    def on_new(self, view):
        # Aplicar sintaxis Cisco por defecto para nuevos tabs.
        sublime.set_timeout(lambda: _apply_cisco_syntax(view), 0)

        # Resetear flags
        view.settings().set(SYNTAX_APPLIED_FLAG, False)
        view.settings().set("auto_named_final", False)

    def on_load(self, view):
        # Aplicar sintaxis Cisco a cualquier archivo cargado.
        sublime.set_timeout(lambda: _apply_cisco_syntax(view), 0)

        # Resetear flags al cargar
        view.settings().set(SYNTAX_APPLIED_FLAG, False)
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
