import frappe

from frappe.client import set_value as client_set_value
from frappe.tests.utils import FrappeTestCase


class TestDACNPublishingIntegration(FrappeTestCase):

    def setUp(self):
        super().setUp()

        # Run tests as Administrator on the TEST SITE.
        previous_user = frappe.session.user
        frappe.set_user("Administrator")
        self.addCleanup(frappe.set_user, previous_user)

        # Create a real Draft Course with mandatory fields.
        self.course = frappe.get_doc({
            "doctype": "LMS Course",
            "title": f"DACN Integration {frappe.generate_hash(length=8)}",
            "short_introduction": "Automated integration testing",
            "description": "<p>Course for DACN integration tests.</p>",
            "instructors": [
                {
                    "doctype": "Course Instructor",
                    "instructor": "Administrator",
                }
            ],
            "published": 0,
            "upcoming": 0,
        }).insert(ignore_permissions=True)

    def test_publish_empty_course_is_rejected(self):
        # Publishing a course without lessons must fail.
        with self.assertRaisesRegex(
            frappe.ValidationError,
            "Add at least one lesson",
        ):
            client_set_value(
                "LMS Course",
                self.course.name,
                "published",
                1,
            )

        # Verify that the database still contains published = 0.
        published = frappe.db.get_value(
            "LMS Course", self.course.name, "published"
        )
        self.assertEqual(published, 0)

    def test_upcoming_course_can_be_published(self):
        # Upcoming courses may be published without lessons.
        self.course.upcoming = 1
        self.course.save()

        client_set_value(
            "LMS Course",
            self.course.name,
            "published",
            1,
        )

        published = frappe.db.get_value(
            "LMS Course", self.course.name, "published"
        )
        self.assertEqual(published, 1)

    def test_upcoming_to_regular_without_lessons_is_rejected(self):
        """Published upcoming course cannot become regular without lessons."""

        # Step 1: Create an upcoming course.
        self.course.upcoming = 1
        self.course.save()

        # Step 2: Publishing an upcoming course is allowed.
        client_set_value(
            "LMS Course",
            self.course.name,
            "published",
            1,
        )

        # Step 3: Converting to a regular course must fail.
        with self.assertRaisesRegex(
            frappe.ValidationError,
            "Add at least one lesson",
        ):
            client_set_value(
                "LMS Course",
                self.course.name,
                "upcoming",
                0,
            )

        # Step 4: Database must preserve the previous state.
        upcoming = frappe.db.get_value(
            "LMS Course", self.course.name, "upcoming"
        )
        self.assertEqual(upcoming, 1)


    def test_publish_course_with_real_lesson(self):
        """A regular course with a real lesson can be published."""
        from lms.lms.utils import get_lesson_count

        suffix = frappe.generate_hash(length=8)

        # Step 1: Create a real chapter for the Draft Course.
        chapter = frappe.get_doc({
            "doctype": "Course Chapter",
            "title": f"DACN Chapter {suffix}",
            "course": self.course.name,
        }).insert(ignore_permissions=True)

        # Step 2: Create a real lesson linked to that chapter.
        lesson = frappe.get_doc({
            "doctype": "Course Lesson",
            "title": f"DACN Lesson {suffix}",
            "chapter": chapter.name,
            "course": self.course.name,
        }).insert(ignore_permissions=True)

        # Step 3: Link the lesson to the chapter.
        chapter.reload()

        if not any(
            row.lesson == lesson.name
            for row in chapter.lessons
        ):
            chapter.append("lessons", {
                "lesson": lesson.name,
            })
            chapter.save(ignore_permissions=True)

        # Step 4: Link the chapter to the course.
        self.course.reload()

        if not any(
            row.chapter == chapter.name
            for row in self.course.chapters
        ):
            self.course.append("chapters", {
                "chapter": chapter.name,
            })
            self.course.save(ignore_permissions=True)

        # Step 5: Check that the lesson is counted.
        self.assertEqual(
            get_lesson_count(self.course.name),
            1,
        )

        # Step 6: Publish via the real Frappe API.
        client_set_value(
            "LMS Course",
            self.course.name,
            "published",
            1,
        )

        # Step 7: Verify the database state.
        published = frappe.db.get_value(
            "LMS Course",
            self.course.name,
            "published",
        )

        self.assertEqual(published, 1)
