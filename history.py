import functools
import re

import sublime
from svn import SvnTextCommand, SvnWindowCommand, plugin_file


class SvnBlameCommand(SvnTextCommand):
    def run(self, edit):
        # somewhat custom blame command:
        # -w: ignore whitespace changes
        # -M: retain blame when moving lines
        # -C: retain blame when copying lines between files
        command = ['svn', 'blame', '-w', '-M', '-C']

        s = sublime.load_settings("Svn.sublime-settings")
        selection = self.view.sel()[0]  # todo: multi-select support?
        if not selection.empty() or not s.get('blame_whole_file'):
            # just the lines we have a selection on
            begin_line, begin_column = self.view.rowcol(selection.begin())
            end_line, end_column = self.view.rowcol(selection.end())
            # blame will fail if last line is empty and is included in the selection
            if end_line > begin_line and end_column == 0:
                end_line -= 1
            lines = str(begin_line + 1) + ',' + str(end_line + 1)
            command.extend(('-L', lines))
            callback = self.blame_done
        else:
            callback = functools.partial(self.blame_done,
                    position=self.view.viewport_position())

        command.append(self.get_file_name())
        self.run_command(command, callback)

    def blame_done(self, result, position=None):
        self.scratch(result, title="Svn Blame", position=position,
                syntax=plugin_file("syntax/Svn Blame.tmLanguage"))


class SvnLog(object):
    def run(self, edit=None):
        fn = self.get_file_name()
        return self.run_log(fn != '', '--', fn)

    def run_log(self, follow, *args):
        # the ASCII bell (\a) is just a convenient character I'm pretty sure
        # won't ever come up in the subject of the commit (and if it does then
        # you positively deserve broken output...)
        # 9000 is a pretty arbitrarily chosen limit; picked entirely because
        # it's about the size of the largest repo I've tested this on... and
        # there's a definite hiccup when it's loading that
        command = ['svn', 'log', '--pretty=%s\a%h %an <%aE>\a%ad (%ar)',
            '--date=local', '--max-count=9000', '--follow' if follow else None]
        command.extend(args)
        self.run_command(
            command,
            self.log_done)

    def log_done(self, result):
        self.results = [r.split('\a', 2) for r in result.strip().split('\n')]
        self.quick_panel(self.results, self.log_panel_done)

    def log_panel_done(self, picked):
        if 0 > picked < len(self.results):
            return
        item = self.results[picked]
        # the commit hash is the first thing on the second line
        self.log_result(item[1].split(' ')[0])

    def log_result(self, ref):
        # I'm not certain I should have the file name here; it restricts the
        # details to just the current file. Depends on what the user expects...
        # which I'm not sure of.
        self.run_command(
            ['svn', 'log', '-p', '-1', ref, '--', self.get_file_name()],
            self.details_done)

    def details_done(self, result):
        self.scratch(result, title="Svn Commit Details", syntax=plugin_file("syntax/Svn Commit Message.tmLanguage"))


class SvnLogCommand(SvnLog, SvnTextCommand):
    pass


class SvnLogAllCommand(SvnLog, SvnWindowCommand):
    pass


class SvnShow(object):
    def run(self, edit=None):
        # SvnLog Copy-Past
        self.run_command(
            ['svn', 'log', '--pretty=%s\a%h %an <%aE>\a%ad (%ar)',
            '--date=local', '--max-count=9000', '--', self.get_file_name()],
            self.show_done)

    def show_done(self, result):
        # SvnLog Copy-Past
        self.results = [r.split('\a', 2) for r in result.strip().split('\n')]
        self.quick_panel(self.results, self.panel_done)

    def panel_done(self, picked):
        if 0 > picked < len(self.results):
            return
        item = self.results[picked]
        # the commit hash is the first thing on the second line
        ref = item[1].split(' ')[0]
        self.run_command(
            ['svn', 'show', '%s:%s' % (ref, self.get_relative_file_name())],
            self.details_done,
            ref=ref)

    def details_done(self, result, ref):
        syntax = self.view.settings().get('syntax')
        self.scratch(result, title="%s:%s" % (ref, self.get_file_name()), syntax=syntax)


class SvnShowCommand(SvnShow, SvnTextCommand):
    pass


class SvnShowAllCommand(SvnShow, SvnWindowCommand):
    pass


class SvnGraph(object):
    def run(self, edit=None):
        filename = self.get_file_name()
        self.run_command(
            ['svn', 'log', '--graph', '--pretty=%h -%d (%cr) (%ci) <%an> %s', '--abbrev-commit', '--no-color', '--decorate', '--date=relative', '--follow' if filename else None, '--', filename],
            self.log_done
        )

    def log_done(self, result):
        self.scratch(result, title="Svn Log Graph", syntax=plugin_file("syntax/Svn Graph.tmLanguage"))


class SvnGraphCommand(SvnGraph, SvnTextCommand):
    pass


class SvnGraphAllCommand(SvnGraph, SvnWindowCommand):
    pass


class SvnOpenFileCommand(SvnLog, SvnWindowCommand):
    def run(self):
        self.run_command(['svn', 'branch', '-a', '--no-color'], self.branch_done)

    def branch_done(self, result):
        self.results = result.rstrip().split('\n')
        self.quick_panel(self.results, self.branch_panel_done,
            sublime.MONOSPACE_FONT)

    def branch_panel_done(self, picked):
        if 0 > picked < len(self.results):
            return
        self.branch = self.results[picked].split(' ')[-1]
        self.run_log(False, self.branch)

    def log_result(self, result_hash):
        # the commit hash is the first thing on the second line
        self.ref = result_hash
        self.run_command(
            ['svn', 'ls-tree', '-r', '--full-tree', self.ref],
            self.ls_done)

    def ls_done(self, result):
        # Last two items are the ref and the file name
        # p.s. has to be a list of lists; tuples cause errors later
        self.results = [[match.group(2), match.group(1)] for match in re.finditer(r"\S+\s(\S+)\t(.+)", result)]

        self.quick_panel(self.results, self.ls_panel_done)

    def ls_panel_done(self, picked):
        if 0 > picked < len(self.results):
            return
        item = self.results[picked]

        self.filename = item[0]
        self.fileRef = item[1]

        self.run_command(
            ['svn', 'show', self.fileRef],
            self.show_done)

    def show_done(self, result):
        self.scratch(result, title="%s:%s" % (self.fileRef, self.filename))
