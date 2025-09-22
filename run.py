import os
from app import create_app, socketio  # 'app' is your package folder with __init__.py

# Create the Flask app
app = create_app()

# Get port from environment (Render sets PORT automatically)
PORT = int(os.environ.get("PORT", 5000))

# Get host from environment (default to '0.0.0.0' for external access)
HOST = os.environ.get("HOST", "0.0.0.0")

# Debug mode (Render sets RENDER_DEBUG or use FLASK_DEBUG in .env)
DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

if __name__ == "__main__":
    # Run SocketIO server (supports real-time features)
    socketio.run(
        app,
        debug=DEBUG,
        host=HOST,
        port=PORT
    )
