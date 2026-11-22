import frappe
from frappe.client import set_value as client_set_value
from frappe.tests.utils import FrappeTestCase


class TestDACNPublishingPermissions(FrappeTestCase):

    def setUp(self):
        super().setUp()

        previous_user = frappe.session.user
        frappe.set_user("Administrator")
        self.addCleanup(frappe.set_user, previous_user)

        # Create a real Draft Upcoming Course on the test site.
        self.course = frappe.get_doc({
            "doctype": "LMS Course",
            "title": f"DACN Permission {frappe.generate_hash(length=8)}",
            "short_introduction": "Permission testing",
            "description": "<p>Test course for user roles.</p>",
            "instructors": [
                {
                    "doctype": "Course Instructor",
                    "instructor": "Administrator",
                }
            ],
            "published": 0,
            "upcoming": 1,
        }).insert(ignore_permissions=True)

    def create_test_user(self, role):
        # Generate a unique user for each test.
        email = (
            f"dacn-{frappe.generate_hash(length=10)}"
            "@example.test"
        )

        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": "DACN Test User",
            "enabled": 1,
            "user_type": "System User",
            "send_welcome_email": 0,
        }).insert(ignore_permissions=True)

        user.add_roles(role)
        return email

    def test_course_creator_can_publish(self):
        user = self.create_test_user("Course Creator")

        # Assign the Course Creator as an instructor.
        self.course.append("instructors", {"instructor": user})
        self.course.save()

        frappe.set_user(user)

        client_set_value(
            "LMS Course",
            self.course.name,
            "published",
            1,
        )

        self.assertEqual(
            frappe.db.get_value(
                "LMS Course", self.course.name, "published"
            ),
            1,
        )

    def test_moderator_can_publish(self):
        user = self.create_test_user("Moderator")
        frappe.set_user(user)

        client_set_value(
            "LMS Course",
            self.course.name,
            "published",
            1,
        )

        self.assertEqual(
            frappe.db.get_value(
                "LMS Course", self.course.name, "published"
            ),
            1,
        )

    def test_student_cannot_publish(self):
        user = self.create_test_user("LMS Student")
        frappe.set_user(user)

        with self.assertRaises(frappe.PermissionError):
            client_set_value(
                "LMS Course",
                self.course.name,
                "published",
                1,
            )

        self.assertEqual(
            frappe.db.get_value(
                "LMS Course", self.course.name, "published"
            ),
            0,
        )

    def test_unassigned_course_creator_cannot_publish(self):
        # This user is not an instructor of the course.
        user = self.create_test_user("Course Creator")
        frappe.set_user(user)

        with self.assertRaises(frappe.PermissionError):
            client_set_value(
                "LMS Course",
                self.course.name,
                "published",
                1,
            )

        self.assertEqual(
            frappe.db.get_value(
                "LMS Course", self.course.name, "published"
            ),
            0,
        )
