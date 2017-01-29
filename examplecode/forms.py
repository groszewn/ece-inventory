from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, IntegerField, SelectField, PasswordField, SelectMultipleField, DateTimeField, TextAreaField
from wtforms.validators import DataRequired, Length, Required, EqualTo


class GroupNewFormFactory:
    @staticmethod
    def form(assignments):
        class F(FlaskForm):
            name = StringField(default='')
            assign_options = [("none", "Study Group")]
            assign_options.extend([(str(assign.assignment_id), assign.description) for assign in assignments])
            assign = SelectField('Assignment', choices=assign_options)
        return F()

class UserLoginFormFactory:
    @staticmethod
    def form():
        class F(FlaskForm):
            email = StringField(default='')
            password = PasswordField(default='')
        return F()

class UserRegisterFormFactory:
    @staticmethod
    def form():
        class F(FlaskForm):
            name = StringField(default='')
            password = PasswordField('Password', [Required(), Length(8, 256), EqualTo('confirm_pw', message="Passwords don't match")])
            confirm_pw = PasswordField('Confirm Password', [Required()])
            phone = StringField('Phone Number')
            email = StringField('Email', [Required()])
            user_type = SelectField('User Type', choices=[('stu', 'Student'), ('pro', 'Professor')])
        return F()

class ClassRegisterFormFactory:
    @staticmethod
    def form():
        class F(FlaskForm):
            section_code = StringField(default='')
        return F()

class UniversityCreateFormFactory:
    @staticmethod
    def form():
        class F(FlaskForm):
            u_loc = StringField('New University Location')
            u_name = StringField('New University Name')
        return F()

class ClassCreateFormFactory:
    @staticmethod
    def form(universities):
        class F(FlaskForm):
            u_options = [(u.university_name, u.university_name) for u in universities]
            university = SelectField('University', choices=u_options)
            u_loc = StringField('New University Location')
            u_name = StringField('New University Name')
            course_code = StringField('Course Code')
            course_semester = StringField('Course Semester')
            course_pre = StringField('Course Prefix')
            course_name = StringField('Course Name')
            num_sect = IntegerField('Number Of Sections')
        return F()

class PostNewFormFactory:
    @staticmethod
    def form():
        class F(FlaskForm):
            message = TextAreaField('Message')
            options = [('need_team','looking for team'),('need_member','looking for member')]
            looking_for = SelectField('Looking For', choices=options)
        return F()

class EditProfileFormFactory:
    @staticmethod
    def form(user_info, isStudent):
        class F(FlaskForm):
            name = StringField(default=user_info.name)
            phone = StringField(default=user_info.phone)
            email = StringField(default=user_info.email)
            if isStudent:
                first_major = StringField(default=user_info.first_major)
                second_major = StringField(default=user_info.second_major)
                grad_year = StringField(default=user_info.grad_year)
        return F()

class AssignmentNewFormFactory:
    @staticmethod
    def form(sections):
        class F(FlaskForm):
            @staticmethod
            def section_field_name(id):
                return 'section_{}'.format(id)
            def section_fields(self):
                for s in sections:
                    yield s.section_id, str(s.section_number)+" "+s.course_code, getattr(self, F.section_field_name(s.section_id))
            def get_sections(self):
                for s_id, s_name, s_field in self.section_fields():
                    if s_field.data:
                        yield s_id
            date_assigned = StringField()
            date_due = StringField()
            description = TextAreaField()
        for s in sections:
            field_name = F.section_field_name(s.section_id)
            default = None
            setattr(F, field_name, BooleanField(default=default))
        return F()

class ResponseFormFactory:
    @staticmethod
    def form():
        class F(FlaskForm):
            message = TextAreaField()
        return F()
