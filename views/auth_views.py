from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, g, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
import pymysql
from pymysql.cursors import DictCursor
from .forms import SignupForm  # forms.py에서 SignupForm 가져오기
from datetime import datetime  # 추가

bp = Blueprint('auth', __name__, url_prefix='/auth')

from datetime import timedelta


def get_db_connection():
    import pymysql
    return pymysql.connect(
        host='localhost',
        port=3306,
        user='root',
        password='1234',
        db='daon_db',
        charset='utf8',
        cursorclass=pymysql.cursors.DictCursor
    )

bp = Blueprint('auth', __name__, url_prefix='/auth')

# 세션 설정
@bp.before_request
def before_request():
    session.permanent = True
    current_app.permanent_session_lifetime = timedelta(days=1)  # 세션 유효기간 1일로 설정

db = pymysql.connect(
    host='localhost',
    port=3306,
    user='root',
    passwd='1234',
    db='daon_db',
    charset='utf8',
    cursorclass=DictCursor
)

cursor = db.cursor()

@bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    next_page = request.args.get('next')  # 'next' 파라미터 가져오기

    # GET 요청일 때 이전 페이지 URL을 세션에 저장
    if request.method == 'GET':
        if next_page:
            session['next_url'] = next_page  # 'next' 파라미터가 있으면 세션에 저장
        elif request.referrer:  # 없을 경우 이전 페이지(referrer) 활용
            session['next_url'] = request.referrer

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        try:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM user WHERE username = %s", (username,))
            user = cursor.fetchone()

            if not user:
                error = "존재하지 않는 사용자입니다."
            elif not check_password_hash(user['password1'], password):
                error = "비밀번호가 일치하지 않습니다."
            else:
                # 세션에 사용자 정보 저장
                session['user_id'] = user['user_id']
                session['user'] = user['username']
                session.permanent = True

                # admin 사용자일 경우 master/cart ���지로 이동
                if user['username'] == 'admin':
                    return """
                        <script>
                            alert('로그인 성공!');
                            window.location.href = 'http://localhost:5000/master/cart';
                        </script>
                    """

                # 일반 사용자는 루트(/) 페이지로 이동
                return """
                    <script>
                        alert('로그인 성공!');
                        window.location.href = '/';
                    </script>
                """

        except Exception as e:
            flash(f"오류: {e}", 'error')
        finally:
            cursor.close()
            db.close()

    return render_template('auth/login.html', error=error)



@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        phone = form.phone.data
        password = form.password1.data
        erum = form.erum.data

        # 중복 확인
        cursor.execute("SELECT * FROM user WHERE username = %s OR email = %s OR phone = %s", (username, email, phone))
        existing_user = cursor.fetchone()

        if existing_user:
            if existing_user['username'] == username:
                form.username.errors.append('이미 사용 중인 ID입니다.')
            if existing_user['email'] == email:
                form.email.errors.append('이미 사용 중인 이메일입니다.')
            if existing_user['phone'] == phone:
                form.phone.errors.append('이미 사용 중인 휴대폰 번호입니다.')
            return render_template('auth/signup.html', form=form)

        # 비밀번호 해시화
        password_hash = generate_password_hash(password)
        
        # 사용자 데이터 저장
        try:
            cursor.execute(
                "INSERT INTO user (username, password1, password2, email, phone, erum, create_date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (username, password_hash, password_hash, email, phone, erum, datetime.now())
            )
            db.commit()
            return """
                <script>
                    alert('회원가입이 되었습니다');
                    window.location.href = '{}';
                </script>
            """.format(url_for('auth.login'))
        except Exception as e:
            db.rollback()
            flash('회원가입 중 오류가 발생했습니다.', 'error')
            return render_template('auth/signup.html', form=form)

    return render_template('auth/signup.html', form=form)



@bp.route('/myinfo', methods=['GET', 'POST'])
def myinfo():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # 현재 수정 중인 사용자 확인
        target_username = session.get('edit_username') if session.get('user') == 'admin' else session.get('user')
        
        cursor.execute("SELECT * FROM user WHERE username = %s", (target_username,))
        user = cursor.fetchone()

        if not user:
            flash('사용자 정보를 찾을 수 없습니다.')
            return redirect(url_for('main.index'))

        mode = request.args.get('mode', 'info')

        if request.method == 'POST':
            mode = request.form.get('mode', 'info')

            if mode == 'edit':
                # 정보 수정 처리
                erum = request.form.get('erum')
                email = request.form.get('email')
                phone = request.form.get('phone')

                # 이메일과 전화번호 중복 체크 (현재 사용자 제외)
                cursor.execute("""
                    SELECT * FROM user 
                    WHERE (email = %s OR phone = %s) AND username != %s
                """, (email, phone, target_username))
                existing = cursor.fetchone()

                if existing:
                    if existing['email'] == email:
                        flash('이미 사용 중인 이메일입니다.')
                        return render_template('auth/myinfo.html', user=user, mode='edit')
                    if existing['phone'] == phone:
                        flash('이미 사용 중인 전화번호입니다.')
                        return render_template('auth/myinfo.html', user=user, mode='edit')

                # 정보 업데이트
                cursor.execute("""
                    UPDATE user 
                    SET erum = %s, email = %s, phone = %s 
                    WHERE username = %s
                """, (erum, email, phone, target_username))
                connection.commit()

                if session.get('user') == 'admin':
                    # 관리자가 수정한 경우 회원관리 페이지로
                    session.pop('edit_username', None)  # 임시 저장된 username 제거
                    return redirect(url_for('master.auth'))
                else:
                    # 일반 사용자는 정보 보기 모드로
                    return redirect(url_for('auth.myinfo', mode='info'))

            elif mode == 'password':
                # 비���번호 변경 처리
                password1 = request.form.get('password1')
                password2 = request.form.get('password2')

                if password1 != password2:
                    flash('비밀번호가 일치하지 않습니다.')
                    return render_template('auth/myinfo.html', user=user, mode='password')

                # 비밀번호 해시화 및 업데이트
                password_hash = generate_password_hash(password1)
                cursor.execute("""
                    UPDATE user 
                    SET password1 = %s, password2 = %s 
                    WHERE username = %s
                """, (password_hash, password_hash, target_username))
                connection.commit()

                return redirect(url_for('auth.myinfo', mode='info'))

            elif mode == 'delete':
                # 회원 탈퇴 처리
                cursor.execute("DELETE FROM user WHERE username = %s", (target_username,))
                connection.commit()
                session.clear()
                return redirect(url_for('main.index'))

        return render_template('auth/myinfo.html', user=user, mode=mode)

    except Exception as e:
        print(f"Error in myinfo: {e}")
        connection.rollback()
        flash('오류가 발생했습니다.')
        return redirect(url_for('main.index'))

    finally:
        cursor.close()
        connection.close()


@bp.route('/logout/')
def logout():
    # 특정 세션 키만 제거하는 대신 전체 세션을 클리어
    session.clear()
    return redirect(url_for('main.index'))


@bp.route('/check_duplicate', methods=['POST'])
def check_duplicate():
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    current_username = data.get('current_username')  # 현재 사용자의 username

    # 필드 이름을 데이터베이스 컬럼 이름과 매핑
    field_map = {
        'username': 'username',
        'email': 'email',
        'phone': 'phone'
    }

    db_field = field_map.get(field)
    if not db_field:
        return jsonify({'error': 'Invalid field'}), 400

    # 중복 체크 쿼리 실행 (현재 사용자 제외)
    query = f"SELECT COUNT(*) as count FROM user WHERE {db_field} = %s"
    params = [value]
    
    if current_username:
        query += " AND username != %s"
        params.append(current_username)

    cursor.execute(query, params)
    result = cursor.fetchone()
    
    return jsonify({'duplicate': result['count'] > 0})


@bp.route('/myinfo/<string:username>', methods=['GET'])
def admin_edit_user(username):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        # 사용자 정보 조회
        cursor.execute("SELECT * FROM user WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if not user:
            flash('사용자를 찾을 수 없습니다.')
            return redirect(url_for('master.auth'))

        # 세션에 임시로 수정할 사용자의 username 저장
        session['edit_username'] = username
        
        return render_template('auth/myinfo.html', user=user, mode='edit')

    except Exception as e:
        print(f"Error in admin_edit_user: {e}")
        flash('사용자 정보를 불러오는 중 오류가 발생했습니다.')
        return redirect(url_for('master.auth'))
    finally:
        cursor.close()
        connection.close()

