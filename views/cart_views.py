import pymysql
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, current_app
from werkzeug.utils import secure_filename

bp = Blueprint('cart', __name__, url_prefix='/cart')

# 데이터베이스 연결 함수
def get_db_connection():
    return pymysql.connect(
        host='localhost',
        port=3306,
        user='root',
        password='1234',
        db='daon_db',
        charset='utf8'
    )

@bp.route('/list')
def cart_list():
    user_id = session.get('user_id')  # 로그인된 사용자 ID 확인
    if not user_id:
        flash("로그인이 필요합니다.", 'error')
        return redirect(url_for('auth.login'))

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # 장바구니 데이터 조회 (cart_id 기준 최신순 정렬)
        cursor.execute("""
            SELECT c.cart_id, c.gwon AS quantity, c.price, c.pumname, p.image_url
            FROM cart c
            JOIN products p ON c.pum_id = p.pum_id
            WHERE c.user_id = %s
            ORDER BY c.cart_id DESC  -- cart_id 기준으로 최신순 정렬
        """, (user_id,))
        cart_items = cursor.fetchall()

        # 총 금액 계산
        total_price = sum(item[1] * item[2] for item in cart_items)  # 수량 * 단가

        return render_template('cart.html', cart_items=cart_items, total_price=total_price)

    except Exception as e:
        flash(f"오류: {e}", 'error')
        return render_template('cart.html', cart_items=[], total_price=0)
    finally:
        cursor.close()
        db.close()

@bp.route('/update_quantity/<int:cart_id>', methods=['POST'])
def update_quantity(cart_id):
    action = request.form.get('action')  # increase 또는 decrease
    try:
        db = get_db_connection()
        cursor = db.cursor(pymysql.cursors.DictCursor)

        # 현재 수량 및 상품 ID 조회
        cursor.execute("SELECT gwon, pum_id FROM cart WHERE cart_id = %s", (cart_id,))
        cart_item = cursor.fetchone()
        if not cart_item:
            flash("장바구니 항목을 찾을 수 없습니다.", "error")
            return redirect(url_for('cart.cart_list'))

        current_quantity = cart_item['gwon']
        pum_id = cart_item['pum_id']

        # 상품의 단가 가져오기 (products 테이블에서 고정된 가격)
        cursor.execute("SELECT price FROM products WHERE pum_id = %s", (pum_id,))
        product = cursor.fetchone()
        if not product:
            flash("상품 정보를 찾을 수 없습니다.", "error")
            return redirect(url_for('cart.cart_list'))

        price = product['price']  # 상품의 단가

        # 수량 업데이트 로직
        if action == 'increase':
            new_quantity = current_quantity + 1
        elif action == 'decrease' and current_quantity > 1:
            new_quantity = current_quantity - 1
        else:
            new_quantity = current_quantity

        # 장바구니에는 수량만 업데이트 (단가는 고정되어 있음)
        cursor.execute("""
            UPDATE cart 
            SET gwon = %s
            WHERE cart_id = %s
        """, (new_quantity, cart_id))

        db.commit()
        flash("수량이 업데이트되었습니다.", "success")
        return redirect(url_for('cart.cart_list'))

    except Exception as e:
        db.rollback()
        flash(f"오류 발생: {e}", "error")
        return redirect(url_for('cart.cart_list'))

    finally:
        db.close()


@bp.route('/delete', methods=['POST'])
def delete_selected():
    user_id = session.get('user_id')  # 로그인 여부 확인
    if not user_id:
        flash("로그인이 필요합니다.", 'error')
        return redirect(url_for('auth.login'))

    # 선택된 상품의 cart_id 리스트 가져오기
    selected_items = request.form.getlist('selected_items')

    if not selected_items:
        flash("삭제할 상품을 선택해주세요.", 'warning')
        return redirect(url_for('cart.cart_list'))

    try:
        db = get_db_connection()
        cursor = db.cursor()

        # 선택된 상품 삭제 쿼리
        query = "DELETE FROM cart WHERE user_id = %s AND cart_id IN ({})".format(
            ','.join(['%s'] * len(selected_items))
        )
        cursor.execute(query, [user_id] + selected_items)

        db.commit()
        flash("선택한 상품이 삭제되었습니다.", 'success')

    except Exception as e:
        db.rollback()
        flash(f"삭제 중 오류가 발생했습니다: {e}", 'error')
    finally:
        cursor.close()
        db.close()

    return redirect(url_for('cart.cart_list'))
        
@bp.route('/create/<int:pum_id>', methods=['POST'])
def add_to_cart(pum_id):
    user_id = session.get('user_id')  # 세션에서 user_id 확인
    if not user_id:
        flash("로그인이 필요합니다.", 'error')
        return redirect(url_for('auth.login'))  # 로그인 페이지로 리다이렉트

    # 아래는 로그인된 상태에서만 실행
    quantity = int(request.form.get('quantity', 1))
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT pumname, price FROM products WHERE pum_id = %s", (pum_id,))
        product = cursor.fetchone()

        if not product:
            flash("상품 정보를 찾을 수 없습니다.", 'error')
            return redirect(url_for('pum.pum_detail', pum_id=pum_id))

        pumname, price = product

        # 장바구니에 상품 추가 로직
        cursor.execute("""
            INSERT INTO cart (user_id, pum_id, gwon, price, username, pumname)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, pum_id, quantity, price, session['user'], pumname))

        db.commit()
        flash("장바구니에 상품이 추가되었습니다.", 'success')
        return redirect(url_for('cart.cart_list'))

    except Exception as e:
        db.rollback()
        flash(f"오류: {e}", 'error')
        return redirect(url_for('pum.pum_detail', pum_id=pum_id))
    finally:
        db.close()
