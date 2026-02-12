import sublime
import sublime_plugin

class SetDefaultSyntax(sublime_plugin.EventListener):
    def on_new(self, view):
        view.set_syntax_file("Packages/CiscoCollab/CiscoCollab.sublime-syntax")
    
    def on_load(self, view):
        # Apply to non-defined files with syntax
        if view.settings().get('syntax') == "Packages/Text/Plain text.sublime-syntax":
            view.set_syntax_file("Packages/CiscoCollab/CiscoCollab.sublime-syntax")