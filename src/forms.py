"""
WTForms for Authentication System
===============================

Form definitions for user authentication and profile management.
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    BooleanField,
    SelectField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo,
    ValidationError,
    Optional,
    Regexp,
)

try:
    from .auth import User
    from .extensions import get_session
except ImportError:
    from auth import User
    from extensions import get_session


class LoginForm(FlaskForm):
    """User login form."""

    username = StringField(
        "Username or Email",
        validators=[DataRequired(), Length(min=3, max=80)],
        render_kw={
            "placeholder": "Enter username or email",
            "autocomplete": "username",
        },
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired()],
        render_kw={"placeholder": "Enter password", "autocomplete": "current-password"},
    )
    remember_me = BooleanField("Keep me logged in")
    submit = SubmitField("Sign In")


class RegistrationForm(FlaskForm):
    """User registration form."""

    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=20),
            Regexp(
                r"^[a-zA-Z0-9_-]+$",
                message="Username must contain only letters, numbers, hyphens, and underscores",
            ),
        ],
        render_kw={"placeholder": "Choose a username"},
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=120)],
        render_kw={"placeholder": "Enter your email address", "autocomplete": "email"},
    )
    first_name = StringField(
        "First Name",
        validators=[Optional(), Length(max=50)],
        render_kw={"placeholder": "Your first name"},
    )
    last_name = StringField(
        "Last Name",
        validators=[Optional(), Length(max=50)],
        render_kw={"placeholder": "Your last name"},
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, message="Password must be at least 8 characters long"),
        ],
        render_kw={
            "placeholder": "Choose a strong password",
            "autocomplete": "new-password",
        },
    )
    password2 = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match"),
        ],
        render_kw={
            "placeholder": "Confirm your password",
            "autocomplete": "new-password",
        },
    )
    submit = SubmitField("Create Account")

    def validate_username(self, username):
        """Validate username uniqueness."""
        with get_session() as session:
            user = session.query(User).filter_by(username=username.data).first()
            if user:
                raise ValidationError(
                    "Username already taken. Please choose a different one."
                )

    def validate_email(self, email):
        """Validate email uniqueness."""
        with get_session() as session:
            user = session.query(User).filter_by(email=email.data).first()
            if user:
                raise ValidationError(
                    "Email already registered. Please use a different email."
                )


class ProfileForm(FlaskForm):
    """User profile edit form."""

    email = StringField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=120)],
        render_kw={"autocomplete": "email"},
    )
    first_name = StringField(
        "First Name",
        validators=[Optional(), Length(max=50)],
        render_kw={"placeholder": "Your first name"},
    )
    last_name = StringField(
        "Last Name",
        validators=[Optional(), Length(max=50)],
        render_kw={"placeholder": "Your last name"},
    )
    submit = SubmitField("Update Profile")


class ChangePasswordForm(FlaskForm):
    """Change password form."""

    current_password = PasswordField(
        "Current Password",
        validators=[DataRequired()],
        render_kw={
            "placeholder": "Enter current password",
            "autocomplete": "current-password",
        },
    )
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(min=8, message="Password must be at least 8 characters long"),
        ],
        render_kw={"placeholder": "Enter new password", "autocomplete": "new-password"},
    )
    new_password2 = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo("new_password", message="Passwords must match"),
        ],
        render_kw={
            "placeholder": "Confirm new password",
            "autocomplete": "new-password",
        },
    )
    submit = SubmitField("Change Password")


class AdminUserForm(FlaskForm):
    """Admin user management form."""

    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=3, max=20)],
        render_kw={"readonly": True},
    )
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField("First Name", validators=[Optional(), Length(max=50)])
    last_name = StringField("Last Name", validators=[Optional(), Length(max=50)])
    role = SelectField(
        "Role",
        choices=[
            ("user", "User"),
            ("researcher", "Researcher"),
            ("admin", "Administrator"),
        ],
        validators=[DataRequired()],
    )
    is_active = BooleanField("Active Account")
    is_verified = BooleanField("Verified Email")
    submit = SubmitField("Update User")


class CreateUserForm(FlaskForm):
    """Admin create user form."""

    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=20),
            Regexp(
                r"^[a-zA-Z0-9_-]+$",
                message="Username must contain only letters, numbers, hyphens, and underscores",
            ),
        ],
    )
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField("First Name", validators=[Optional(), Length(max=50)])
    last_name = StringField("Last Name", validators=[Optional(), Length(max=50)])
    role = SelectField(
        "Role",
        choices=[
            ("user", "User"),
            ("researcher", "Researcher"),
            ("admin", "Administrator"),
        ],
        default="user",
        validators=[DataRequired()],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, message="Password must be at least 8 characters long"),
        ],
    )
    password2 = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match"),
        ],
    )
    send_welcome_email = BooleanField("Send Welcome Email", default=True)
    submit = SubmitField("Create User")

    def validate_username(self, username):
        """Validate username uniqueness."""
        with get_session() as session:
            user = session.query(User).filter_by(username=username.data).first()
            if user:
                raise ValidationError("Username already taken.")

    def validate_email(self, email):
        """Validate email uniqueness."""
        with get_session() as session:
            user = session.query(User).filter_by(email=email.data).first()
            if user:
                raise ValidationError("Email already registered.")


class APITokenForm(FlaskForm):
    """API token creation form."""

    name = StringField(
        "Token Name",
        validators=[DataRequired(), Length(max=100)],
        render_kw={"placeholder": "e.g., My Analysis Script"},
    )
    expires_days = SelectField(
        "Expires In",
        choices=[
            ("7", "7 days"),
            ("30", "30 days"),
            ("90", "90 days"),
            ("365", "1 year"),
            ("0", "Never"),
        ],
        default="30",
        coerce=int,
        validators=[DataRequired()],
    )
    can_read = BooleanField("Read Access", default=True)
    can_write = BooleanField("Write Access", default=False)
    can_admin = BooleanField("Admin Access", default=False)
    submit = SubmitField("Create Token")


class PreferencesForm(FlaskForm):
    """User preferences form."""

    email_notifications = BooleanField("Email Notifications", default=True)
    job_completion_notifications = BooleanField(
        "Job Completion Notifications", default=True
    )
    security_alerts = BooleanField("Security Alerts", default=True)
    weekly_summaries = BooleanField("Weekly Summary Reports", default=False)

    default_analysis_types = SelectField(
        "Default Analysis Types",
        choices=[
            ("security", "Security Analysis"),
            ("performance", "Performance Testing"),
            ("all", "All Analysis Types"),
        ],
        default="security",
    )

    results_per_page = SelectField(
        "Results Per Page",
        choices=[("10", "10"), ("25", "25"), ("50", "50"), ("100", "100")],
        default="25",
        coerce=int,
    )

    timezone = SelectField(
        "Timezone",
        choices=[
            ("UTC", "UTC"),
            ("US/Eastern", "Eastern Time"),
            ("US/Central", "Central Time"),
            ("US/Mountain", "Mountain Time"),
            ("US/Pacific", "Pacific Time"),
            ("Europe/London", "London"),
            ("Europe/Paris", "Paris"),
            ("Asia/Tokyo", "Tokyo"),
            ("Asia/Shanghai", "Shanghai"),
        ],
        default="UTC",
    )

    notes = TextAreaField(
        "Notes",
        validators=[Optional(), Length(max=500)],
        render_kw={"rows": 3, "placeholder": "Personal notes or preferences..."},
    )

    submit = SubmitField("Save Preferences")


class ForgotPasswordForm(FlaskForm):
    """Forgot password form."""

    email = StringField(
        "Email",
        validators=[DataRequired(), Email()],
        render_kw={"placeholder": "Enter your email address", "autocomplete": "email"},
    )
    submit = SubmitField("Reset Password")


class ResetPasswordForm(FlaskForm):
    """Reset password form."""

    password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(min=8, message="Password must be at least 8 characters long"),
        ],
        render_kw={"placeholder": "Enter new password", "autocomplete": "new-password"},
    )
    password2 = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match"),
        ],
        render_kw={
            "placeholder": "Confirm new password",
            "autocomplete": "new-password",
        },
    )
    submit = SubmitField("Set New Password")


class TwoFactorSetupForm(FlaskForm):
    """Two-factor authentication setup form."""

    verification_code = StringField(
        "Verification Code",
        validators=[
            DataRequired(),
            Length(min=6, max=6),
            Regexp(r"^\d{6}$", message="Code must be 6 digits"),
        ],
        render_kw={"placeholder": "000000", "autocomplete": "one-time-code"},
    )
    backup_codes = BooleanField(
        "I have saved my backup codes", validators=[DataRequired()]
    )
    submit = SubmitField("Enable Two-Factor Authentication")


class TwoFactorForm(FlaskForm):
    """Two-factor authentication login form."""

    code = StringField(
        "Authentication Code",
        validators=[
            DataRequired(),
            Length(min=6, max=8),
            Regexp(r"^\d+$", message="Code must be numeric"),
        ],
        render_kw={"placeholder": "000000", "autocomplete": "one-time-code"},
    )
    remember_device = BooleanField("Trust this device for 30 days")
    submit = SubmitField("Verify")
