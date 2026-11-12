"""Mission 5 Linux-only synthetic laboratory; Python PSF-2.0.

No operational source/destination arguments: all data is generated in a new
private /tmp directory. No network, cleanup, scheduler or production integration.
Requires an independently verified Restic executable (BSD-2-Clause).
Artifacts are retained privately; never add laboratory output to Git.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time

from backup_architecture import file_digest, load_policy, restore_target


@contextmanager
def barrier(lock):
    # Every cooperative writer AND capture takes the same interprocess lock.
    # Closing on exception/process exit releases the kernel lock.
    with lock.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def writer(root, count, ready=None, release=None):
    for generation in range(1, count + 1):
        with barrier(root / 'barrier.lock'):
            with sqlite3.connect(root / 'state.sqlite') as db:
                db.execute('UPDATE state SET generation=?', (generation,))
            if ready is not None and generation == 1:
                ready.set()
                if not release.wait(10):
                    raise TimeoutError('synthetic coordination timeout')
            time.sleep(.002)  # Deliberately expose DB/JSON transaction gap.
            tmp = root / 'next.json'
            tmp.write_text(json.dumps({'generation': generation}))
            os.replace(tmp, root / 'state.json')


def capture(root, target):
    with barrier(root / 'barrier.lock'):
        target.mkdir(mode=0o700)
        with sqlite3.connect(root / 'state.sqlite') as src:
            with sqlite3.connect(target / 'state.sqlite') as dst:
                src.backup(dst)
        shutil.copyfile(root / 'state.json', target / 'state.json')
    with sqlite3.connect(target / 'state.sqlite') as db:
        assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        generation = db.execute('SELECT generation FROM state').fetchone()[0]
    assert generation == json.loads((target / 'state.json').read_text())['generation']
    return generation


class Lab:
    def __init__(self, binary):
        os.umask(0o077)
        self.root = Path(tempfile.mkdtemp(prefix='seppe-m5-lab-', dir='/tmp'))
        self.binary = str(Path(binary).resolve(strict=True))
        self.results = []
        self.commands = []
        self.started = time.monotonic()
        self.env = {'PATH': os.defpath, 'HOME': str(self.root), 'LC_ALL': 'C',
                    'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
                    'GIT_TERMINAL_PROMPT': '0', 'RESTIC_PASSWORD_FILE': str(self.root / 'password'),
                    'RESTIC_CACHE_DIR': str(self.root / 'cache'), 'GOMAXPROCS': '2'}
        (self.root / 'password').write_text(os.urandom(32).hex())
        (self.root / 'wrong').write_text(os.urandom(32).hex())
        self.repo = self.root / 'repository'
        self.source = self.root / 'source'
        self.source.mkdir()
        print('Private laboratory:', self.root, flush=True)

    def command(self, args, cwd=None, expected=(0,), env=None):
        start = time.monotonic()
        result = subprocess.run(args, cwd=cwd or self.root, env=env or self.env,
                                text=True, capture_output=True, timeout=180)
        self.commands.append({'argv': [str(a).replace(str(self.root), '<LAB>') for a in args],
                              'returncode': result.returncode,
                              'seconds': round(time.monotonic()-start, 3)})
        assert result.returncode in expected, (args, result.returncode, result.stderr[-2000:])
        return result

    def restic(self, *args, repo=None, **kwargs):
        return self.command([self.binary, '-r', str(repo or self.repo), '--no-cache', *args], **kwargs)

    def record(self, name, **evidence):
        row = {'test': name, 'status': 'PASS', **evidence}
        self.results.append(row)
        print(json.dumps(row), flush=True)
        self.save()

    def save(self):
        (self.root / 'evidence.json').write_text(json.dumps({
            'seconds': round(time.monotonic()-self.started, 3),
            'results': self.results, 'commands': self.commands}, indent=2))

    def backup(self, *paths, expected=(0,)):
        result = self.restic('backup', '--json', '--host', 'synthetic', '--tag', 'mission5',
                             '--', *(paths or ('.',)), cwd=self.source, expected=expected)
        summaries = [json.loads(line) for line in result.stdout.splitlines()
                     if json.loads(line).get('message_type') == 'summary']
        assert summaries
        return result, summaries[-1]

    def restore(self, snapshot, name):
        target = restore_target(self.root / name, [self.source, self.repo])
        target.mkdir(mode=0o700)  # Exclusive reservation inside private parent.
        self.restic('restore', snapshot, '--target', str(target), '--verify', '--sparse')
        return target

    def run(self):
        load_policy()  # Fail closed if any production flag is enabled.
        version = self.command([self.binary, 'version']).stdout.strip()
        self.record('verified executable runs', version=version,
                    binary_sha256=file_digest(self.binary))
        self.restic('init', '--repository-version', '2')
        (self.source / 'layout.json').write_text('{"version":1}')
        (self.source / 'stable.bin').write_bytes(os.urandom(8*1024*1024))
        big = self.source / 'large.sparse'
        size = 2*1024**3 + 16*1024**2
        assert shutil.disk_usage(self.root).free > 4*1024**3
        with big.open('wb') as out:
            out.write(b'synthetic-v1'); out.truncate(size)
        before_hash = file_digest(big)
        _, initial = self.backup()
        self.record('initial and multigiB', logical_bytes=size,
                    source_allocated_bytes=big.stat().st_blocks*512, summary=initial)
        (self.source / 'layout.json').write_text('{"version":2}')
        with big.open('r+b') as out:
            out.seek(1024**3); out.write(b'synthetic-v2')
        after_hash = file_digest(big)
        _, incremental = self.backup()
        assert incremental['data_added'] < size//10
        assert incremental['files_unmodified'] >= 1
        self.record('incremental deduplication', summary=incremental)
        _, unchanged = self.backup()
        assert unchanged['data_blobs'] == 0
        self.record('unchanged backup', summary=unchanged)
        self.restic('check', '--read-data')
        self.record('full repository integrity')
        for summary, name, digest, version_number in (
                (initial, 'restore-v1', before_hash, 1),
                (incremental, 'restore-v2', after_hash, 2)):
            target = self.restore(summary['snapshot_id'], name)
            assert file_digest(target / 'large.sparse') == digest
            assert (target / 'large.sparse').stat().st_size == size
            assert json.loads((target / 'layout.json').read_text())['version'] == version_number
            assert file_digest(target / 'stable.bin') == file_digest(self.source / 'stable.bin')
            assert {p.name for p in target.iterdir()} == {p.name for p in self.source.iterdir()}
            self.record(name, snapshot_id=summary['snapshot_id'], large_sha256=digest,
                        restored_allocated_bytes=(target / 'large.sparse').stat().st_blocks*512)
        env = dict(self.env, RESTIC_PASSWORD_FILE=str(self.root / 'wrong'))
        result = self.restic('snapshots', env=env, expected=(12,))
        self.record('wrong password refused', returncode=result.returncode)
        sentinel = self.root / 'existing'
        sentinel.mkdir(); (sentinel / 'keep').write_text('synthetic sentinel')
        try:
            restore_target(sentinel, [self.source, self.repo])
        except ValueError:
            pass
        else:
            raise AssertionError('existing destination accepted')
        assert (sentinel / 'keep').read_text() == 'synthetic sentinel'
        self.record('existing restore target refused by wrapper')
        config_hash = file_digest(self.repo / 'config')
        result = self.restic('init', expected=(1,))
        assert file_digest(self.repo / 'config') == config_hash
        self.record('existing repository init refused', returncode=result.returncode)
        result = self.restic('snapshots', repo=self.root / 'unavailable', expected=(10,))
        assert not (self.root / 'unavailable').exists()
        self.record('repository unavailable', returncode=result.returncode)
        result, partial = self.backup('layout.json', 'missing-synthetic-file', expected=(3,))
        assert partial.get('snapshot_id')
        # Promotion gate: NEVER accept a nonzero backup exit, even with a snapshot ID.
        assert result.returncode != 0
        self.record('incomplete snapshot rejected', returncode=result.returncode,
                    snapshot_created=True, promoted=False)
        self.concurrent_change()
        self.coordination()
        self.bundle()
        corrupt = self.root / 'corrupt-repository'
        shutil.copytree(self.repo, corrupt)
        pack = next((corrupt / 'data').glob('*/*'))
        pack.chmod(0o600)  # Only the disposable synthetic corruption copy.
        with pack.open('r+b') as out:
            out.seek(0); byte = out.read(1); out.seek(0); out.write(bytes([byte[0] ^ 1]))
        result = self.restic('check', '--read-data', repo=corrupt, expected=(1,))
        self.record('corrupted pack detected', returncode=result.returncode)
        self.restic('check', '--read-data')
        self.record('original synthetic repository preserved')
        self.save()

    def concurrent_change(self):
        changing = self.source / 'changing.bin'
        changing.write_bytes(b'initial')
        initial = file_digest(changing)
        stop = threading.Event()
        def mutate():
            n = 0
            while not stop.wait(.005):
                n += 1
                changing.write_text(str(n))
        thread = threading.Thread(target=mutate)
        thread.start()
        try:
            result, _ = self.backup(expected=(0, 3))
        finally:
            stop.set(); thread.join()
        assert file_digest(changing) != initial
        self.record('changed during capture rejected by inventory gate',
                    restic_returncode=result.returncode, promoted=False,
                    limitation='Restic alone does not ensure cross-file consistency')

    def coordination(self):
        root = self.root / 'coordination'; root.mkdir()
        with sqlite3.connect(root / 'state.sqlite') as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE state(generation INTEGER NOT NULL)')
            db.execute('INSERT INTO state VALUES(0)')
        (root / 'state.json').write_text('{"generation":0}')
        ctx = mp.get_context('spawn')
        ready, release = ctx.Event(), ctx.Event()
        process = ctx.Process(target=writer, args=(root, 40, ready, release))
        process.start()
        assert ready.wait(10)
        # An uncoordinated read sees the deliberately exposed inconsistent pair.
        with sqlite3.connect(root / 'state.sqlite') as db:
            assert db.execute('SELECT generation FROM state').fetchone()[0] == 1
        assert json.loads((root / 'state.json').read_text())['generation'] == 0
        with (root / 'barrier.lock').open('a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError('writer lock ineffective')
        release.set()
        start = time.monotonic()
        generations = [capture(root, root / f'capture-{n}') for n in range(30)]
        process.join(15)
        assert process.exitcode == 0
        assert capture(root, root / 'final') == 40
        try:
            with barrier(root / 'barrier.lock'):
                raise RuntimeError('synthetic capture failure')
        except RuntimeError:
            pass
        with (root / 'barrier.lock').open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = self.restic('backup', '--json', '--host', 'synthetic',
                             '--tag', 'coordinated', '--', '.', cwd=root / 'final')
        summary = [json.loads(line) for line in result.stdout.splitlines()
                   if json.loads(line).get('message_type') == 'summary'][-1]
        restored = self.restore(summary['snapshot_id'], 'restore-coordinated')
        with sqlite3.connect(restored / 'state.sqlite') as db:
            assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
            assert db.execute('SELECT generation FROM state').fetchone()[0] == 40
        assert json.loads((restored / 'state.json').read_text())['generation'] == 40
        self.record('coordinated SQLite JSON Restic recovery',
                    snapshot_id=summary['snapshot_id'], generation=40)
        self.record('SQLite JSON cooperative process barrier', captures=31,
                    final_generation=40, seconds=round(time.monotonic()-start, 3),
                    inconsistent_without_barrier=True, exception_releases_lock=True,
                    generations_observed=sorted(set(generations)))

    def bundle(self):
        source = self.root / 'git-source'
        def git(*args, cwd=source):
            return self.command(['git', *args], cwd=cwd)
        git('init', '-b', 'main', str(source), cwd=self.root)
        git('config', 'user.name', 'Synthetic Test')
        git('config', 'user.email', 'synthetic@example.invalid')
        (source / 'code.txt').write_text('version one\n')
        git('add', 'code.txt'); git('commit', '-m', 'synthetic v1')
        first = git('rev-parse', 'HEAD').stdout.strip()
        git('tag', '-a', 'v1', '-m', 'synthetic v1')
        git('checkout', '-b', 'feature')
        (source / 'code.txt').write_text('version two\n')
        git('add', 'code.txt'); git('commit', '-m', 'synthetic v2')
        git('tag', 'v2')
        refs = git('show-ref').stdout
        bundle = self.root / 'synthetic.bundle'
        git('bundle', 'create', str(bundle), '--all')
        git('bundle', 'verify', str(bundle))
        restored = self.root / 'git-restored'
        git('clone', '--mirror', str(bundle), str(restored), cwd=self.root)
        assert git('show-ref', cwd=restored).stdout == refs
        git('fsck', '--full', cwd=restored)
        assert git('show', f'{first}:code.txt', cwd=restored).stdout == 'version one\n'
        assert git('show', 'refs/tags/v2:code.txt', cwd=restored).stdout == 'version two\n'
        self.record('synthetic Git bundle reconstruction', branches=2, tags=2,
                    exact_refs=True, bundle_sha256=file_digest(bundle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restic', required=True, type=Path)
    args = parser.parse_args()
    lab = Lab(args.restic)
    try:
        lab.run()
    finally:
        lab.save()


if __name__ == '__main__':
    main()
