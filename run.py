from app import create_app, socketio  # make sure 'app' is the folder name where __init__.py lives

# Create the Flask app
app = create_app()

if __name__ == "__main__":
    # Run with SocketIO for real-time features
    socketio.run(
        app,
        debug=True,          # turn off in production
        host="0.0.0.0",      # makes app accessible on your network
        port=5000
    )
