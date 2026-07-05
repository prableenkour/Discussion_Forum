from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo
from flask_wtf.file import FileField, FileAllowed

# ---------------- SIGNUP FORM ----------------
class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(3, 50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(6, 128)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')


# ---------------- LOGIN FORM ----------------
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


# ---------------- THREAD FORM ----------------
class ThreadForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(3, 200)])
    content = TextAreaField('Content', validators=[DataRequired(), Length(5, 2000)])
    submit = SubmitField('Post Thread')
class CommentForm(FlaskForm):
    content = TextAreaField('Add a Comment', validators=[DataRequired(), Length(1, 500)])
    submit = SubmitField('Post Comment')


class EditProfileForm(FlaskForm):
    bio = TextAreaField('Bio', validators=[Length(max=300)])
    avatar = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')])
    submit = SubmitField('Save Changes')
