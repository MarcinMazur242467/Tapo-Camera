

from flask import Blueprint, render_template, send_file, current_app, abort, request, Response, redirect, url_for
from werkzeug.utils import safe_join
import os

recordings_bp = Blueprint('recordings', __name__, template_folder='templates')

@recordings_bp.route('/recordings')
def recordings_browser():
    output_dir = current_app.config.get('OUTPUT_DIR', 'recordings')
    try:
        files = [f for f in os.listdir(output_dir) if f.endswith('.mp4')]
        files.sort(reverse=True)
    except Exception as e:
        files = []
        error = str(e)
    else:
        error = None
    return render_template('recordings.html', files=files, error=error)


# Serve video for in-browser playback (not as attachment)


@recordings_bp.route('/recordings/play/<filename>')
def play_recording(filename):
    # Use absolute path to the recordings directory
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    recordings_dir = os.path.join(base_dir, 'recordings')
    file_path = safe_join(recordings_dir, filename)
    
    if not file_path or not os.path.isfile(file_path):
        abort(404)
    
    # Send file for in-browser playback (not as attachment)
    return send_file(file_path, mimetype='video/mp4')
    
        
        
@recordings_bp.route('/recordings/download/<filename>')
def download_recording(filename):
    # Use absolute path to the recordings directory
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    recordings_dir = os.path.join(base_dir, 'recordings')
    file_path = safe_join(recordings_dir, filename)
    if not file_path or not os.path.isfile(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True, mimetype='video/mp4')


@recordings_bp.route('/recordings/delete/<filename>', methods=['POST'])
def delete_recording(filename):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    recordings_dir = os.path.join(base_dir, 'recordings')
    file_path = safe_join(recordings_dir, filename)
    if not file_path or not os.path.isfile(file_path):
        abort(404)
    try:
        os.remove(file_path)
    except Exception as e:
        return abort(500, description=f"Could not delete file: {e}")
    return redirect(url_for('recordings.recordings_browser'))
