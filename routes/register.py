from flask import Blueprint, render_template, Response, request, jsonify, current_app
import cv2
import base64
import numpy as np
import os
import shutil
import time
from datetime import datetime
from camera import generate_frames, capture_frame, face_cascade, get_camera
from face_detection import (
    train_model, get_registered_names, 
    get_person_image_count, delete_person
)
from gesture_detection import (
    detect_gesture, draw_hand_landmarks, draw_gesture_indicator
)

register_bp = Blueprint('register', __name__)

# Number of images to capture for registration
IMAGES_TO_CAPTURE = 40

# Face validation parameters
MIN_FACE_SIZE = 80      # Minimum face size in pixels
MAX_FACE_SIZE = 400     # Maximum face size in pixels
MIN_BLUR_THRESHOLD = 50 # Minimum Laplacian variance (higher = less blurry)
MIN_BRIGHTNESS = 40     # Minimum mean brightness
MAX_BRIGHTNESS = 220    # Maximum mean brightness

# Session storage for registration in progress
registration_session = {
    'active': False,
    'name': '',
    'captured_count': 0,
    'images': [],
    'gesture_capture_enabled': False,
    'last_gesture': None,
    'last_gesture_time': 0
}

# Gesture cooldown (seconds)
GESTURE_COOLDOWN = 1.5

@register_bp.route('/')
def register_page():
    """Registration page"""
    return render_template('register/index.html', images_to_capture=IMAGES_TO_CAPTURE)

@register_bp.route('/video_feed')
def video_feed():
    """Video streaming route for registration (no detection)"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@register_bp.route('/video_feed_gesture')
def video_feed_gesture():
    """Video streaming route with gesture detection overlay"""
    return Response(generate_frames_with_gesture(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

def generate_frames_with_gesture():
    """Generate video frames with gesture detection overlay."""
    global registration_session
    
    cam = get_camera()
    
    while True:
        success, frame = cam.read()
        if not success:
            break
        
        # Detect gesture
        gesture, confidence, landmarks = detect_gesture(frame)
        
        # Draw hand landmarks
        if landmarks:
            frame = draw_hand_landmarks(frame, landmarks)
        
        # Draw gesture indicator
        frame = draw_gesture_indicator(frame, gesture, confidence)
        
        # Update session with detected gesture (with cooldown)
        current_time = time.time()
        if gesture and (current_time - registration_session['last_gesture_time']) > GESTURE_COOLDOWN:
            registration_session['last_gesture'] = gesture
            registration_session['last_gesture_time'] = current_time
        
        # Add instructions overlay
        cv2.putText(frame, "Gestures: Thumbs Up=Capture, Thumbs Down=Cancel, One=New User", 
                    (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        
        # Encode and yield frame
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@register_bp.route('/gesture_status')
def gesture_status():
    """Get current gesture status for polling."""
    global registration_session
    
    gesture = registration_session.get('last_gesture')
    gesture_time = registration_session.get('last_gesture_time', 0)
    
    # Clear gesture after reading (one-time trigger)
    if gesture:
        registration_session['last_gesture'] = None
    
    return jsonify({
        'gesture': gesture,
        'timestamp': gesture_time,
        'session_active': registration_session.get('active', False),
        'captured_count': registration_session.get('captured_count', 0),
        'gesture_capture_enabled': registration_session.get('gesture_capture_enabled', False)
    })

@register_bp.route('/start', methods=['POST'])
def start_registration():
    """Start a new registration session"""
    global registration_session
    
    data = request.json
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'status': 'error', 'message': 'Name is required'})
    
    # Reset session with gesture support
    registration_session = {
        'active': True,
        'name': name,
        'captured_count': 0,
        'images': [],
        'gesture_capture_enabled': True,
        'last_gesture': None,
        'last_gesture_time': 0
    }
    
    print(f"Started registration for: {name}")
    return jsonify({'status': 'started', 'name': name, 'total': IMAGES_TO_CAPTURE})

@register_bp.route('/capture_multiple', methods=['POST'])
def capture_multiple():
    """Capture images during registration with validation"""
    global registration_session
    
    if not registration_session['active']:
        return jsonify({'status': 'error', 'message': 'No active registration session'})
    
    if registration_session['captured_count'] >= IMAGES_TO_CAPTURE:
        return jsonify({
            'status': 'completed',
            'captured': registration_session['captured_count'],
            'total': IMAGES_TO_CAPTURE
        })
    
    frame = capture_frame()
    
    if frame is None:
        return jsonify({
            'status': 'skipped',
            'validation': {'error': 'Failed to capture frame'},
            'captured': registration_session['captured_count']
        })
    
    # Detect face in frame
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray_equalized = cv2.equalizeHist(gray)
    
    faces = face_cascade.detectMultiScale(
        gray_equalized,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )
    
    # Validation checks
    validation = {'valid': True}
    
    if len(faces) == 0:
        validation = {'valid': False, 'no_face': True}
        return jsonify({
            'status': 'skipped',
            'validation': validation,
            'captured': registration_session['captured_count']
        })
    
    if len(faces) > 1:
        validation = {'valid': False, 'error': 'Multiple faces'}
        return jsonify({
            'status': 'skipped',
            'validation': validation,
            'captured': registration_session['captured_count']
        })
    
    # Get face dimensions
    x, y, w, h = faces[0]
    face_size = max(w, h)
    
    # Check face size
    if face_size < MIN_FACE_SIZE:
        validation = {'valid': False, 'face_size': 'small'}
        return jsonify({
            'status': 'skipped',
            'validation': validation,
            'captured': registration_session['captured_count']
        })
    
    if face_size > MAX_FACE_SIZE:
        validation = {'valid': False, 'face_size': 'large'}
        return jsonify({
            'status': 'skipped',
            'validation': validation,
            'captured': registration_session['captured_count']
        })
    
    # Extract face region for quality checks
    face_gray = gray[y:y+h, x:x+w]
    
    # Check blur (Laplacian variance)
    laplacian_var = cv2.Laplacian(face_gray, cv2.CV_64F).var()
    if laplacian_var < MIN_BLUR_THRESHOLD:
        validation = {'valid': False, 'blur': True}
        return jsonify({
            'status': 'skipped',
            'validation': validation,
            'captured': registration_session['captured_count']
        })
    
    # Check brightness
    mean_brightness = np.mean(face_gray)
    if mean_brightness < MIN_BRIGHTNESS:
        validation = {'valid': False, 'brightness': 'dark'}
        return jsonify({
            'status': 'skipped',
            'validation': validation,
            'captured': registration_session['captured_count']
        })
    
    if mean_brightness > MAX_BRIGHTNESS:
        validation = {'valid': False, 'brightness': 'bright'}
        return jsonify({
            'status': 'skipped',
            'validation': validation,
            'captured': registration_session['captured_count']
        })
    
    # Check face is reasonably centered
    frame_height, frame_width = frame.shape[:2]
    face_center_x = x + w // 2
    face_center_y = y + h // 2
    margin = 0.1
    
    if (face_center_x < frame_width * margin or 
        face_center_x > frame_width * (1 - margin) or
        face_center_y < frame_height * margin or 
        face_center_y > frame_height * (1 - margin)):
        validation = {'valid': False, 'error': 'Face at edge'}
        return jsonify({
            'status': 'skipped',
            'validation': validation,
            'captured': registration_session['captured_count']
        })
    
    # === IMAGE IS VALID - SAVE IT ===
    try:
        name = registration_session['name']
        known_faces_dir = current_app.config.get('KNOWN_FACES_DIR', 'known_faces')
        person_dir = os.path.join(known_faces_dir, name)
        
        if not os.path.exists(person_dir):
            os.makedirs(person_dir)
        
        # Extract face region (grayscale, no padding - exact face bbox)
        # This ensures consistency with how LBPH training loads images
        face_gray_crop = gray[y:y+h, x:x+w]
        
        # Resize to standard size for LBPH (100x100)
        face_resized = cv2.resize(face_gray_crop, (100, 100))
        
        # Save grayscale image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        idx = registration_session['captured_count']
        filename = f"{idx:03d}_{timestamp}.jpg"
        filepath = os.path.join(person_dir, filename)
        cv2.imwrite(filepath, face_resized)
        
        registration_session['captured_count'] += 1
        registration_session['images'].append(filepath)
        
        captured = registration_session['captured_count']
        
        # Check if completed
        if captured >= IMAGES_TO_CAPTURE:
            return jsonify({
                'status': 'completed',
                'captured': captured,
                'total': IMAGES_TO_CAPTURE,
                'validation': {'valid': True}
            })
        
        return jsonify({
            'status': 'capturing',
            'captured': captured,
            'total': IMAGES_TO_CAPTURE,
            'validation': {'valid': True}
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'captured': registration_session['captured_count']
        })

@register_bp.route('/complete', methods=['POST'])
def complete_registration():
    """Complete registration and train the model"""
    global registration_session
    
    if not registration_session['active']:
        return jsonify({'status': 'error', 'message': 'No active registration session'})
    
    name = registration_session['name']
    captured = registration_session['captured_count']
    
    if captured < IMAGES_TO_CAPTURE:
        return jsonify({
            'status': 'error',
            'message': f'Not enough images. Captured {captured}/{IMAGES_TO_CAPTURE}'
        })
    
    try:
        # Train the model with new data
        print(f"Training model after registering {name} with {captured} images...")
        train_model()
        
        # Reset session
        registration_session = {
            'active': False,
            'name': '',
            'captured_count': 0,
            'images': [],
            'gesture_capture_enabled': False,
            'last_gesture': None,
            'last_gesture_time': 0
        }
        
        return jsonify({
            'status': 'success',
            'message': f'Successfully registered {name}',
            'images_saved': captured
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@register_bp.route('/cancel', methods=['POST'])
def cancel_registration():
    """Cancel the current registration session"""
    global registration_session
    
    if registration_session.get('active', False):
        name = registration_session.get('name', '')
        
        # Optionally delete captured images
        if name:
            try:
                known_faces_dir = current_app.config.get('KNOWN_FACES_DIR', 'known_faces')
                person_dir = os.path.join(known_faces_dir, name)
                if os.path.exists(person_dir):
                    # Only delete if it was just created (has few images)
                    count = get_person_image_count(name)
                    if count <= IMAGES_TO_CAPTURE:
                        shutil.rmtree(person_dir)
                        print(f"Deleted incomplete registration for {name}")
            except Exception as e:
                print(f"Error cleaning up: {e}")
    
    # Reset session
    registration_session = {
        'active': False,
        'name': '',
        'captured_count': 0,
        'images': [],
        'gesture_capture_enabled': False,
        'last_gesture': None,
        'last_gesture_time': 0
    }
    
    return jsonify({'status': 'cancelled'})

@register_bp.route('/list')
def list_faces():
    """Get list of registered faces"""
    names = get_registered_names()
    
    faces_info = []
    for name in names:
        count = get_person_image_count(name)
        faces_info.append({
            'name': name,
            'image_count': count
        })
    
    return jsonify({'success': True, 'faces': [f['name'] for f in faces_info], 'faces_info': faces_info})

@register_bp.route('/delete/<name>', methods=['DELETE'])
def delete_face(name):
    """Delete a registered face"""
    if not name:
        return jsonify({'success': False, 'error': 'Name is required'})
    
    if delete_person(name):
        return jsonify({'success': True, 'message': f'Deleted {name}'})
    else:
        return jsonify({'success': False, 'error': f'Failed to delete {name}'})


@register_bp.route('/update/<name>', methods=['POST'])
def start_update_registration(name):
    """Start updating images for an existing registered user"""
    global registration_session
    
    if not name:
        return jsonify({'status': 'error', 'message': 'Name is required'})
    
    # Check if user exists
    existing_names = get_registered_names()
    if name not in existing_names:
        return jsonify({'status': 'error', 'message': f'User "{name}" not found'})
    
    # Delete existing images for this user
    known_faces_dir = current_app.config.get('KNOWN_FACES_DIR', 'known_faces')
    person_dir = os.path.join(known_faces_dir, name)
    
    try:
        if os.path.exists(person_dir):
            shutil.rmtree(person_dir)
            print(f"Cleared existing images for: {name}")
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to clear existing images: {str(e)}'})
    
    # Reset session with gesture support for update mode
    registration_session = {
        'active': True,
        'name': name,
        'captured_count': 0,
        'images': [],
        'gesture_capture_enabled': True,
        'last_gesture': None,
        'last_gesture_time': 0,
        'update_mode': True  # Flag to indicate this is an update
    }
    
    print(f"Started image update for: {name}")
    return jsonify({'status': 'started', 'name': name, 'total': IMAGES_TO_CAPTURE, 'update_mode': True})
