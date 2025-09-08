
import os
import time
import cv2
import moviepy as mpy
from threading import Lock
from queue import Queue, Empty
from . import socketio

# Recording state and resources
recording = False  # Flag for recording state
recorded_frames = []  # List to store frames for moviepy
output_dir = "recordings"  # Directory for saving recordings
recording_lock = Lock()  # Lock to ensure thread-safe recording control
frame_queue = Queue(maxsize=100)  # Queue for passing frames to recording thread

# Ensure recordings directory exists
os.makedirs(output_dir, exist_ok=True)

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
