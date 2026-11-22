"""DACN regression tests for LMS setup demo data."""

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from lms.demo import demo_data


class TestDACNDemoSetup(unittest.TestCase):

    def test_demo_course_is_created_as_draft(self):
        """New demo course must not publish before lessons exist."""
        course = MagicMock()

        with (
            patch.object(demo_data.frappe.db, "exists", return_value=False),
            patch.object(
                demo_data,
                "create_instructor",
                return_value=SimpleNamespace(name="test-instructor"),
            ),
            patch.object(demo_data.frappe, "new_doc", return_value=course),
        ):
            result = demo_data.create_course()

        fields = course.update.call_args.args[0]

        self.assertEqual(fields["published"], 0)
        self.assertNotIn("published_on", fields)
        course.save.assert_called_once()
        self.assertIs(result, course)

    def test_demo_course_published_after_lessons(self):
        """Setup must create lessons before publishing the course."""
        events = []
        course = MagicMock()
        course.published = 0

        course.reload.side_effect = lambda: events.append("reload")
        course.save.side_effect = lambda: events.append(
            ("save", course.published)
        )

        functions = (
            "create_course",
            "create_user",
            "create_chapter",
            "create_lessons",
            "enroll_student_in_course",
            "create_reviews",
            "create_progress",
        )

        with ExitStack() as stack:
            mocks = {
                name: stack.enter_context(patch.object(demo_data, name))
                for name in functions
            }
            stack.enter_context(
                patch.object(demo_data.frappe.db, "set_single_value")
            )

            mocks["create_course"].return_value = course
            mocks["create_user"].return_value = MagicMock()
            mocks["create_chapter"].side_effect = (
                lambda _: events.append("chapters")
            )
            mocks["create_lessons"].side_effect = (
                lambda _: events.append("lessons")
            )

            demo_data.create_demo_data()

        self.assertEqual(
            events,
            ["chapters", "lessons", "reload", ("save", 1)],
        )
