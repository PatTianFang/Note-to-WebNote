import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Publish.git_ops import deploy_webnote_repo


def run_git(repo, *args):
    return subprocess.run(
        ['git', *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
    ).stdout.strip()


class DeployWebNoteRepoTests(unittest.TestCase):
    def test_pushes_clean_worktree_when_local_branch_is_ahead(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            remote = root / 'remote.git'
            repo = root / 'repo'
            run_git(root, 'init', '--bare', str(remote))
            run_git(root, 'init', '-b', 'master', str(repo))
            run_git(repo, 'config', 'user.name', 'Publish Test')
            run_git(repo, 'config', 'user.email', 'publish@example.com')
            run_git(repo, 'remote', 'add', 'origin', str(remote))

            tracked_file = repo / 'post.txt'
            tracked_file.write_text('first', encoding='utf-8')
            run_git(repo, 'add', 'post.txt')
            run_git(repo, 'commit', '-m', 'initial')
            run_git(repo, 'push', '-u', 'origin', 'master')

            tracked_file.write_text('second', encoding='utf-8')
            run_git(repo, 'commit', '-am', 'local only')
            local_head = run_git(repo, 'rev-parse', 'HEAD')
            self.assertEqual(run_git(repo, 'status', '--porcelain'), '')
            self.assertNotEqual(local_head, run_git(repo, 'rev-parse', 'origin/master'))

            with patch('Publish.git_ops.WEBNOTE_ROOT', str(repo)):
                self.assertTrue(deploy_webnote_repo())

            remote_head = run_git(repo, 'ls-remote', 'origin', 'refs/heads/master').split()[0]
            self.assertEqual(remote_head, local_head)


if __name__ == '__main__':
    unittest.main()
