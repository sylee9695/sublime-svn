import os

import sublime
from svn import SvnTextCommand, SvnWindowCommand, svn_root_exist


class SvnInit(object):
    def svn_init(self, directory):
        if os.path.exists(directory):
            self.run_command(['svn', 'init'], self.svn_inited, working_dir=directory)
        else:
            sublime.status_message("Directory does not exist.")

    def svn_inited(self, result):
        sublime.status_message(result)


class SvnInitCommand(SvnInit, SvnWindowCommand):
    def run(self):
        self.get_window().show_input_panel("Svn directory", self.get_working_dir(), self.svn_init, None, None)

    def is_enabled(self):
        if not svn_root_exist(self.get_working_dir()):
            return True
        else:
            return False


class SvnBranchCommand(SvnWindowCommand):
    may_change_files = True
    command_to_run_after_branch = ['checkout']
    extra_flags = []

    def run(self):
        self.run_command(['svn', 'branch', '--no-color'] + self.extra_flags, self.branch_done)

    def branch_done(self, result):
        self.results = result.rstrip().split('\n')
        self.quick_panel(self.results, self.panel_done,
            sublime.MONOSPACE_FONT)

    def panel_done(self, picked):
        if 0 > picked < len(self.results):
            return
        picked_branch = self.results[picked]
        if picked_branch.startswith("*"):
            return
        picked_branch = picked_branch.strip()
        self.run_command(['svn'] + self.command_to_run_after_branch + [picked_branch], self.update_status)

    def update_status(self, result):
        global branch
        branch = ""
        for view in self.window.views():
            view.run_command("svn_branch_status")


class SvnMergeCommand(SvnBranchCommand):
    command_to_run_after_branch = ['merge']
    extra_flags = ['--no-merge']


class SvnDeleteBranchCommand(SvnBranchCommand):
    command_to_run_after_branch = ['branch', '-d']


class SvnNewBranchCommand(SvnWindowCommand):
    def run(self):
        self.get_window().show_input_panel("Branch name", "",
            self.on_input, None, None)

    def on_input(self, branchname):
        if branchname.strip() == "":
            self.panel("No branch name provided")
            return
        self.run_command(['svn', 'checkout', '-b', branchname])


class SvnNewTagCommand(SvnWindowCommand):
    def run(self):
        self.get_window().show_input_panel("Tag name", "", self.on_input, None, None)

    def on_input(self, tagname):
        if not tagname.strip():
            self.panel("No branch name provided")
            return
        self.run_command(['svn', 'tag', tagname])


class SvnShowTagsCommand(SvnWindowCommand):
    def run(self):
        self.run_command(['svn', 'tag'], self.fetch_tag)

    def fetch_tag(self, result):
        self.results = result.rstrip().split('\n')
        self.quick_panel(self.results, self.panel_done)

    def panel_done(self, picked):
        if 0 > picked < len(self.results):
            return
        picked_tag = self.results[picked]
        picked_tag = picked_tag.strip()
        self.run_command(['svn', 'show', picked_tag])


class SvnPushTagsCommand(SvnWindowCommand):
    def run(self):
        self.run_command(['svn', 'push', '--tags'])


class SvnCheckoutCommand(SvnTextCommand):
    may_change_files = True

    def run(self, edit):
        self.run_command(['svn', 'checkout', self.get_file_name()])


class SvnFetchCommand(SvnWindowCommand):
    def run(self):
        self.run_command(['svn', 'fetch'], callback=self.panel)


class SvnPullCommand(SvnWindowCommand):
    def run(self):
        self.run_command(['svn', 'pull'], callback=self.panel)


class SvnPullCurrentBranchCommand(SvnWindowCommand):
    command_to_run_after_describe = 'pull'

    def run(self):
        self.run_command(['svn', 'describe', '--contains',  '--all', 'HEAD'], callback=self.describe_done)

    def describe_done(self, result):
        self.current_branch = result.strip()
        self.run_command(['svn', 'remote'], callback=self.remote_done)

    def remote_done(self, result):
        self.remotes = result.rstrip().split('\n')
        if len(self.remotes) == 1:
            self.panel_done()
        else:
            self.quick_panel(self.remotes, self.panel_done, sublime.MONOSPACE_FONT)

    def panel_done(self, picked=0):
        if picked < 0 or picked >= len(self.remotes):
            return
        self.picked_remote = self.remotes[picked]
        self.picked_remote = self.picked_remote.strip()
        self.run_command(['svn', self.command_to_run_after_describe, self.picked_remote, self.current_branch])


class SvnPushCommand(SvnWindowCommand):
    def run(self):
        self.run_command(['svn', 'push'], callback=self.panel)


class SvnPushCurrentBranchCommand(SvnPullCurrentBranchCommand):
    command_to_run_after_describe = 'push'
