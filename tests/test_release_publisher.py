"""Release target identity, asset verification, and preservation of existing assets."""

import contextlib
import hashlib
import io
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
import publish_release as publisher


def response(status, data):
    result = MagicMock(status_code=status)
    result.json.return_value = data
    return result


class TestReleasePublisher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.exe = os.path.join(self.tmp.name, 'Pulse.exe')
        with open(self.exe, 'wb') as handle:
            handle.write(b'verified-test-binary')
        self.size = os.path.getsize(self.exe)
        self.digest = publisher.compute_sha256(self.exe)
        self.target = 'a' * 40
        self.file_patch = patch.object(publisher, 'EXE_PATH', self.exe)
        self.token_patch = patch.object(publisher, 'get_github_token', return_value='test-secret-never-printed')
        self.file_patch.start()
        self.token_patch.start()
        self.session = MagicMock()
        self.release = {'id': 1, 'assets': [], 'upload_url': 'https://uploads.github.com/test{?name}', 'html_url': 'https://github.com/test/release'}

    def tearDown(self):
        self.file_patch.stop()
        self.token_patch.stop()
        self.tmp.cleanup()

    def run_publish(self, dry_run=False):
        output = io.StringIO()
        with patch('requests.Session', return_value=self.session), contextlib.redirect_stdout(output):
            result = publisher.publish(dry_run=dry_run, target_commit=self.target)
        self.assertNotIn('test-secret-never-printed', output.getvalue())
        return result

    def test_dry_run_has_no_network_or_credential_access(self):
        self.assertEqual(self.run_publish(dry_run=True), 0)
        self.token_patch.stop()
        self.session.get.assert_not_called()
        self.session.post.assert_not_called()

    def test_new_release_uses_verified_commit_and_publishes_after_asset(self):
        self.session.get.side_effect = [response(404, {}), response(404, {})]
        self.session.post.side_effect = [response(201, self.release), response(201, {'size': self.size, 'digest': f'sha256:{self.digest}', 'browser_download_url': 'https://github.com/test/Pulse.exe'})]
        self.session.patch.return_value = response(200, {'html_url': 'https://github.com/test/release'})
        self.assertEqual(self.run_publish(), 0)
        payload = self.session.post.call_args_list[0].kwargs['json']
        self.assertEqual(payload['target_commitish'], self.target)
        self.assertTrue(payload['draft'])
        self.assertEqual(self.session.patch.call_args.kwargs['json'], {'draft': False})
        self.session.delete.assert_not_called()

    def test_different_tag_commit_prevents_mutation(self):
        self.session.get.return_value = response(200, {'sha': 'b' * 40})
        self.assertEqual(self.run_publish(), 1)
        self.session.post.assert_not_called()
        self.session.patch.assert_not_called()

    def test_missing_tag_422_allows_new_release(self):
        self.session.get.side_effect = [
            response(422, {'message': f'No commit found for SHA: {publisher.TAG_NAME}'}),
            response(404, {}),
        ]
        self.session.post.side_effect = [
            response(201, self.release),
            response(201, {'size': self.size, 'digest': f'sha256:{self.digest}',
                           'browser_download_url': 'https://github.com/test/Pulse.exe'}),
        ]
        self.session.patch.return_value = response(200, {'html_url': 'https://github.com/test/release'})
        self.assertEqual(self.run_publish(), 0)
        self.assertEqual(self.session.post.call_args_list[0].kwargs['json']['target_commitish'], self.target)
        self.assertEqual(self.session.patch.call_args.kwargs['json'], {'draft': False})

    def test_unrelated_tag_422_prevents_mutation(self):
        self.session.get.return_value = response(422, {'message': 'Validation Failed'})
        self.assertEqual(self.run_publish(), 1)
        self.session.post.assert_not_called()
        self.session.patch.assert_not_called()
        self.session.delete.assert_not_called()

    def test_existing_different_asset_is_preserved(self):
        release = dict(self.release, assets=[{'name': 'Pulse.exe', 'digest': 'sha256:different', 'size': self.size}])
        self.session.get.side_effect = [response(200, {'sha': self.target}), response(200, release)]
        self.assertEqual(self.run_publish(), 1)
        self.session.delete.assert_not_called()
        self.session.post.assert_not_called()

    def test_matching_existing_asset_is_reused(self):
        release = dict(self.release, assets=[{'name': 'Pulse.exe', 'digest': f'sha256:{self.digest}', 'size': self.size, 'browser_download_url': 'https://github.com/test/Pulse.exe'}])
        self.session.get.side_effect = [response(200, {'sha': self.target}), response(200, release)]
        self.assertEqual(self.run_publish(), 0)
        self.session.post.assert_not_called()
        self.session.delete.assert_not_called()

    def test_wrong_uploaded_checksum_keeps_release_draft(self):
        self.session.get.side_effect = [response(404, {}), response(404, {})]
        self.session.post.side_effect = [response(201, self.release), response(201, {'size': self.size, 'digest': 'sha256:wrong'})]
        self.assertEqual(self.run_publish(), 1)
        self.session.patch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
