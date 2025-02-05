import os
import pymysql
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
from flask import Blueprint
from functools import wraps


bp = Blueprint('master', __name__, url_prefix='/master')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 세션에서 로그인한 사용자의 정보 확인
        user = session.get('user')
        if not user:  # 로그인이 안 되어 있으면
            
            return redirect(url_for('auth.login'))  # 로그인 페이지로 리디렉션
        if user != 'admin':  # 관리자가 아닌 경우
            
            return redirect(url_for('main.index'))  # 메인 페이지로 리디렉션
        return f(*args, **kwargs)
    return decorated_function



def get_db_connection():
    return pymysql.connect(
        host='localhost',
        port=3306,
        user='root',
        password='1234',
        db='daon_db',
        charset='utf8'
    )
# 장바구니 관리 #
# 장바구니 데이터 조회 함수 (auth 함수에서 사용)
def get_cart_data(page=1, per_page=10, search=None):
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        offset = (page - 1) * per_page

        # 검색 조건 추가
        search_query = ""
        search_params = []
        if search:
            search_query = "AND (u.erum LIKE %s OR u.username LIKE %s)"
            search_params = [f"%{search}%", f"%{search}%"]

        # 데이터 조회 쿼리
        query = f"""
            SELECT 
                ROW_NUMBER() OVER (ORDER BY c.cart_id desc) AS '순번',
                u.erum AS '이름',
                u.username AS '아이디',
                u.phone AS '휴대폰',
                c.pumname AS '물품 이름',
                c.gwon AS '수량',
                c.price AS '가격',
                (c.gwon * c.price) AS '합계',
                c.cart_id
            FROM cart c
            JOIN user u ON c.user_id = u.user_id
            WHERE 1=1 {search_query}
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, search_params + [per_page, offset])
        cart = cursor.fetchall()

        # 총 항목 수 계산
        count_query = f"""
            SELECT COUNT(*)
            FROM cart c
            JOIN user u ON c.user_id = u.user_id
            WHERE 1=1 {search_query}
        """
        cursor.execute(count_query, search_params)
        total_rows = cursor.fetchone()[0]
        total_pages = (total_rows + per_page - 1) // per_page

        return {
            "cart": cart,
            "total_pages": total_pages,
            "total_rows": total_rows,
            "page": page,
        }

    except Exception as e:
        connection.rollback()
        print(f"Error in get_cart_data: {e}")
        return {"cart": [], "total_pages": 0, "total_rows": 0, "page": page}

    finally:
        cursor.close()
        connection.close()
    
    return cart

# auth 라우트에서 user 데이터와 cart 데이터를 함께 가져오기
@bp.route('/auth', methods=['GET', 'POST'])
@admin_required
def auth():
    connection = get_db_connection()
    cursor = connection.cursor()
    
    try:
        # 검색어 가져오기
        search = request.args.get('search', '')
        
        # 페이지 정보 가져오기
        page = request.args.get('page', 1, type=int)  # 기본 페이지 번호는 1
        per_page = 10  # 한 페이지당 표시할 항목 수
        offset = (page - 1) * per_page  # 현재 페이지의 오프셋

        # 사용자 검색
        if search:
            cursor.execute("""
                SELECT * FROM user 
                WHERE username LIKE %s OR erum LIKE %s OR phone LIKE %s
                ORDER BY user_id DESC 
                LIMIT %s OFFSET %s
            """, (f'%{search}%', f'%{search}%', f'%{search}%', per_page, offset))
            user = cursor.fetchall()
            # 검색된 총 항목 수 계산
            cursor.execute("""
                SELECT COUNT(*) FROM user 
                WHERE username LIKE %s OR erum LIKE %s OR phone LIKE %s
            """, (f'%{search}%', f'%{search}%', f'%{search}%'))
        else:
            cursor.execute("SELECT * FROM user ORDER BY user_id DESC LIMIT %s OFFSET %s", (per_page, offset))
            user = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) FROM user")

        total_rows = cursor.fetchone()[0]
        total_pages = total_rows // per_page + (total_rows % per_page > 0)

        # 삭제 처리
        if request.method == 'POST':
            action = request.form.get('action')
            user_id = request.form.get('user_id')  # 삭제할 사용자 ID
            if action == 'delete' and user_id:
                # 삭제 쿼리 실행
                delete_query = """
                    DELETE FROM user WHERE user_id = %s;
                """
                cursor.execute(delete_query, (user_id,))
                connection.commit()  # 변경사항 커밋
                

                return redirect(url_for('master.auth', page=page, search=search))  # 삭제 후 현재 페이지로 리다이렉트

    except Exception as e:
        connection.rollback()
        print(f"Error: {e}")
        user = []
        total_pages = 0
        search = ''

    finally:
        cursor.close()
        connection.close()

    return render_template('master/master_auth.html', user=user, page=page, total_pages=total_pages, search=search)






    # 장바구니 데이터 가져오기
    cart = get_cart_data()

    # HTML 템플릿에 user, cart, 페이지 정보 전달
    return render_template('master/master_auth.html', user=user, cart=cart, page=page, total_pages=total_pages)

# 장바구니 관리 #
# cart 라우트는 장바구니 업데이트 및 삭제 기능 처리
@bp.route('/cart', methods=['GET', 'POST'])
@admin_required
def cart():
    connection = get_db_connection()
    cursor = connection.cursor()
    # 검색어와 페이지 값 가져오기
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    data = get_cart_data(page=page, search=search)
    
    try:
        page = request.args.get('page', 1, type=int)  # 기본 페이지 번호는 1
        per_page = 10  # 한 페이지당 표시할 항목 수
        offset = (page - 1) * per_page  # 현재 페이지의 오프셋
        


        if request.method == 'POST':
            action = request.form.get('action')
            cart_id = request.form.get('cart_id')  # cart_id를 받아옴
            

            # cart_id가 제대로 전달되지 않은 경우 오류 로그
            if not cart_id:
                print("Cart ID is missing!")  # 로그로 확인

            if action == 'update':
                # 수량 수정 처리
                new_quantity = request.form.get(f"gwon_{cart_id}")
                
                if new_quantity and new_quantity.isdigit() and int(new_quantity) > 0:
                    update_query = """
                        UPDATE cart
                        SET gwon = %s
                        WHERE cart_id = %s;
                    """
                    print(f"Executing query: {update_query} with params ({new_quantity}, {cart_id})")
                    cursor.execute(update_query, (new_quantity, cart_id))
                    connection.commit()  # 반드시 commit 호출
                    print(f"Updated cart {cart_id} with new quantity {new_quantity}")

                    # 업데이트된 데이터 확인
                    cursor.execute("SELECT * FROM cart WHERE cart_id = %s", (cart_id,))
                    updated_cart = cursor.fetchone()
                    print(f"Updated cart data: {updated_cart}")

            elif action == 'delete':
                # 장바구니 삭제 처리
                delete_query = """
                    DELETE FROM cart WHERE cart_id = %s;
                """
                cursor.execute(delete_query, (cart_id,))
                connection.commit()  # 변경사항 커밋
                print(f"Deleted cart {cart_id}")

            return redirect(url_for('master.cart', page=page, search=search))

        # 장바구니 데이터 조회
        cursor.execute("""
            SELECT 
                ROW_NUMBER() OVER (ORDER BY c.cart_id) AS '순번',
                u.erum AS '이름',
                u.username AS '아이디',
                u.phone AS '휴대폰',
                c.pumname AS '물품 이름',
                c.gwon AS '수량',
                c.price AS '가격',
                (c.gwon * c.price) AS '합계',
                c.cart_id
            FROM cart c
            JOIN user u ON c.user_id = u.user_id
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        cart = cursor.fetchall()

        # 총 항목 수 계산
        cursor.execute("SELECT COUNT(*) FROM cart")
        total_rows = cursor.fetchone()[0]
        total_pages = total_rows // per_page + (total_rows % per_page > 0)  # 총 페이지 수 계산

    except Exception as e:
        connection.rollback()  # 예외 발생 시 롤백
        print(f"Error: {e}")
        cart = []
        total_pages = 0

    finally:
        cursor.close()
        connection.close()

    return render_template('master/master_cart.html', cart=data['cart'],
        total_pages=data['total_pages'],
        page=data['page'],
        search=search)

# 상품관리 #

# 현재 경로가 /book이라는 가정
current_dir = os.path.abspath('book/.')  # 절대 경로로 설정

# 새로운 폴더 경로 설정
new_folder_path = os.path.join(current_dir, 'static', 'images')
UPLOAD_FOLDER = new_folder_path  # UPLOAD_FOLDER 정의


# 디렉토리가 존재하지 않으면 생성
if not os.path.exists(new_folder_path):
    os.makedirs(new_folder_path)
    print(f"'{new_folder_path}' 폴더가 생성되었습니다.")
else:
    print(f"'{new_folder_path}' 폴더는 이미 존재합니다.")

    # 허용되는 파일 확장자 설정
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Create Product: 등록 후 목록 페이지로 이동
@bp.route('/pum/create', methods=['GET', 'POST'])
@admin_required
def create_pum():
    connection = get_db_connection()
    cursor = connection.cursor()

    if request.method == 'POST':
        pumname = request.form['pumname']
        price = request.form['price']
        content = request.form['content']
        file = request.files['file']

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(new_folder_path, filename)  # 안전한 경로 생성
            file.save(file_path)  # 파일 저장

            # Insert into DB, image_url에 '/static/images/' 추가
            cursor.execute(
                "INSERT INTO products (pumname, price, content, image_url) VALUES (%s, %s, %s, %s)",
                (pumname, price, content, f'/static/images/{filename}'),  # 경로 포함하여 저장
            )
            connection.commit()
            #return redirect(url_for('master.master_pum')) # 등록 후 목록 페이지로 리다이렉트
            return redirect(url_for('master.pum')) # 등록 후 목록 페이지로 리다이렉트
    else:
        return render_template('master/master_upload.html', products=[])
    return render_template('master/master_upload.html', products=[])

@bp.route('/pum/update/<int:pum_id>', methods=['GET', 'POST'])
@admin_required
def update_pum(pum_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM products WHERE pum_id = %s", (pum_id,))
    product = cursor.fetchone()

    if not product:
        # 상품이 존재하지 않을 경우 에러 처리
        #return redirect(url_for('master.master_pum'))
        return redirect(url_for('master.pum'))

    if request.method == 'POST':
        pumname = request.form['pumname']
        price = request.form['price']
        content = request.form['content']
        file = request.files['file']
             # 이미지 처리
        image_url = product[4]  # 기존 이미지 URL 유지

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            image_url = f'/static/images/{filename}'  # 새 이미지 URL로 업데이트

        # 상품 정보 업데이트
        cursor.execute(
            "UPDATE products SET pumname = %s, price = %s, content = %s, image_url = %s WHERE pum_id = %s",
            (pumname, price, content, image_url, pum_id)
        )
        connection.commit()
        return redirect(url_for('master.pum'))

    # 수정 폼에 기존 데이터 전달
    return render_template('master/master_upload.html', product=product)

@bp.route('/pum/delete/<int:pum_id>', methods=['POST'])
@admin_required
def delete_pum(pum_id):
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("DELETE FROM products WHERE pum_id = %s", (pum_id,))
    connection.commit()
    # 삭제 후 목록 페이지로 리다이렉트하고 캐시를 무효화하기 위해 쿼리 파라미터 추가
    return redirect(url_for('master.pum', _external=True))

@bp.route('/pum', methods=['GET'])
@admin_required
def pum():
    connection = get_db_connection()
    cursor = connection.cursor()

    # 검색어 가져오기
    search = request.args.get('search', '').strip()
    
    try:
        # 총 상품 개수 계산 (검색 조건 포함)
        if search:
            count_query = """
                SELECT COUNT(*) FROM products
                WHERE pumname LIKE %s
            """
            cursor.execute(count_query, (f"%{search}%",))
        else:
            cursor.execute("SELECT COUNT(*) FROM products")
        total_products = cursor.fetchone()[0]
        
        # 페이지 번호 가져오기, 기본값은 1
        page = request.args.get('page', 1, type=int)
        per_page = 9  # 한 페이지에 표시할 상품 개수
        offset = (page - 1) * per_page  # 페이지 번호에 맞는 상품 목록 가져오기

        # 상품 목록 가져오기 (검색 조건 포함)
        if search:
            products_query = """
                SELECT * FROM products
                WHERE pumname LIKE %s
                ORDER BY pum_id DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(products_query, (f"%{search}%", per_page, offset))
        else:
            cursor.execute("SELECT * FROM products ORDER BY pum_id DESC LIMIT %s OFFSET %s", (per_page, offset))
        
        products = cursor.fetchall()

        # 총 페이지 수 계산
        total_pages = (total_products + per_page - 1) // per_page  # 올림 계산

    except Exception as e:
        connection.rollback()
        print(f"Error: {e}")
        products = []
        total_pages = 0
        page = 1
    finally:
        cursor.close()
        connection.close()
    
    return render_template('master/master_pum.html', products=products, page=page, total_pages=total_pages, search=search)
