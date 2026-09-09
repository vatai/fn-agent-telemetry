"""Sandbox and runners for the tests.

Every test runs a plugin the way its agent runs it -- an executable with one
JSON payload on stdin, or `python3 -m agent_telemetry.<module>` -- inside a
temporary `HOME`, project directory and `AGENT_TELEMETRY_DIR`, so nothing reads
or writes the real ones.

The child's environment is built here rather than inherited, because `HOME` is
load-bearing in four places: the instruction files collected, the skill lookup,
the identity resolved, and the paths scrubbed on the way out. A leaked one would
make a result depend on the machine that ran the tests. The project directory
sits *under* the temporary home, which is also the arrangement that exercises
the scrubber's rule that the project prefix wins over the home it is in.

`git config` reads the system file too, which `HOME` does not cover, so
`GIT_CONFIG_NOSYSTEM` is set and the identity is pinned by a file this writes.
"""

import collections
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS_DIR)
PACKAGE_ROOT = os.path.join(REPO, "plugins", "claude-code")

# `tests/run` exports these as PYTHONPATH as well; doing it here too keeps a
# plain `python3 -m unittest discover -s tests` working from the repo root.
for _path in (PACKAGE_ROOT, REPO):
    if _path not in sys.path:
        sys.path.insert(0, _path)

HOOK = "agent-telemetry-hook"
FEEDBACK = "agent-telemetry-feedback"

ACCOUNT_EMAIL = "signed-in@example.com"
GIT_EMAIL = "git-identity@example.com"

Run = collections.namedtuple("Run", "code out err")


class Sandboxed(unittest.TestCase):
    """A temporary home, project and telemetry directory, and ways to run into them."""

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="fn-agent-telemetry-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.home = self.make_directory(self.root, "home")
        self.project = self.make_directory(self.home, "code", "widget")
        self.codex_home = self.make_directory(self.home, ".codex")
        self.telemetry = os.path.join(self.root, "telemetry")

    # --- running the things an agent runs ---------------------------------

    def run_hook(self, plugin, payload, env=None):
        """One hook event, as the agent delivers it: a JSON payload on stdin."""
        return self._run([self._executable(plugin, HOOK)], json.dumps(payload), env)

    def run_hook_at(self, plugin_dir, payload, env=None):
        """The same hook, from a copy of a plugin taken out of the checkout."""
        return self._run([os.path.join(plugin_dir, "bin", HOOK)], json.dumps(payload), env)

    def run_feedback_at(self, plugin_dir, env=None, **answers):
        """The same command, from such a copy."""
        command = [os.path.join(plugin_dir, "bin", FEEDBACK), *options(answers)]
        return self._run(command, "", env)

    def run_raw_hook(self, plugin, stdin, env=None):
        """The same hook, given stdin that is not a payload."""
        return self._run([self._executable(plugin, HOOK)], stdin, env)

    def run_feedback(self, plugin, env=None, **answers):
        """`/fn-eval`'s own executable, with the answers as command-line options."""
        command = [self._executable(plugin, FEEDBACK), *options(answers)]
        return self._run(command, "", env)

    def run_module(self, module, *args, stdin="", env=None):
        """A shared entry point invoked as a module, which is how opencode invokes them."""
        command = [sys.executable, "-m", f"agent_telemetry.{module}", *args]
        return self._run(command, stdin, env, pythonpath=PACKAGE_ROOT)

    # --- what came out ----------------------------------------------------

    def pending(self, session_id):
        """The document still being assembled, or None when there is not one."""
        return _read(os.path.join(self.telemetry, ".pending", session_id + ".json"))

    def results(self):
        return sorted(glob.glob(os.path.join(self.telemetry, "*.json")))

    def one_result(self, session_id):
        """The single result written for a session, by its `<date>-<time>-<id>` name."""
        found = glob.glob(os.path.join(self.telemetry, f"*-{session_id}.json"))
        self.assertEqual(len(found), 1, f"expected one result, found {found}")
        return _read(found[0])

    def everything_collected(self):
        """Every byte under the telemetry directory, results and pending alike."""
        collected = []
        for directory, _subdirs, names in os.walk(self.telemetry):
            collected += [text(os.path.join(directory, name)) for name in names]
        return "\n".join(collected)

    # --- files a session runs against -------------------------------------

    def write_record(self, path, records):
        """A JSONL record of the kind an agent keeps for itself. Returns its path."""
        return self.write_file(path, "".join(json.dumps(r) + "\n" for r in records))

    def write_file(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def copy_plugin(self, plugin):
        """A plugin on its own, the way an installer that copies one would leave it."""
        copied = os.path.join(self.root, "installed", plugin)
        shutil.copytree(os.path.join(REPO, "plugins", plugin), copied)
        return copied

    def claude_account(self, email=ACCOUNT_EMAIL):
        """Claude Code's own config, holding the account it is signed in as."""
        config = {"oauthAccount": {"emailAddress": email}}
        return self.write_file(os.path.join(self.home, ".claude.json"), json.dumps(config))

    def git_identity(self, email=GIT_EMAIL):
        """The rung below: git's own idea of who the user is."""
        return self.write_file(
            os.path.join(self.home, ".gitconfig"), f"[user]\n\temail = {email}\n"
        )

    def env(self, **overrides):
        """The child's whole environment. An override of None removes a variable."""
        base = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": self.home,
            "USER": "tester",
            "AGENT_TELEMETRY_DIR": self.telemetry,
            "CODEX_HOME": self.codex_home,
            "XDG_CONFIG_HOME": os.path.join(self.home, ".config"),
            "CLAUDE_PLUGIN_ROOT": os.path.join(REPO, "plugins", "claude-code"),
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        return {key: value for key, value in (base | overrides).items() if value is not None}

    def _run(self, command, stdin, env, pythonpath=None):
        environment = self.env() if env is None else env
        if pythonpath:
            environment = environment | {"PYTHONPATH": pythonpath}
        done = subprocess.run(
            command, input=stdin, cwd=self.project, env=environment, capture_output=True, text=True
        )
        return Run(done.returncode, done.stdout, done.stderr)

    def _executable(self, plugin, name):
        return os.path.join(REPO, "plugins", plugin, "bin", name)

    def make_directory(self, *parts):
        path = os.path.join(*parts)
        os.makedirs(path, exist_ok=True)
        return path


def options(answers):
    """`fom="flops"` -> `["--fom", "flops"]`. A None answer is simply not passed."""
    given = [(key, value) for key, value in answers.items() if value is not None]
    return [part for key, value in given for part in (f"--{key.replace('_', '-')}", str(value))]


def _read(path):
    if not os.path.isfile(path):
        return None
    return json.loads(text(path))


def text(path):
    """A file as it reads on disk."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()
