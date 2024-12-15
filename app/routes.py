from flask import Blueprint, render_template
from flask_socketio import emit
import cv2
import base64
import time
from threading import Thread
from . import socketio
from flask_socketio import SocketIO

socket = SocketIO()

bp = Blueprint('main', __name__)
camera_url = "rtsp://tapo1234:tapo1234@192.168.18.13/stream1"

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
    


@bp.route('/')
def index():
    return render_template('index.html')

def start_video_stream():
    thread = Thread(target=capture_frames)
    thread.daemon = True
    thread.start()
