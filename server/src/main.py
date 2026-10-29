from server.src.app import create_app
from server.src.config.env import env

app = create_app()

if __name__ == "__main__":
    print(f"Starting server on port {env.PORT}...")
    app.run(host="0.0.0.0", port=env.PORT, debug=env.FLASK_ENV == "development")
