from flask import Flask

def create_app():
    app = Flask(__name__)

    app.secret_key =  'mini'
    from .views import main_views, cart_views, pum_views, auth_views, master_views

   # 블루프린트
    app.register_blueprint(main_views.bp)
    app.register_blueprint(cart_views.bp)
    app.register_blueprint(pum_views.bp)
    app.register_blueprint(auth_views.bp)
    app.register_blueprint(master_views.bp)

    return app