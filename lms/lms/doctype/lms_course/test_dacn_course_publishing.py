import unittest
from unittest.mock import patch

import frappe


COUNT_FUNCTION = (
    "lms.lms.doctype.lms_course.lms_course.get_lesson_count"
)


class TestDACNCoursePublishing(unittest.TestCase):

    def setUp(self):
        self.course = frappe.new_doc("LMS Course")
        self.course.name = "dacn-publishing-test"
        self.course.title = "DACN Publishing Test"
        self.course.published = 0
        self.course.upcoming = 0

    def test_draft_without_lessons(self):
        """Draft course must be allowed without lessons."""

        with patch(COUNT_FUNCTION) as count:
            self.course.validate_published()
            count.assert_not_called()

    def test_publish_without_lessons(self):
        """Normal course cannot be published without lessons."""

        self.course.published = 1

        with patch(COUNT_FUNCTION, return_value=0):
            with self.assertRaises(frappe.ValidationError):
                self.course.validate_published()

    def test_publish_with_lessons(self):
        """Course with at least one lesson can be published."""

        self.course.published = 1

        with patch(COUNT_FUNCTION, return_value=1) as count:
            self.course.validate_published()
            count.assert_called_once_with(self.course.name)

        self.assertTrue(self.course.published_on)

    def test_upcoming_course_without_lessons(self):
        """Upcoming courses may be published without lessons."""

        self.course.published = 1
        self.course.upcoming = 1

        with patch(COUNT_FUNCTION) as count:
            self.course.validate_published()
            count.assert_not_called()
