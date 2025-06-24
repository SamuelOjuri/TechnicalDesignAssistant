from app import create_app

app, socketio = create_app()

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5001, host='0.0.0.0')
