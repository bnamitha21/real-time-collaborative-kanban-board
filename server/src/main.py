from server.src.app import create_app
from server.src.config.env import env
from server.src.realtime.socket import socketio

app = create_app()

if __name__ == "__main__":
    print(f"Starting server on port {env.PORT}...")
    socketio.run(
        app,
        host="0.0.0.0",
        port=env.PORT,
        debug=env.FLASK_ENV == "development",
        allow_unsafe_werkzeug=True,
    )
