# Flask Video Streaming Application

This project implements a video streaming application using Flask and WebSockets. It allows real-time video streaming to clients through a web interface.

## Project Structure

```
flask-video-streaming
├── app
│   ├── __init__.py
│   ├── routes.py
│   ├── static
│   │   └── video.html
│   └── templates
│       └── index.html
├── requirements.txt
├── config.py
├── run.py
└── README.md
```

## Requirements

To run this project, you need to install the following dependencies:

- Flask
- Flask-SocketIO
- eventlet
- opencv-python
- numpy
- pytapo

You can install the required packages using pip:

```
pip install -r requirements.txt
```

## Configuration

The configuration settings for the application can be found in `config.py` and `config.json`. You can modify the settings such as secret keys and WebSocket configurations as needed.

## Running the Application

To start the application, run the following command:

```
python run.py
```

Once the server is running, you can access the application in your web browser at `http://localhost:5000`.

## Usage

- Navigate to the main page to access the video streaming interface.
- The application uses WebSockets to stream video in real-time.
- Use the camera controls to move the camera.
- Use the recording controls to start and stop video recording.

## Technologies and Concepts

- **Flask**: A micro web framework for Python.
- **Flask-SocketIO**: Enables WebSocket communication in Flask applications.
- **WebSockets**: Provides full-duplex communication channels over a single TCP connection.
- **OpenCV**: A library for computer vision tasks, used here for video capture and processing.
- **Eventlet**: A concurrent networking library for Python, used by Flask-SocketIO.
- **pytapo**: A library to control Tapo cameras.
- **Threading**: Used for handling video capture and motion detection in separate threads.
- **Base64 Encoding**: Used to encode video frames for transmission over WebSockets.
- **Motion Detection**: Implemented using frame differencing and contour detection with OpenCV.
- **Video Recording**: Captures and saves video streams to files using OpenCV's `VideoWriter`.

## License

This project is licensed under the MIT License.