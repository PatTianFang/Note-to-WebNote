import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Publish.app import main
from Publish.source_copy import copy_configured_sources


class CopyConfiguredSourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.note_root = self.root / 'Note'
        self.config_path = self.root / 'copy_sources.json'

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_config(self, copies):
        self.config_path.write_text(json.dumps({'copies': copies}), encoding='utf-8')

    def test_copies_directory_contents_with_structure_and_overwrites_files(self):
        source = self.root / 'source'
        (source / 'CLI' / 'docs').mkdir(parents=True)
        (source / 'CLI' / 'docs' / 'guide.md').write_text('new', encoding='utf-8')
        target_file = self.note_root / '雷达智能化' / 'CLI' / 'docs' / 'guide.md'
        target_file.parent.mkdir(parents=True)
        target_file.write_text('old', encoding='utf-8')
        self.write_config([{'source': str(source), 'destination': '雷达智能化'}])

        self.assertTrue(copy_configured_sources(self.config_path, self.note_root))
        self.assertEqual(target_file.read_text(encoding='utf-8'), 'new')

    def test_copies_single_file_to_destination_directory(self):
        source = self.root / 'README.md'
        source.write_text('content', encoding='utf-8')
        self.write_config([{'source': str(source), 'destination': '雷达智能化'}])

        self.assertTrue(copy_configured_sources(self.config_path, self.note_root))
        self.assertEqual((self.note_root / '雷达智能化' / 'README.md').read_text(encoding='utf-8'), 'content')

    def test_copies_multiple_source_destination_pairs(self):
        first_source = self.root / 'first'
        second_source = self.root / 'second'
        first_source.mkdir()
        second_source.mkdir()
        (first_source / 'one.pdf').write_text('one', encoding='utf-8')
        (second_source / 'two.JPG').write_text('two', encoding='utf-8')
        self.write_config([
            {'source': str(first_source), 'destination': '第一目录'},
            {'source': str(second_source), 'destination': '第二目录'},
        ])

        self.assertTrue(copy_configured_sources(self.config_path, self.note_root))
        self.assertEqual((self.note_root / '第一目录' / 'one.pdf').read_text(encoding='utf-8'), 'one')
        self.assertEqual((self.note_root / '第二目录' / 'two.JPG').read_text(encoding='utf-8'), 'two')

    def test_skips_files_outside_the_publish_whitelist(self):
        source = self.root / 'source'
        source.mkdir()
        (source / 'keep.md').write_text('keep', encoding='utf-8')
        (source / 'skip.exe').write_text('skip', encoding='utf-8')
        (source / 'skip.txt').write_text('skip', encoding='utf-8')
        self.write_config([{'source': str(source), 'destination': 'target'}])

        self.assertTrue(copy_configured_sources(self.config_path, self.note_root))
        self.assertTrue((self.note_root / 'target' / 'keep.md').exists())
        self.assertFalse((self.note_root / 'target' / 'skip.exe').exists())
        self.assertFalse((self.note_root / 'target' / 'skip.txt').exists())

    def test_rejects_destination_outside_note_root(self):
        source = self.root / 'source'
        source.mkdir()
        self.write_config([{'source': str(source), 'destination': '../outside'}])

        self.assertFalse(copy_configured_sources(self.config_path, self.note_root))
        self.assertFalse((self.root / 'outside').exists())

    def test_returns_false_when_source_is_missing(self):
        self.write_config([{'source': str(self.root / 'missing'), 'destination': 'target'}])

        self.assertFalse(copy_configured_sources(self.config_path, self.note_root))


class PublishFlowTests(unittest.TestCase):
    @patch('Publish.app.setup_logging')
    @patch('Publish.app.cleanup_local_artifacts')
    @patch('Publish.app.copy_configured_sources', return_value=False)
    def test_copy_failure_stops_publish_before_cleanup(self, copy_sources, cleanup, setup_logging):
        self.assertEqual(main(), 1)
        copy_sources.assert_called_once_with()
        cleanup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
