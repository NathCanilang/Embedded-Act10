"""
Face Recognition Module using LBPH (Local Binary Pattern Histogram)

This module handles:
- Face detection using Haar Cascade
- Face recognition using OpenCV's LBPH Face Recognizer
- Model training and persistence
"""

import cv2
import numpy as np
import os
import pickle

# Paths
KNOWN_FACES_DIR = "known_faces"
MODEL_PATH = "face_model.yml"
LABELS_PATH = "face_labels.pkl"

# Face cascade for detection
face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_alt.xml")

# Global LBPH recognizer and label mapping
lbph_recognizer = None
label_to_name = {}
name_to_label = {}

# Recognition threshold - lower is stricter (LBPH confidence is distance-based)
# Values < 50 are very good matches, 50-80 are acceptable, > 80 are poor
RECOGNITION_THRESHOLD = 80

# Face size requirements for validation
MIN_FACE_SIZE = 80   # Minimum face width/height in pixels (far position)
MAX_FACE_SIZE = 300  # Maximum face width/height in pixels (near position)
IDEAL_FACE_SIZE = 150  # Ideal face size (medium position)

def detect_face(frame):
    """
    Detect faces in a frame and return face regions.
    Uses more stable parameters to reduce flickering.
    
    Args:
        frame: BGR image
    
    Returns:
        List of tuples (x, y, w, h, face_gray)
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Equalize histogram for better detection in varying lighting
    gray_eq = cv2.equalizeHist(gray)
    
    # Detect faces on equalized image
    faces = face_cascade.detectMultiScale(
        gray_eq,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(40, 40),
        flags=cv2.CASCADE_SCALE_IMAGE
    )
    
    result = []
    for (x, y, w, h) in faces:
        # Extract face from original gray (not equalized) for recognition
        # Recognition will handle equalization consistently with training
        face_gray = gray[y:y+h, x:x+w]
        result.append((x, y, w, h, face_gray))
    
    return result

def validate_face_for_capture(face_width, face_height, required_position=None):
    """
    Validate if a face is suitable for capture based on size and position requirements.
    
    Args:
        face_width: Width of detected face
        face_height: Height of detected face
        required_position: 'near', 'medium', 'far', or None for any
    
    Returns:
        Tuple (is_valid, message, detected_position)
    """
    face_size = max(face_width, face_height)
    
    # Determine detected position based on face size
    if face_size >= 200:
        detected_position = 'near'
    elif face_size >= 120:
        detected_position = 'medium'
    elif face_size >= MIN_FACE_SIZE:
        detected_position = 'far'
    else:
        return False, f"Face too small ({face_size}px). Move closer to the camera.", None
    
    if face_size > MAX_FACE_SIZE:
        return False, f"Face too close ({face_size}px). Move back from the camera.", detected_position
    
    # Check if it matches required position
    if required_position:
        if required_position == 'near' and face_size < 200:
            return False, "Move CLOSER to the camera for near capture.", detected_position
        elif required_position == 'medium' and (face_size < 120 or face_size >= 200):
            return False, "Adjust distance for medium capture (arm's length).", detected_position
        elif required_position == 'far' and face_size >= 120:
            return False, "Move FURTHER from the camera for far capture.", detected_position
    
    return True, f"Good! Face detected at {detected_position} position.", detected_position

def load_training_data():
    """
    Load all face images from known_faces directory for LBPH training.
    
    Returns:
        Tuple (faces_list, labels_list) or ([], []) if no data
    """
    global label_to_name, name_to_label
    
    faces = []
    labels = []
    label_to_name = {}
    name_to_label = {}
    current_label = 0
    
    if not os.path.exists(KNOWN_FACES_DIR):
        print("Known faces directory not found", flush=True)
        return [], []
    
    for person_name in os.listdir(KNOWN_FACES_DIR):
        person_dir = os.path.join(KNOWN_FACES_DIR, person_name)
        
        if not os.path.isdir(person_dir):
            continue
        
        print(f"Loading faces for: {person_name}", flush=True)
        
        # Assign label to this person
        if person_name not in name_to_label:
            name_to_label[person_name] = current_label
            label_to_name[current_label] = person_name
            current_label += 1
        
        person_label = name_to_label[person_name]
        
        for image_name in os.listdir(person_dir):
            if not image_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            image_path = os.path.join(person_dir, image_name)
            
            try:
                # Load image in grayscale (already saved as 100x100 grayscale)
                img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    print(f"  Failed to load: {image_path}", flush=True)
                    continue
                
                # Verify size and resize if needed (for compatibility with old images)
                if img.shape != (100, 100):
                    img = cv2.resize(img, (100, 100))
                
                # Equalize histogram for consistent lighting
                img_equalized = cv2.equalizeHist(img)
                
                faces.append(img_equalized)
                labels.append(person_label)
                    
            except Exception as e:
                print(f"Error processing {image_path}: {e}", flush=True)
                continue
    
    print(f"Loaded {len(faces)} face images for {len(name_to_label)} people", flush=True)
    return faces, labels

def train_model():
    """
    Train the LBPH recognizer on the loaded face data.
    """
    global lbph_recognizer, label_to_name, name_to_label
    
    faces, labels = load_training_data()
    
    if len(faces) == 0:
        print("No training data available", flush=True)
        return False
    
    # Create LBPH Face Recognizer
    lbph_recognizer = cv2.face.LBPHFaceRecognizer_create(
        radius=1,
        neighbors=8,
        grid_x=8,
        grid_y=8,
        threshold=RECOGNITION_THRESHOLD
    )
    
    # Train the recognizer
    lbph_recognizer.train(faces, np.array(labels))
    
    print(f"LBPH model trained with {len(faces)} samples", flush=True)
    
    # Save model
    save_model()
    
    return True

def save_model():
    """Save the trained LBPH model and label mappings to disk."""
    global lbph_recognizer, label_to_name, name_to_label
    
    try:
        if lbph_recognizer is not None:
            # Save LBPH model
            lbph_recognizer.save(MODEL_PATH)
            
            # Save label mappings
            with open(LABELS_PATH, 'wb') as f:
                pickle.dump({
                    'label_to_name': label_to_name,
                    'name_to_label': name_to_label
                }, f)
            
            print("LBPH model saved successfully", flush=True)
            return True
    except Exception as e:
        print(f"Error saving model: {e}", flush=True)
    
    return False

def load_model():
    """Load the trained LBPH model and label mappings from disk."""
    global lbph_recognizer, label_to_name, name_to_label
    
    print(f"Attempting to load LBPH model from {MODEL_PATH}...", flush=True)
    
    try:
        if os.path.exists(MODEL_PATH) and os.path.exists(LABELS_PATH):
            # Create recognizer and load model
            lbph_recognizer = cv2.face.LBPHFaceRecognizer_create()
            lbph_recognizer.read(MODEL_PATH)
            
            # Load label mappings
            with open(LABELS_PATH, 'rb') as f:
                data = pickle.load(f)
                label_to_name = data['label_to_name']
                name_to_label = data['name_to_label']
            
            print(f"LBPH model loaded: {len(label_to_name)} people registered", flush=True)
            return True
        else:
            print(f"Model files not found", flush=True)
    except Exception as e:
        print(f"Error loading model: {e}", flush=True)
    
    return False

def recognize_face(face_gray):
    """
    Recognize a face using the trained LBPH model.
    
    Args:
        face_gray: Grayscale face image (cropped)
    
    Returns:
        Tuple (name, confidence) or (None, 0) if not recognized
    """
    global lbph_recognizer, label_to_name
    
    if lbph_recognizer is None:
        return None, 0
    
    try:
        # Resize to 100x100 to match training data
        face_resized = cv2.resize(face_gray, (100, 100))
        
        # Equalize histogram (same as training)
        face_equalized = cv2.equalizeHist(face_resized)
        
        # Verify input is correct format
        if face_equalized.dtype != np.uint8:
            face_equalized = face_equalized.astype(np.uint8)
        
        # Predict using LBPH
        label, distance = lbph_recognizer.predict(face_equalized)
        
        # LBPH returns distance - lower is better match
        # Typical good match: < 50, acceptable: 50-80, poor: > 80
        
        # Convert distance to confidence percentage for display
        # Cap distance at 100 for percentage calculation
        confidence_percent = max(0, min(100, 100 - distance)) / 100
        
        # Check if match is good enough
        if distance < RECOGNITION_THRESHOLD:
            name = label_to_name.get(label, "Unknown")
            print(f"Recognition: {name} (label={label}, distance={distance:.1f})", flush=True)
            return name, confidence_percent
        else:
            print(f"Recognition: Unknown (distance={distance:.1f} > threshold={RECOGNITION_THRESHOLD})", flush=True)
            return None, confidence_percent
            
    except Exception as e:
        print(f"Recognition error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None, 0

def get_registered_names():
    """Get list of all registered face names."""
    names = set()
    
    if os.path.exists(KNOWN_FACES_DIR):
        for name in os.listdir(KNOWN_FACES_DIR):
            if os.path.isdir(os.path.join(KNOWN_FACES_DIR, name)):
                names.add(name)
    
    return list(names)

def get_person_image_count(name):
    """Get number of images for a person."""
    person_dir = os.path.join(KNOWN_FACES_DIR, name)
    
    if os.path.exists(person_dir):
        return len([f for f in os.listdir(person_dir) 
                   if f.lower().endswith(('.jpg', '.jpeg', '.png'))])
    return 0

def delete_person(name):
    """
    Delete a registered person and their face data.
    
    Args:
        name: Name of the person to delete
    
    Returns:
        True if deleted successfully, False otherwise
    """
    import shutil
    
    person_dir = os.path.join(KNOWN_FACES_DIR, name)
    
    if not os.path.exists(person_dir):
        print(f"Person '{name}' not found", flush=True)
        return False
    
    try:
        # Remove the person's directory and all images
        shutil.rmtree(person_dir)
        print(f"Deleted person: {name}", flush=True)
        
        # Retrain model with remaining data
        remaining_names = get_registered_names()
        if remaining_names:
            train_model()
        else:
            # No data left, clear the model
            global lbph_recognizer, label_to_name, name_to_label
            lbph_recognizer = None
            label_to_name = {}
            name_to_label = {}
            # Remove model files
            if os.path.exists(MODEL_PATH):
                os.remove(MODEL_PATH)
            if os.path.exists(LABELS_PATH):
                os.remove(LABELS_PATH)
            print("No faces remaining, model cleared", flush=True)
        
        return True
    except Exception as e:
        print(f"Error deleting person: {e}", flush=True)
        return False

def get_model_info():
    """Get information about the current model state."""
    global lbph_recognizer, label_to_name
    
    return {
        'model_loaded': lbph_recognizer is not None,
        'num_people': len(label_to_name),
        'registered_names': list(label_to_name.values()) if label_to_name else []
    }

# Initialize - try to load existing model
def initialize():
    """Initialize the face recognition system."""
    if not load_model():
        # If no model exists, try to train from existing data
        train_model()

# Auto-initialize when module is imported
initialize()
