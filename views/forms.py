from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo

class SignupForm(FlaskForm):
    username = StringField('ID', validators=[DataRequired()])
    password1 = PasswordField('비밀번호', validators=[DataRequired()])
    password2 = PasswordField('비밀번호 확인', validators=[DataRequired(), EqualTo('password1', '비밀번호가 일치하지 않습니다.')])
    erum = StringField('이름', validators=[DataRequired()])
    email = StringField('이메일', validators=[DataRequired(), Email()])
    phone = StringField('핸드폰 번호', validators=[DataRequired()])
    submit = SubmitField('가입하기') 