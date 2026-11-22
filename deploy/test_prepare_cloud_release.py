import unittest

from prepare_cloud_release import REPO, RUN_URL, SITE, URL, prepare


class PrepareCloudReleaseTests(unittest.TestCase):
    def setUp(self):
        self.stable = {
            "image": REPO + ":sha-" + "a" * 12,
            "digest": "sha256:" + "d" * 64,
            "site": SITE,
            "url": URL,
        }
        self.manifest = {
            "commit": "b" * 40,
            "run_id": 123,
            "run_attempt": 1,
            "run_url": RUN_URL + "123",
            "image_ref": REPO + "@sha256:" + "c" * 64,
        }

    def test_candidate_is_bound_to_commit_and_digest(self):
        release = prepare(self.manifest, self.stable, "123")
        self.assertEqual(release["target"]["image"], REPO + ":sha-" + "b" * 12)
        self.assertEqual(release["target"]["digest"], "sha256:" + "c" * 64)
        self.assertTrue(release["cloud_deploy_approved"])

    def test_rejects_manifest_from_another_run(self):
        self.manifest["run_id"] = 124
        with self.assertRaises(ValueError):
            prepare(self.manifest, self.stable, "123")

    def test_rejects_foreign_image_repository(self):
        self.manifest["image_ref"] = "ghcr.io/other/repo@sha256:" + "c" * 64
        with self.assertRaises(ValueError):
            prepare(self.manifest, self.stable, "123")

    def test_rejects_candidate_identical_to_stable(self):
        self.manifest["commit"] = "a" * 40
        with self.assertRaises(ValueError):
            prepare(self.manifest, self.stable, "123")


if __name__ == "__main__":
    unittest.main()
