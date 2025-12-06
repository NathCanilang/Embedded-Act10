"""
Camera Module - Handles camera operations with OS-specific support

- Windows: Uses standard OpenCV VideoCapture
- Linux/Raspberry Pi: Uses PiCamera2 if available, falls back to OpenCV
"""

import cv2
import platform
import sys
import time
from face_detection import detect_face, recognize_face
from buzzer import activate_buzzer

# Detect operating system
IS_WINDOWS = platform.system() == 'Windows'
IS_LINUX = platform.system() == 'Linux'
IS_RASPBERRY_PI = False

# Check if running on Raspberry Pi
if IS_LINUX:
    try:
        with open('/proc/device-tree/model', 'r') as f:
            if 'Raspberry Pi' in f.read():
                IS_RASPBERRY_PI = True
    except:
        pass

# Global camera instance
camera = None
picamera_available = False

# Try to import picamera2 for Raspberry Pi
if IS_LINUX:
    try:
        from picamera2 import Picamera2
        picamera_available = True
        print("PiCamera2 module available", flush=True)
    except ImportError:
        print("PiCamera2 not available, using OpenCV", flush=True)

# Face cascade for detection
face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_alt.xml")

# Detection events for notifications
detection_events = []
MAX_EVENTS = 50  # Keep last 50 events
NOTIFICATION_COOLDOWN = 3.0  # Seconds between notifications for same person
last_notifications = {}  # Track last notification time per person

def get_camera():
    """Get or initialize camera based on OS"""
    global camera
    
    if camera is not None:
        return camera
    
    if IS_RASPBERRY_PI and picamera_available:
        # Use PiCamera2 for Raspberry Pi
        try:
            camera = PiCameraWrapper()
            print("Using PiCamera2 for Raspberry Pi", flush=True)
            return camera
        except Exception as e:
            print(f"Failed to initialize PiCamera2: {e}", flush=True)
            print("Falling back to OpenCV", flush=True)
    
    # Use OpenCV VideoCapture for Windows or as fallback
    camera = OpenCVCameraWrapper()
    print(f"Using OpenCV camera on {platform.system()}", flush=True)
    return camera

def release_camera():
    """Release camera resource"""
    global camera
    if camera is not None:
        camera.release()
        camera = None

class OpenCVCameraWrapper:
    """Wrapper for OpenCV VideoCapture"""
    
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        if not self.cap.isOpened():
            raise RuntimeError("Could not open camera")
    
    def read(self):
        """Read a frame from the camera"""
        return self.cap.read()
    
    def release(self):
        """Release the camera"""
        if self.cap is not None:
            self.cap.release()

class PiCameraWrapper:
    """Wrapper for PiCamera2 to provide OpenCV-like interface"""
    
    def __init__(self):
        self.picam2 = Picamera2()
        
        # Configure camera for preview
        config = self.picam2.create_preview_configuration(
            main={"size": (640, 480), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()
    
    def read(self):
        """Read a frame from the camera (OpenCV compatible)"""
        try:
            # Capture frame as numpy array
            frame = self.picam2.capture_array()
            
            # Convert RGB to BGR for OpenCV compatibility
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            return True, frame_bgr
        except Exception as e:
            print(f"PiCamera read error: {e}", flush=True)
            return False, None
    
    def release(self):
        """Release the camera"""
        if self.picam2 is not None:
            self.picam2.stop()
            self.picam2.close()

def generate_frames():
    """Generate frames from camera (basic - no face detection)"""
    cam = get_camera()
    
    while True:
        success, frame = cam.read()
        if not success:
            break
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

def generate_frames_with_detection():
    """
    Generate frames with face detection and LBPH-based recognition.
    Uses smoothing to reduce bounding box jitter.
    Triggers buzzer for unknown faces and tracks detection events.
    """
    global detection_events, last_notifications
    
    cam = get_camera()
    
    # Smoothing: store previous face positions for stability
    prev_faces = {}  # Dictionary to track faces by approximate position
    smooth_factor = 0.7  # How much to weight previous position (higher = smoother but laggier)
    
    while True:
        success, frame = cam.read()
        if not success:
            break
        
        # Detect faces using the face_detection module
        faces = detect_face(frame)
        
        current_faces = {}
        current_time = time.time()
        
        # Draw bounding boxes for detected faces
        for (x, y, w, h, face_gray) in faces:
            # Try to recognize the face using LBPH
            name, confidence = recognize_face(face_gray)
            
            # Create a key based on approximate center position (for tracking)
            center_x, center_y = x + w // 2, y + h // 2
            face_key = None
            
            # Find matching previous face (within 100 pixels)
            for key, (px, py, pw, ph, pname) in prev_faces.items():
                pcx, pcy = px + pw // 2, py + ph // 2
                if abs(center_x - pcx) < 100 and abs(center_y - pcy) < 100:
                    face_key = key
                    # Apply smoothing
                    x = int(px * smooth_factor + x * (1 - smooth_factor))
                    y = int(py * smooth_factor + y * (1 - smooth_factor))
                    w = int(pw * smooth_factor + w * (1 - smooth_factor))
                    h = int(ph * smooth_factor + h * (1 - smooth_factor))
                    break
            
            if face_key is None:
                face_key = f"{center_x}_{center_y}"
            
            current_faces[face_key] = (x, y, w, h, name)
            
            # Handle detection events and notifications
            person_id = name if name else "Unknown"
            last_notif_time = last_notifications.get(person_id, 0)
            
            if current_time - last_notif_time > NOTIFICATION_COOLDOWN:
                # Create detection event
                event = {
                    'timestamp': current_time,
                    'name': name,
                    'confidence': confidence,
                    'type': 'recognized' if name else 'unknown'
                }
                detection_events.append(event)
                
                # Trim events list if too long
                if len(detection_events) > MAX_EVENTS:
                    detection_events = detection_events[-MAX_EVENTS:]
                
                last_notifications[person_id] = current_time
                
                # Trigger buzzer for unknown faces
                if not name:
                    activate_buzzer(duration=0.3)
            
            if name:
                # Known face - GREEN box
                color = (0, 255, 0)
                label = f"{name} ({confidence:.0%})"
            else:
                # Unknown face - RED box
                color = (0, 0, 255)
                label = "Unknown"
            
            # Draw rectangle around face
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            
            # Draw label background
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            cv2.rectangle(frame, (x, y - 25), (x + label_size[0] + 10, y), color, -1)
            
            # Draw label text
            cv2.putText(frame, label, (x + 5, y - 7), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Update previous faces for next frame
        prev_faces = current_faces
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

def capture_frame():
    """Capture a single frame from camera"""
    cam = get_camera()
    success, frame = cam.read()
    
    if success:
        return frame
    return None

def get_camera_info():
    """Get information about the current camera setup"""
    return {
        'os': platform.system(),
        'is_raspberry_pi': IS_RASPBERRY_PI,
        'picamera_available': picamera_available,
        'camera_type': 'PiCamera2' if (IS_RASPBERRY_PI and picamera_available) else 'OpenCV'
    }


def get_detection_events(since_timestamp=0):
    """
    Get detection events since a given timestamp.
    
    Args:
        since_timestamp: Only return events after this timestamp
    
    Returns:
        List of detection events
    """
    global detection_events
    
    if since_timestamp:
        return [e for e in detection_events if e['timestamp'] > since_timestamp]
    return detection_events.copy()


def clear_detection_events():
    """Clear all detection events."""
    global detection_events
    detection_events = []
