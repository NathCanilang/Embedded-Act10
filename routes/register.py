from flask import Blueprint, render_template, Response, request, jsonify, current_app
import cv2
import base64
import numpy as np
import os
from datetime import datetime
from camera import generate_frames, capture_frame, face_cascade
from face_detection import load_training_data, train_model, get_registered_names, get_person_image_count, delete_person

register_bp = Blueprint('register', __name__)

# Number of images to capture for registration
IMAGES_TO_CAPTURE = 30

@register_bp.route('/')
def register_page():
    """Registration page"""
    return render_template('register/index.html', images_to_capture=IMAGES_TO_CAPTURE)

@register_bp.route('/video_feed')
def video_feed():
    """Video streaming route for registration (no detection)"""
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@register_bp.route('/capture', methods=['POST'])
def capture():
    """Capture current frame for registration - returns face crop if detected"""
    frame = capture_frame()
    
    if frame is not None:
        # Detect face in frame
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        if len(faces) == 0:
            return jsonify({'success': False, 'error': 'No face detected'})
        
        if len(faces) > 1:
            return jsonify({'success': False, 'error': 'Multiple faces detected. Please ensure only one face is visible.'})
        
        # Get face region
        x, y, w, h = faces[0]
        
        # Add some padding around the face
        padding = 20
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(frame.shape[1], x + w + padding)
        y2 = min(frame.shape[0], y + h + padding)
        
        face_crop = frame[y1:y2, x1:x2]
        
        # Convert to base64
        ret, buffer = cv2.imencode('.jpg', face_crop)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True, 
            'image': img_base64,
            'face_detected': True
        })
    
    return jsonify({'success': False, 'error': 'Failed to capture frame'})

@register_bp.route('/capture_multiple', methods=['POST'])
def capture_multiple():
    """Capture a single frame during multi-capture registration"""
    data = request.json
    name = data.get('name', '').strip()
    capture_index = data.get('index', 0)
    
    if not name:
        return jsonify({'success': False, 'error': 'Name is required'})
    
    frame = capture_frame()
    
    if frame is None:
        return jsonify({'success': False, 'error': 'Failed to capture frame'})
    
    # Detect face in frame
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )
    
    if len(faces) == 0:
        return jsonify({'success': False, 'error': 'No face detected', 'retry': True})
    
    if len(faces) > 1:
        return jsonify({'success': False, 'error': 'Multiple faces detected', 'retry': True})
    
    try:
        # Create person's folder
        known_faces_dir = current_app.config.get('KNOWN_FACES_DIR', 'known_faces')
        person_dir = os.path.join(known_faces_dir, name)
        
        if not os.path.exists(person_dir):
            os.makedirs(person_dir)
        
        # Get face region with padding
        x, y, w, h = faces[0]
        padding = 20
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(frame.shape[1], x + w + padding)
        y2 = min(frame.shape[0], y + h + padding)
        
        face_crop = frame[y1:y2, x1:x2]
        
        # Save image
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{capture_index:03d}_{timestamp}.jpg"
        filepath = os.path.join(person_dir, filename)
        cv2.imwrite(filepath, face_crop)
        
        # Convert to base64 for preview
        ret, buffer = cv2.imencode('.jpg', face_crop)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'image': img_base64,
            'index': capture_index,
            'filename': filename
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@register_bp.route('/complete_registration', methods=['POST'])
def complete_registration():
    """Complete registration and retrain the model"""
    data = request.json
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'success': False, 'error': 'Name is required'})
    
    # Check if person has enough images
    image_count = get_person_image_count(name)
    
    if image_count < IMAGES_TO_CAPTURE:
        return jsonify({
            'success': False, 
            'error': f'Not enough images. Captured {image_count}/{IMAGES_TO_CAPTURE}'
        })
    
    try:
        # Retrain the model with new data
        print(f"Retraining model after registering {name}...")
        load_training_data()
        train_model()
        
        return jsonify({
            'success': True,
            'message': f'Successfully registered {name} with {image_count} images',
            'image_count': image_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@register_bp.route('/save', methods=['POST'])
def save_face():
    """Save a captured face with name (legacy single-image endpoint)"""
    data = request.json
    name = data.get('name', '').strip()
    image_data = data.get('image', '')
    
    if not name:
        return jsonify({'success': False, 'error': 'Name is required'})
    
    if not image_data:
        return jsonify({'success': False, 'error': 'Image is required'})
    
    try:
        # Decode base64 image
        img_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Create person's folder
        known_faces_dir = current_app.config.get('KNOWN_FACES_DIR', 'known_faces')
        person_dir = os.path.join(known_faces_dir, name)
        
        if not os.path.exists(person_dir):
            os.makedirs(person_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}.jpg"
        filepath = os.path.join(person_dir, filename)
        cv2.imwrite(filepath, img)
        
        return jsonify({
            'success': True, 
            'message': f'Saved image for {name}',
            'filename': filename
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

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
