import sublime
import re
from svn import svn_root, SvnTextCommand, SvnWindowCommand
import functools


def do_when(conditional, callback, *args, **kwargs):
    if conditional():
        return callback(*args, **kwargs)
    sublime.set_timeout(functools.partial(do_when, conditional, callback, *args, **kwargs), 50)


def goto_xy(view, line, col):
    view.run_command("goto_line", {"line": line})
    for i in range(col):
        view.run_command("move", {"by": "characters", "forward": True})


class SvnDiff (object):
    def run(self, edit=None):
        self.run_command(['svn', 'diff', '--no-color', '--', self.get_file_name()],
                         self.diff_done)

    def diff_done(self, result):
        if not result.strip():
            self.panel("No output")
            return
        s = sublime.load_settings("Svn.sublime-settings")
        if s.get('diff_panel'):
            view = self.panel(result)
        else:
            view = self.scratch(result, title="Svn Diff")

        lines_inserted = view.find_all(r'^\+[^+]{2} ')
        lines_deleted = view.find_all(r'^-[^-]{2} ')

        view.add_regions("inserted", lines_inserted, "markup.inserted.diff", "dot", sublime.HIDDEN)
        view.add_regions("deleted", lines_deleted, "markup.deleted.diff", "dot", sublime.HIDDEN)

        # Store the svn root directory in the view so we can resolve relative paths
        # when the user wants to navigate to the source file.
        view.settings().set("svn_root_dir", svn_root(self.get_working_dir()))


class SvnDiffCommit (object):
    def run(self, edit=None):
        self.run_command(['svn', 'diff', '--cached', '--no-color'],
            self.diff_done)

    def diff_done(self, result):
        if not result.strip():
            self.panel("No output")
            return
        self.scratch(result, title="Svn Diff")


class SvnDiffCommand(SvnDiff, SvnTextCommand):
    pass


class SvnDiffAllCommand(SvnDiff, SvnWindowCommand):
    pass


class SvnDiffCommitCommand(SvnDiffCommit, SvnWindowCommand):
    pass


class SvnDiffTool(object):
    def run(self, edit=None):
        self.run_command(['svn', 'difftool', '--', self.get_file_name()])


class SvnDiffToolCommand(SvnDiffTool, SvnTextCommand):
    pass


class SvnDiffToolAll(SvnWindowCommand):
    def run(self):
        self.run_command(['svn', 'difftool'])


class SvnGotoDiff(sublime_plugin.TextCommand):
    def run(self, edit):
        v = self.view
        view_scope_name = v.scope_name(v.sel()[0].a)
        scope_markup_inserted = ("markup.inserted.diff" in view_scope_name)
        scope_markup_deleted = ("markup.deleted.diff" in view_scope_name)

        if not scope_markup_inserted and not scope_markup_deleted:
            return

        beg = v.sel()[0].a          # Current position in selection
        pt = v.line(beg).a          # First position in the current diff line
        self.column = beg - pt - 1  # The current column (-1 because the first char in diff file)

        self.file_name = None
        hunk_line = None
        line_offset = 0

        while pt > 0:
            line = v.line(pt)
            lineContent = v.substr(line)
            if lineContent.startswith("@@"):
                if not hunk_line:
                    hunk_line = lineContent
            elif lineContent.startswith("+++ b/"):
                self.file_name = v.substr(sublime.Region(line.a+6, line.b)).strip()
                break
            elif not hunk_line and not lineContent.startswith("-"):
                line_offset = line_offset+1

            pt = v.line(pt-1).a

        hunk = re.match(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@.*", hunk_line)
        if not hunk:
            sublime.status_message("No hunk info")
            return

        hunk_start_line = hunk.group(3)
        self.goto_line = int(hunk_start_line) + line_offset - 1

        svn_root_dir = v.settings().get("svn_root_dir")

        # Sanity check and see if the file we're going to try to open even
        # exists. If it does not, prompt the user for the correct base directory
        # to use for their diff.
        full_path_file_name = self.file_name
        if svn_root_dir:
            full_path_file_name = os.path.join(svn_root_dir, self.file_name)
        else:
            svn_root_dir = ""

        if not os.path.isfile(full_path_file_name):
            caption = "Enter base directory for file '%s':" % self.file_name
            v.window().show_input_panel(caption,
                                        svn_root_dir,
                                        self.on_path_confirmed,
                                        None,
                                        None)
        else:
            self.on_path_confirmed(svn_root_dir)

    def on_path_confirmed(self, svn_root_dir):
        v = self.view
        old_svn_root_dir = v.settings().get("svn_root_dir")

        # If the user provided a new svn_root_dir, save it in the view settings
        # so they only have to fix it once
        if old_svn_root_dir != svn_root_dir:
            v.settings().set("svn_root_dir", svn_root_dir)

        full_path_file_name = os.path.join(svn_root_dir, self.file_name)

        new_view = v.window().open_file(full_path_file_name)
        do_when(lambda: not new_view.is_loading(),
                lambda: goto_xy(new_view, self.goto_line, self.column))
