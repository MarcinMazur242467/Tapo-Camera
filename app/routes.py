from flask import Blueprint, render_template, request, jsonify
from flask_socketio import emit
import cv2
import base64
import time
from threading import Thread
from . import socketio
from flask_socketio import SocketIO
from pytapo import Tapo
from flask import request
import json

def load_config(config_file='config.json'):
    with open(config_file, 'r') as file:
        return json.load(file)

config = load_config()

camera_ip = config['host']
camera_user = config['user']
camera_password = config['password']
camera_url = config['rtsp_url']

camera = Tapo(camera_ip, camera_user, camera_password)

socket = SocketIO()
bp = Blueprint('main', __name__)

def capture_frames():
    cap = cv2.VideoCapture(camera_url)

    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    while True:
        success, frame = cap.read()

        if not success:
            print("Warning: Failed to capture frame, retrying...")
            # Jeśli nie udało się odczytać klatki, zamykamy połączenie i próbujemy ponownie
            cap.release()
            time.sleep(1)
            cap = cv2.VideoCapture(camera_url)  # Próba ponownego połączenia
            if not cap.isOpened():
                print("Error: Could not reconnect to the camera stream.")
                break
            continue


        # Zmniejszenie rozdzielczości obrazu, aby zmniejszyć obciążenie
        frame = cv2.resize(frame, (640, 480))

        _, buffer = cv2.imencode('.jpg', frame)
        if not _:
            print("Failed to encode frame.")
            continue
        frame_b64 = base64.b64encode(buffer).decode('utf-8')
            
        
        # Wysyłanie klatki do klienta przez WebSocket
        #socketio.emit('video_frame', {'frame': frame_b64}, namespace='/')
        socketio.emit('video_frame', {'frame': frame_b64})


        # Czekanie przed wysłaniem kolejnej klatki (30 FPS)
        socketio.sleep(0.033)  # ~30 FPS
    
@bp.route('/move', methods=['POST'])
def move_camera():
    print("Headers:", request.headers)  # Logowanie nagłówków żądania
    print("Data received:", request.data)  # Logowanie surowych danych

    try:
        data = request.get_json()
        print("Parsed JSON:", data)  # Logowanie sparsowanego JSONa
        
        if not data or 'direction' not in data:
            return jsonify({"error": "Missing 'direction' in request"}), 400

        direction = data.get('direction')

        if direction == 'left':
            camera.moveMotor(-10, 0)  # Przesunięcie w lewo (x=-10, y=0)
        elif direction == 'right':
            camera.moveMotor(10, 0)   # Przesunięcie w prawo (x=10, y=0)
        elif direction == 'up':
            camera.moveMotor(0, 10)   # Przesunięcie w górę (x=0, y=10)
        elif direction == 'down':
            camera.moveMotor(0, -10)  # Przesunięcie w dół (x=0, y=-10)
        else:
            return jsonify({"error": "Invalid direction"}), 400

        return jsonify({"status": "success", "direction": direction})
    
    except Exception as e:
        print(f"Error in move_camera: {e}")  # Logowanie błędu na serwerze
        return jsonify({"error": "Internal Server Error", "message": str(e)}), 500
    
@bp.route('/')
def index():
    return render_template('index.html')

def start_video_stream():
    thread = Thread(target=capture_frames)
    thread.daemon = True
    thread.start()
