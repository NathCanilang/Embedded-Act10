import cv2
from face_detection import detect_face, recognize_face

# Global camera instance
camera = None
face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_alt.xml")

def get_camera():
    """Get or initialize camera"""
    global camera
    if camera is None:
        camera = cv2.VideoCapture(0)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return camera

def release_camera():
    """Release camera resource"""
    global camera
    if camera is not None:
        camera.release()
        camera = None

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
    Generate frames with face detection and KNN-based recognition.
    """
    cam = get_camera()
    
    while True:
        success, frame = cam.read()
        if not success:
            break
        
        # Detect faces using the face_detection module
        faces = detect_face(frame)
        
        # Draw bounding boxes for detected faces
        for (x, y, w, h, face_gray) in faces:
            # Try to recognize the face using KNN
            name, confidence = recognize_face(face_gray)
            
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
