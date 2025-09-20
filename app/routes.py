from flask import Blueprint, render_template, request, jsonify
from flask_socketio import emit
import cv2
import moviepy as mpy
import base64
import time
from threading import Thread, Lock
from queue import Queue, Empty
from . import socketio
from .recordings_routes import recordings_bp
from flask_socketio import SocketIO
from pytapo import Tapo
from flask import request
import json
import os


def load_config(config_file='config.json'):
    try:
        with open(config_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        # Return empty config instead of raising so app can show setup screen
        print("config.json not found. Setup screen will be shown to configure camera.")
        return {}


from flask import current_app
config = load_config()


# Helper to check config validity
def is_config_valid(cfg: dict) -> bool:
    required = ['host', 'user', 'password', 'rtsp_url']
    return all(k in cfg and cfg[k] for k in required)


# Camera variables will be initialized lazily if config is valid
camera_ip = config.get('host')
camera_user = config.get('user')
camera_password = config.get('password')
camera_url = config.get('rtsp_url')

camera = None
camera_connected = False
last_connection_reason = None
last_connection_hint = None
if is_config_valid(config) and Tapo is not None:
    try:
        camera = Tapo(camera_ip, camera_user, camera_password)
    except Exception as e:
        print(f"Warning: could not initialize Tapo camera: {e}")


def check_camera_connection(timeout=5):
    """Check overall camera connectivity.
    Returns (connected: bool, reason: str).
    - Verifies config is present
    - Verifies Tapo API credentials (if Tapo available)
    - Verifies RTSP stream can be opened
    """
    global camera, camera_connected, camera_ip, camera_user, camera_password, camera_url

    # Check config
    if not is_config_valid(config):
        return False, "config_invalid"

    # Check RTSP stream first (fast fail if RTSP is invalid)
    try:
        cap = cv2.VideoCapture(camera_url)
        start = time.time()
        # Give a short window to open
        while time.time() - start < timeout:
            if cap.isOpened():
                # Try reading a frame to ensure the stream is delivering data
                success, frame = cap.read()
                cap.release()
                if success and frame is not None and frame.size > 0:
                    # RTSP is delivering frames; proceed to Tapo auth check
                    rtsp_ok = True
                    break
                else:
                    return False, "rtsp_no_frame"
            time.sleep(0.2)
        else:
            cap.release()
            return False, "rtsp_unreachable"
    except Exception as e:
        print(f"RTSP check error: {e}")
        return False, "rtsp_error"

    # At this point RTSP is OK. Now check Tapo API credentials (if pytapo available)
    if Tapo is None:
        # If pytapo is not installed, treat RTSP-only as sufficient connectivity
        return False, "ok_rtsp_only"
    else:
        try:
            camera = Tapo(camera_ip, camera_user, camera_password)
            # If we reach here, both RTSP and Tapo auth are OK
            camera_connected = True
            return True, "ok"
        except Exception as e:
            print(f"Tapo auth failed after RTSP OK: {e}")
            return False, "tapo_auth_failed"

socket = SocketIO()
bp = Blueprint('main', __name__)

previous_frame = None
motion_thread = None


recording = False  # Flag for recording state
video_writer = None  # (Unused with moviepy, kept for compatibility)
recorded_frames = []  # List to store frames for moviepy
output_dir = "recordings"  # Directory for saving recordings
recording_lock = Lock()  # Lock to ensure thread-safe recording control
frame_queue = Queue(maxsize=100)  # Queue for passing frames to recording thread

last_motion_time = time.time()  # Track time since the last motion
MOTION_TIMEOUT = 5  # 5 seconds timeout for no motion

# Ensure recordings directory exists
os.makedirs(output_dir, exist_ok=True)

def register_recordings_blueprint(app):
    app.register_blueprint(recordings_bp)
    app.config['OUTPUT_DIR'] = output_dir


# Perform initial connectivity check on import/startup
try:
    ok, reason = check_camera_connection()
    last_connection_reason = reason
    # Provide TAPO-specific hint when auth fails
    if reason == 'tapo_auth_failed':
        last_connection_hint = ('After an unsuccessful login the TAPO API may block connections to the camera for 1800 seconds. '
                                'Try using username: "admin" and password: "TAPO_CLOUD_PASSWD" to log in to the API.')
    if not ok:
        print(f"Camera connectivity check failed: {reason}. The web UI will show the setup/error page.")
except Exception as e:
    print(f"Exception during initial camera check: {e}")

def start_recording_thread(frame_size, fps=15):
    """Starts the recording in a separate thread."""
    global recording, recorded_frames
    with recording_lock:
        if not recording:
            recording = True
            recorded_frames = []
            # Clear the frame queue before starting
            while not frame_queue.empty():
                try:
                    frame_queue.get_nowait()
                except Empty:
                    break
            socketio.start_background_task(record_video, frame_size, fps)
            print("Recording thread started")

def stop_recording():
    """Stops the recording thread."""
    global recording
    with recording_lock:
        if recording:
            recording = False
            print("Recording stopped")
            socketio.emit('recording_status', {'status': 'stopped'})  # Notify the client


def record_video(frame_size, fps):
    """Recording function to write video frames to MP4 from the shared frame queue using moviepy."""
    global recording, recorded_frames
    filename = os.path.join(output_dir, f"recording_{time.strftime('%Y%m%d_%H%M%S')}.mp4")

    print(f"Recording to file: {filename}")
    socketio.emit('recording_status', {'status': 'started', 'filename': filename})

    while recording:
        try:
            frame = frame_queue.get(timeout=1)
        except Empty:
            continue  # No frame available

        frame_resized = cv2.resize(frame, frame_size)
        # Convert BGR (OpenCV) to RGB for moviepy
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        recorded_frames.append(frame_rgb)

    # Write video using moviepy (web-optimized)
    if recorded_frames:
        clip = mpy.ImageSequenceClip(recorded_frames, fps=fps)
        clip.write_videofile(filename, codec='libx264', audio=False, ffmpeg_params=['-movflags', 'faststart'])
        print(f"Saved web-optimized video: {filename}")
    else:
        print("No frames recorded, skipping video file.")
    print("Recording thread finished")


def detect_motion(frame):
    """
    Funkcja wykrywa ruch, porównując bieżącą klatkę z poprzednią.
    Zwraca True, jeśli wykryto ruch.
    """
    global previous_frame

    # Konwersja klatki na skalę szarości i zmniejszenie szumu
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)  # Umiarkowane rozmycie

    if previous_frame is None:
        previous_frame = gray
        return False  # Brak poprzedniej klatki, nie można wykryć ruchu

    # Obliczenie różnicy między klatkami
    delta_frame = cv2.absdiff(previous_frame, gray)
    threshold_frame = cv2.threshold(delta_frame, 28, 255, cv2.THRESH_BINARY)[1]  # Umiarkowany próg

    # Wypełnienie obszarów progowych
    threshold_frame = cv2.dilate(threshold_frame, None, iterations=2)

    # Znalezienie konturów (obszarów zmiany)
    contours, _ = cv2.findContours(threshold_frame, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = False
    for contour in contours:
        # Ignoruj małe obszary, aby uniknąć szumów
        if cv2.contourArea(contour) < 1200:  # Umiarkowany minimalny obszar
            continue
        motion_detected = True
        global last_motion_time
        last_motion_time = time.time()  # Update the last motion time
        break

    # Motion timeout logic
    if time.time() - last_motion_time > MOTION_TIMEOUT:
        motion_detected = False

    # Zapisz bieżącą klatkę jako poprzednią dla następnego kroku
    previous_frame = gray

    socketio.emit('motion_status', {'motion': motion_detected})  # Notify client
    return motion_detected

def capture_frames():
    # Use the main RTSP stream for best quality (check your camera's documentation for the correct URL)
    cap = cv2.VideoCapture(camera_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    # Set desired resolution (Full HD 1920x1080) for server-side processing
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    # Set lower resolution and frame rate for client streaming
    STREAM_WIDTH = 640
    STREAM_HEIGHT = 360
    STREAM_FPS = 30  # Restore to 30 FPS for smoother camera movement

    while True:
        try:
            success, frame = cap.read()

            # Skip corrupted or unreadable frames
            if not success or frame is None or frame.size == 0:
                print("Warning: Corrupted or empty frame, skipping...")
                continue

            # Put frame in queue for recording if recording is active
            if recording:
                try:
                    frame_queue.put_nowait(frame.copy())
                except:
                    pass  # Queue full, drop frame

            # Resize frame for client streaming (lower resolution)
            frame_for_stream = cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT))

            try:
                # Increase JPEG compression for lower bandwidth (quality=60)
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
                _, buffer = cv2.imencode('.jpg', frame_for_stream, encode_param)
                if not _:
                    print("Failed to encode frame.")
                    continue
                frame_b64 = base64.b64encode(buffer).decode('utf-8')
            except Exception as e:
                print(f"Encoding error: {e}")
                continue

            # Wysyłanie klatki do klienta przez WebSocket
            socketio.emit('video_frame', {'frame': frame_b64})

            # Start motion detection in a separate thread if it hasn't already started
            global motion_thread
            if motion_thread is None or not motion_thread.is_alive():
                motion_thread = Thread(target=motion_detection_task, args=(frame,))
                motion_thread.start()

            # Czekanie przed wysłaniem kolejnej klatki (lower FPS)
            socketio.sleep(1.0 / STREAM_FPS)
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

    try:
        # Ensure camera is configured before attempting PTZ movement
        if not camera_connected:
            # Return an error that client can show or trigger a redirect to setup page
            resp = {"error": "Couldn't connect with camera. Check config.json.", "reason": last_connection_reason}
            if last_connection_hint:
                resp['hint'] = last_connection_hint
            return jsonify(resp), 400
        data = request.get_json()
        

        if not data or 'direction' not in data:
            return jsonify({"error": "Missing 'direction' in request"}), 400

        direction = data.get('direction')
        step = int(data.get('step', 10))  # Default step is 10

        try:
            if direction == 'left':
                camera.moveMotor(-step, 0)
            elif direction == 'right':
                camera.moveMotor(step, 0)
            elif direction == 'up':
                camera.moveMotor(0, step)
            elif direction == 'down':
                camera.moveMotor(0, -step)
            else:
                return jsonify({"error": "Invalid direction"}), 400
        except Exception as e:
            # If the error message indicates range, return a specific error
            if 'range' in str(e).lower() or 'limit' in str(e).lower() or 'boundary' in str(e).lower():
                return jsonify({"error": "Maximum range of motion reached"}), 400
            return jsonify({"error": "PTZ movement error", "message": str(e)}), 500

        return jsonify({"status": "success", "direction": direction, "step": step})
    
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
    # If config is invalid or camera not initialized, show the setup page
    if not camera_connected:
        # Show the connection error page which instructs user to check config.json
        return render_template('connection_error.html', reason=(last_connection_reason or "Unknown error"), hint=(last_connection_hint or ""))
    return render_template('index.html')

def start_video_stream():
    # Guard: only start stream if camera is configured
    if not camera_connected:
        print("Video stream not started: couldn't connect to camera.")
        return
    thread = Thread(target=capture_frames)
    thread.daemon = True
    thread.start()
