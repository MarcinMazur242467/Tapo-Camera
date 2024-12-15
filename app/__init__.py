from flask import Flask
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")


def create_app():
    # Tworzymy aplikację Flask
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'secret!'

    # Rejestrujemy blueprint z trasami
    from . import routes
    app.register_blueprint(routes.bp)

    # Inicjalizujemy SocketIO
    socketio.init_app(app)

    # Rozpoczynamy strumieniowanie wideo
    routes.start_video_stream()

    return app, socketio

# Tworzymy instancję aplikacji i SocketIO
app, socketio = create_app()
