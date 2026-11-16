"""Guard tests never invoke GitHub, Git or the operational working tree."""
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('guarded_patch', Path(__file__).resolve().parents[1] / 'scripts/bi_factory_patch_agent.py')
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)
SHA = 'a' * 40
BODY = f'commit={SHA}\nbranch=fix/novo-produto-ficha-isolada-20261116'

class PatchGuards(unittest.TestCase):
    def runner(self, dirty=False, paths='web/bi_factory/src/main.jsx', conflict=False, branch='teste/cadastro-filtros-20261113'):
        def run(*args, **kwargs):
            output = ''
            code = 0
            if args[:3] == ('git', 'branch', '--show-current'): output = branch
            elif args[:3] == ('git', 'diff', '--name-only'): output = paths
            elif args[:3] == ('git', 'status', '--porcelain'): output = ' M main.jsx' if dirty else ''
            elif args[:3] == ('git', 'diff', '--binary'): output = 'synthetic-patch'
            elif args[:3] == ('git', 'apply', '--check') and conflict: code = 1
            return subprocess.CompletedProcess(args, code, output, 'conflict' if code else '')
        return run

    def test_rejects_malformed_request_without_commands(self):
        with patch.object(agent, 'run') as run:
            with self.assertRaises(RuntimeError): agent.apply('commit=main\nbranch=main')
            run.assert_not_called()

    def test_rejects_wrong_local_branch_before_fetch(self):
        with patch.object(agent, 'run', side_effect=self.runner(branch='main')) as run:
            with self.assertRaisesRegex(RuntimeError, 'Branch local'): agent.apply(BODY)
            self.assertEqual(run.call_count, 1)

    def test_rejects_disallowed_files(self):
        with patch.object(agent, 'run', side_effect=self.runner(paths='scripts/serve_bi_factory_api.py')) as run:
            with self.assertRaisesRegex(RuntimeError, 'fora da lista'): agent.apply(BODY)
            self.assertFalse(any(c.args[:2] == ('git', 'apply') for c in run.call_args_list))

    def test_preserves_dirty_target(self):
        with patch.object(agent, 'run', side_effect=self.runner(dirty=True)) as run:
            with self.assertRaisesRegex(RuntimeError, 'Arquivo local alterado'): agent.apply(BODY)
            self.assertFalse(any(c.args[:2] == ('git', 'apply') for c in run.call_args_list))

    def test_conflict_never_applies(self):
        with patch.object(agent, 'run', side_effect=self.runner(conflict=True)) as run:
            with self.assertRaisesRegex(RuntimeError, 'conflitos'): agent.apply(BODY)
            self.assertFalse(any(c.args == ('git', 'apply', '-') for c in run.call_args_list))

    def test_success_checks_before_apply(self):
        with patch.object(agent, 'run', side_effect=self.runner()) as run:
            agent.apply(BODY)
            applies = [c.args for c in run.call_args_list if c.args[:2] == ('git', 'apply')]
            self.assertEqual(applies, [('git', 'apply', '--check', '-'), ('git', 'apply', '-')])
            self.assertFalse(any('reset' in c.args or 'checkout' in c.args for c in run.call_args_list))

    def test_rejects_other_issue_authors(self):
        import json
        with tempfile.TemporaryDirectory() as root, patch.object(agent, 'STATE', Path(root)/'seen.json'), patch.object(agent, 'gh', return_value=json.dumps([{'number':99,'title':agent.TITLE,'author':{'login':'other'},'body':BODY}])), patch.object(agent, 'apply') as apply:
            agent.cycle()
            apply.assert_not_called()

    def test_singleton_does_not_start_second_server(self):
        import fcntl
        with tempfile.TemporaryDirectory() as root, patch.object(agent,'ROOT',Path(root)), patch.object(agent,'serve') as serve:
            (Path(root)/'.git').mkdir()
            with (Path(root)/'.git/bi-factory-patch-agent.lock').open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                agent.main()
                serve.assert_not_called()

class MonitorLifecycle(unittest.TestCase):
    def test_singleton_restart_and_no_inherited_lock(self):
        import os
        import time
        script = Path(__file__).resolve().parents[1]/'scripts/autostart_bi_factory_codespaces.sh'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('.git','bin','scripts','web/bi_factory/node_modules/.bin'):
                (root/name).mkdir(parents=True,exist_ok=True)
            (root/'web/bi_factory/node_modules/.bin/vite').touch()
            (root/'scripts/bi_factory_patch_agent.py').touch()
            for name, text in {
                'node':'#!/bin/sh\nexit 0\n',
                'curl':'#!/bin/sh\nexit 0\n',
                'gh':'#!/bin/sh\nexit 0\n',
                'pgrep':'#!/bin/sh\nexit 1\n',
                'python3':'#!/bin/sh\nif test -e /proc/$$/fd/9; then echo LEAK >> "$MONITOR_TEST_LOG"; else echo CLOSED >> "$MONITOR_TEST_LOG"; fi\n',
            }.items():
                path = root/'bin'/name
                path.write_text(text)
                path.chmod(0o700)
            log = root/'agents.log'
            env = {**os.environ,'PATH':str(root/'bin')+os.pathsep+os.environ['PATH'],'BI_FACTORY_ROOT':str(root),'MONITOR_TEST_LOG':str(log)}
            def count():
                return len(log.read_text().splitlines()) if log.exists() else 0
            def wait_count(expected):
                for _ in range(100):
                    if count() >= expected: return
                    time.sleep(.02)
                self.fail('Monitor did not start agents')
            first = subprocess.Popen(['bash',str(script),'--monitor'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            second = None
            try:
                wait_count(2)
                duplicate = subprocess.run(['bash',str(script),'--monitor'],env=env,timeout=3,capture_output=True)
                self.assertEqual(duplicate.returncode,0)
                self.assertEqual(count(),2)
                first.terminate(); first.wait(timeout=3)
                second = subprocess.Popen(['bash',str(script),'--monitor'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                wait_count(4)
                self.assertEqual(log.read_text().splitlines(),['CLOSED']*4)
            finally:
                for proc in (first,second):
                    if proc is not None and proc.poll() is None:
                        proc.terminate(); proc.wait(timeout=3)
