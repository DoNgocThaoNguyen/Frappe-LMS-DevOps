import json
import unittest
from unittest.mock import patch

import validate_deployment as validator


class ReleaseDigestTests(unittest.TestCase):
    image = "example.test/dacn/lms:stable"
    actual = "sha256:" + "a" * 64

    def setUp(self):
        inspect_output = json.dumps(["example.test/dacn/lms@" + self.actual])
        mock = patch.object(validator, "command", return_value=inspect_output)
        mock.start()
        self.addCleanup(mock.stop)

    def test_accepts_matching_digest(self):
        validator.check_digest(self.image, self.actual)

    def test_rejects_mismatched_digest(self):
        wrong = "sha256:" + "b" * 64
        with self.assertRaisesRegex(validator.ValidationError, "digest"):
            validator.check_digest(self.image, wrong)
