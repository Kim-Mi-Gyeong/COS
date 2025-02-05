import pymysql
from flask import Flask, Blueprint, render_template, request, redirect, url_for, flash

# Flask 애플리케이션 초기화
app = Flask(__name__)
app.secret_key = 'mini'  # 비밀 키 설정

# 데이터베이스 연결 설정
def get_db_connection():
    return pymysql.connect(
        host='localhost',
        port=3306,
        user='root',
        password='1234',
        db='daon_db',
        charset='utf8'
    )

# 블루프린트 설정
bp = Blueprint('pum', __name__, url_prefix='/pum')

@bp.route('/detail/<int:pum_id>', methods=['GET'])
def pum_detail(pum_id):
    pum = None
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM products WHERE pum_id = %s", (pum_id,))
        columns = [col[0] for col in cursor.description]  # 컬럼 이름 가져오기
        result = cursor.fetchone()  # 하나의 상품 데이터만 가져옴
        if result is not None:
            pum = dict(zip(columns, result))  # 튜플을 딕셔너리로 변환
        if pum is None:
            flash('상품을 찾을 수 없습니다.', 'error')
            return redirect(url_for('pum.pum_list'))  # 상품 목록으로 리다이렉트
    except Exception as e:
        flash(f'상품 조회 중 오류가 발생했습니다: {e}', 'error')
        return redirect(url_for('pum.pum_list'))
    finally:
        cursor.close() if cursor else None
        db.close() if db else None

    return render_template('pum_detail.html', pum=pum)  # 상세 페이지로 전달

@bp.route('/list', methods=['GET'])
def pum_list():
    try:
        db = get_db_connection()
        cursor = db.cursor()
        
        # 검색어 가져오기
        search = request.args.get('search', '')
        
        # 페이지 번호 가져오기, 기본값은 1
        page = request.args.get('page', 1, type=int)
        per_page = 9  # 페이지당 항목 수
        offset = (page - 1) * per_page

        # 검색 조건에 따른 쿼리 생성
        if search:
            # 전체 검색 결과 수 가져오기
            cursor.execute("SELECT COUNT(*) FROM products WHERE pumname LIKE %s", (f'%{search}%',))
            total_products = cursor.fetchone()[0]
            
           # 검색된 상품 목록 가져오기, 최신 상품이 먼저 오도록 정렬
            cursor.execute("SELECT * FROM products WHERE pumname LIKE %s ORDER BY pum_id DESC LIMIT %s OFFSET %s", 
                         (f'%{search}%', per_page, offset))
        else:
            # 전체 상품 수 가져오기
            cursor.execute("SELECT COUNT(*) FROM products")
            total_products = cursor.fetchone()[0]
            
            # 전체 상품 목록 가져오기, 최신 상품이 먼저 오도록 정렬
            cursor.execute("SELECT * FROM products ORDER BY pum_id DESC LIMIT %s OFFSET %s", (per_page, offset))
        
        products = cursor.fetchall()

        # 총 페이지 수 계산
        total_pages = (total_products + per_page - 1) // per_page  # 올림 계산
    except Exception as e:
        flash(f'상품 목록 조회 중 오류가 발생했습니다: {e}', 'error')
        products = []
        total_pages = 1
        page = 1
        search = ''
        total_products = 0  # 에러 발생 시 검색 결과 0개로 설정
    finally:
        cursor.close() if cursor else None
        db.close() if db else None

    return render_template('pum_list.html', 
                         products=products, 
                         page=page, 
                         total_pages=total_pages,
                         search=search,
                         total_products=total_products)

app.register_blueprint(bp)

if __name__ == '__main__':
    app.run(debug=True)
