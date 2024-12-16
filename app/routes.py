from flask import Blueprint, render_template, request, jsonify
from flask_socketio import emit
import cv2
import base64
import time
from threading import Thread, Lock
from . import socketio
from flask_socketio import SocketIO
from pytapo import Tapo
from flask import request
import json
import os


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

previous_frame = None
motion_thread = None

recording = False  # Flag for recording state
video_writer = None  # Global VideoWriter object
output_dir = "recordings"  # Directory for saving recordings
recording_lock = Lock()  # Lock to ensure thread-safe recording control

last_motion_time = time.time()  # Track time since the last motion
MOTION_TIMEOUT = 5  # 5 seconds timeout for no motion

# Ensure recordings directory exists
os.makedirs(output_dir, exist_ok=True)

def start_recording_thread(frame_size, fps=15):
    """Starts the recording in a separate thread."""
    global recording, recording_thread
    if not recording:
        recording = True
        recording_thread = Thread(target=record_video, args=(frame_size, fps))
        recording_thread.daemon = True
        recording_thread.start()
        print("Recording thread started")

def stop_recording():
    """Stops the recording thread."""
    global recording, video_writer
    with recording_lock:
        if recording:
            recording = False
            if video_writer:
                video_writer.release()
                video_writer = None
            print("Recording stopped")
            socketio.emit('recording_status', {'status': 'stopped'})  # Notify the client


def record_video(frame_size, fps):
    """Recording function to write video frames to MP4."""
    global recording, video_writer
    filename = os.path.join(output_dir, f"recording_{time.strftime('%Y%m%d_%H%M%S')}.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec for MP4

    with recording_lock:  # Ensure thread safety when initializing
        video_writer = cv2.VideoWriter(filename, fourcc, fps, frame_size)

    if not video_writer.isOpened():  # Check if VideoWriter initialized successfully
        print(f"Error: Unable to open VideoWriter for file: {filename}")
        with recording_lock:
            video_writer = None
            recording = False
        return

    print(f"Recording to file: {filename}")
    socketio.emit('recording_status', {'status': 'started', 'filename': filename})  # Notify the client

    cap = cv2.VideoCapture(camera_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

    while recording:
        success, frame = cap.read()
        if not success:
            print("Failed to capture frame during recording")
            continue

        # Resize frame to ensure size matches VideoWriter configuration
        frame_resized = cv2.resize(frame, frame_size)

        with recording_lock:  # Thread-safe access to video_writer
            if video_writer:
                video_writer.write(frame_resized)  # Write frame

        time.sleep(0.033)  # Limit to ~30 FPS

    cap.release()
    with recording_lock:  # Safely release video_writer
        if video_writer:
            video_writer.release()
            video_writer = None
    print("Recording thread finished")


def detect_motion(frame):
    """
    Funkcja wykrywa ruch, porównując bieżącą klatkę z poprzednią.
    Zwraca True, jeśli wykryto ruch.
    """
    global previous_frame

    # Konwersja klatki na skalę szarości i zmniejszenie szumu
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (31, 31), 0)  # Zwiększ rozmycie (21 -> 31)

    if previous_frame is None:
        previous_frame = gray
        return False  # Brak poprzedniej klatki, nie można wykryć ruchu

    # Obliczenie różnicy między klatkami
    delta_frame = cv2.absdiff(previous_frame, gray)
    threshold_frame = cv2.threshold(delta_frame, 35, 255, cv2.THRESH_BINARY)[1]  # Zwiększ próg (25 -> 35)

    # Wypełnienie obszarów progowych
    threshold_frame = cv2.dilate(threshold_frame, None, iterations=2)

    # Znalezienie konturów (obszarów zmiany)
    contours, _ = cv2.findContours(threshold_frame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = False
    for contour in contours:
        # Ignoruj małe obszary, aby uniknąć szumów
        if cv2.contourArea(contour) < 1500:  # Zwiększ minimalny obszar (500 -> 1500)
            continue
        motion_detected = True
        
        if motion_detected:
            last_motion_time = time.time()  # Update the last motion time

        # Motion timeout logic
        if time.time() - last_motion_time > MOTION_TIMEOUT:
            motion_detected = False
        
        break

    # Zapisz bieżącą klatkę jako poprzednią dla następnego kroku
    previous_frame = gray

    socketio.emit('motion_status', {'motion': motion_detected})  # Notify client
    return motion_detected

def capture_frames():
    
    cap = cv2.VideoCapture(camera_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2) 
    
    
    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    while True:
        try:
            success, frame = cap.read()

            if not success:
                print("Warning: Failed to capture frame, retrying...")
                # Jeśli nie udało się odczytać klatki, zamykamy połączenie i próbujemy ponownie
                cap.release()
                print("Failed to read frame. Skipping...")
                time.sleep(0.1)
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

           # Start motion detection in a separate thread if it hasn't already started
            global motion_thread
            if motion_thread is None or not motion_thread.is_alive():
                motion_thread = Thread(target=motion_detection_task, args=(frame,))
                motion_thread.start()
                
            # Czekanie przed wysłaniem kolejnej klatki (30 FPS)
            socketio.sleep(0.033)  # ~30 FPS
        except Exception as e:
            print(f"Error while reading frame: {e}")
            time.sleep(0.01)  # Avoid CPU overload
            continue
    
def motion_detection_task(frame):
    motion_detected = detect_motion(frame)
    if motion_detected:
        socketio.emit('motion_detected', {'motion': True})
    
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
    
    
# WebSocket Event Handlers for Manual Recording
@socketio.on('start_recording')
def handle_start_recording():
    """Handle start recording WebSocket event."""
    print("Start recording request received")
    start_recording_thread(frame_size=(640, 480))  # Frame size matches streaming resolution

@socketio.on('stop_recording')
def handle_stop_recording():
    """Handle stop recording WebSocket event."""
    print("Stop recording request received")
    stop_recording()
    
@bp.route('/')
def index():
    return render_template('index.html')

def start_video_stream():
    thread = Thread(target=capture_frames)
    thread.daemon = True
    thread.start()
