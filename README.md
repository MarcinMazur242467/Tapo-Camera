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

You can install the required packages using pip:

```
pip install -r requirements.txt
```

## Configuration

The configuration settings for the application can be found in `config.py`. You can modify the settings such as secret keys and WebSocket configurations as needed.

## Running the Application

To start the application, run the following command:

```
python run.py
```

Once the server is running, you can access the application in your web browser at `http://localhost:5000`.

## Usage

- Navigate to the main page to access the video streaming interface.
- The application uses WebSockets to stream video in real-time.

## License

This project is licensed under the MIT License.