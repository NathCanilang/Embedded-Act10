"""
Face Recognition Module using KNN (K-Nearest Neighbors)

This module handles:
- Face encoding extraction using histogram-based features
- KNN-based face recognition
- Model training and persistence
"""

import cv2
import numpy as np
import os
import pickle
from sklearn.neighbors import KNeighborsClassifier

# Paths
KNOWN_FACES_DIR = "known_faces"
MODEL_PATH = "face_model.pkl"
ENCODINGS_PATH = "face_encodings.pkl"

# Face cascade for detection
face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_alt.xml")

# Global KNN model and data
knn_model = None
face_encodings = []
face_labels = []

def extract_face_encoding(face_image):
    """
    Extract face encoding using Local Binary Pattern Histogram (LBPH) features.
    This provides a compact representation of the face.
    
    Args:
        face_image: Grayscale face image (cropped)
    
    Returns:
        numpy array of face features
    """
    # Resize face to standard size
    face_resized = cv2.resize(face_image, (100, 100))
    
    # Calculate histogram of the face
    hist = cv2.calcHist([face_resized], [0], None, [256], [0, 256])
    hist = cv2.normalize(hist, hist).flatten()
    
    # Also add some structural features using HOG-like approach
    # Divide face into grid and get mean intensity
    grid_size = 10
    cell_h = face_resized.shape[0] // grid_size
    cell_w = face_resized.shape[1] // grid_size
    
    grid_features = []
    for i in range(grid_size):
        for j in range(grid_size):
            cell = face_resized[i*cell_h:(i+1)*cell_h, j*cell_w:(j+1)*cell_w]
            grid_features.append(np.mean(cell))
            grid_features.append(np.std(cell))
    
    # Combine features
    features = np.concatenate([hist, np.array(grid_features)])
    
    return features

def detect_face(frame):
    """
    Detect faces in a frame and return face regions.
    
    Args:
        frame: BGR image
    
    Returns:
        List of tuples (x, y, w, h, face_gray)
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30)
    )
    
    result = []
    for (x, y, w, h) in faces:
        face_gray = gray[y:y+h, x:x+w]
        result.append((x, y, w, h, face_gray))
    
    return result

def load_training_data():
    """
    Load all face images from known_faces directory and extract encodings.
    
    Directory structure expected:
    known_faces/
        person1/
            image1.jpg  (cropped face images)
            image2.jpg
            ...
        person2/
            image1.jpg
            ...
    """
    global face_encodings, face_labels
    
    face_encodings = []
    face_labels = []
    
    if not os.path.exists(KNOWN_FACES_DIR):
        print("Known faces directory not found")
        return False
    
    for person_name in os.listdir(KNOWN_FACES_DIR):
        person_dir = os.path.join(KNOWN_FACES_DIR, person_name)
        
        if not os.path.isdir(person_dir):
            continue
        
        print(f"Loading faces for: {person_name}")
        
        for image_name in os.listdir(person_dir):
            if not image_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            image_path = os.path.join(person_dir, image_name)
            
            try:
                # Load image
                img = cv2.imread(image_path)
                if img is None:
                    continue
                
                # Convert to grayscale
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # The images are already cropped faces, so use directly
                # No need to detect face again
                encoding = extract_face_encoding(gray)
                
                face_encodings.append(encoding)
                face_labels.append(person_name)
                    
            except Exception as e:
                print(f"Error processing {image_path}: {e}")
                continue
    
    print(f"Loaded {len(face_encodings)} face encodings for {len(set(face_labels))} people")
    return len(face_encodings) > 0

def train_model():
    """
    Train the KNN model on the loaded face data.
    """
    global knn_model
    
    if len(face_encodings) == 0:
        print("No training data available")
        return False
    
    # Convert to numpy arrays
    X = np.array(face_encodings)
    y = np.array(face_labels)
    
    # Determine n_neighbors (should be less than number of samples)
    n_neighbors = min(5, len(X))
    
    # Create and train KNN model
    knn_model = KNeighborsClassifier(
        n_neighbors=n_neighbors,
        weights='distance',
        metric='euclidean'
    )
    
    knn_model.fit(X, y)
    
    print(f"Model trained with {len(X)} samples, n_neighbors={n_neighbors}")
    
    # Save model and encodings
    save_model()
    
    return True

def save_model():
    """Save the trained model and encodings to disk."""
    global knn_model, face_encodings, face_labels
    
    try:
        # Save KNN model
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(knn_model, f)
        
        # Save encodings and labels
        with open(ENCODINGS_PATH, 'wb') as f:
            pickle.dump({
                'encodings': face_encodings,
                'labels': face_labels
            }, f)
        
        print("Model saved successfully")
        return True
    except Exception as e:
        print(f"Error saving model: {e}")
        return False

def load_model():
    """Load the trained model and encodings from disk."""
    global knn_model, face_encodings, face_labels
    
    print(f"Attempting to load model from {MODEL_PATH}...", flush=True)
    
    try:
        if os.path.exists(MODEL_PATH) and os.path.exists(ENCODINGS_PATH):
            # Load KNN model
            with open(MODEL_PATH, 'rb') as f:
                knn_model = pickle.load(f)
            
            # Load encodings and labels
            with open(ENCODINGS_PATH, 'rb') as f:
                data = pickle.load(f)
                face_encodings = data['encodings']
                face_labels = data['labels']
            
            print(f"Model loaded: {len(face_encodings)} encodings, knn_model={knn_model is not None}", flush=True)
            return True
        else:
            print(f"Model files not found: MODEL_PATH exists={os.path.exists(MODEL_PATH)}, ENCODINGS_PATH exists={os.path.exists(ENCODINGS_PATH)}", flush=True)
    except Exception as e:
        print(f"Error loading model: {e}", flush=True)
    
    return False

def recognize_face(face_gray, threshold=0.3):
    """
    Recognize a face using the trained KNN model.
    
    Args:
        face_gray: Grayscale face image (cropped)
        threshold: Confidence threshold (higher = stricter)
    
    Returns:
        Tuple (name, confidence) or (None, 0) if not recognized
    """
    global knn_model
    
    if knn_model is None:
        print("KNN model is None - not loaded", flush=True)
        return None, 0
    
    try:
        # Extract encoding
        encoding = extract_face_encoding(face_gray)
        encoding = encoding.reshape(1, -1)
        
        # Get prediction and distances
        distances, indices = knn_model.kneighbors(encoding)
        
        # Get the predicted label
        prediction = knn_model.predict(encoding)[0]
        
        # Calculate confidence (inverse of average distance)
        avg_distance = np.mean(distances[0])
        min_distance = np.min(distances[0])
        
        # Normalize confidence (lower distance = higher confidence)
        # Known faces typically have min_distance ~160-185
        # Unknown faces should have higher distances
        max_distance = 300  # For confidence calculation
        confidence = max(0, 1 - (min_distance / max_distance))
        
        print(f"Recognition: {prediction}, avg_dist={avg_distance:.2f}, min_dist={min_distance:.2f}, conf={confidence:.2f}", flush=True)
        
        # STRICT threshold: Only accept if distance is clearly a match
        # Your registered face shows ~160-185 distance
        # Set threshold at 200 to reject unknown faces
        DISTANCE_THRESHOLD = 200
        
        if min_distance < DISTANCE_THRESHOLD:
            return prediction, confidence
        else:
            print(f"  -> Rejected as Unknown (distance {min_distance:.2f} > threshold {DISTANCE_THRESHOLD})", flush=True)
            return None, confidence
            
    except Exception as e:
        print(f"Recognition error: {e}")
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
        if load_training_data():
            train_model()
        else:
            # No data left, clear the model
            global knn_model, face_encodings, face_labels
            knn_model = None
            face_encodings = []
            face_labels = []
            # Remove model files
            if os.path.exists(MODEL_PATH):
                os.remove(MODEL_PATH)
            if os.path.exists(ENCODINGS_PATH):
                os.remove(ENCODINGS_PATH)
            print("No faces remaining, model cleared", flush=True)
        
        return True
    except Exception as e:
        print(f"Error deleting person: {e}", flush=True)
        return False

# Initialize - try to load existing model
def initialize():
    """Initialize the face recognition system."""
    if not load_model():
        # If no model exists, try to train from existing data
        if load_training_data():
            train_model()

# Auto-initialize when module is imported
initialize()
