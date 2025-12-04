from flask import Blueprint, render_template, Response, jsonify
from camera import generate_frames_with_detection, release_camera
from face_detection import load_training_data, train_model, load_model, get_registered_names, knn_model

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Main page - Face detection view"""
    return render_template('main/index.html')

@main_bp.route('/video_feed')
def video_feed():
    """Video streaming route with face detection"""
    return Response(generate_frames_with_detection(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@main_bp.route('/reload_model', methods=['POST'])
def reload_model():
    """Reload the face recognition model"""
    try:
        # First try to load from file
        if load_model():
            return jsonify({'success': True, 'message': 'Model reloaded from file'})
        
        # If no saved model, retrain
        if load_training_data():
            train_model()
            return jsonify({'success': True, 'message': 'Model retrained'})
        
        return jsonify({'success': False, 'error': 'No training data available'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/model_status')
def model_status():
    """Check the status of the face recognition model"""
    from face_detection import knn_model, face_encodings, face_labels
    
    return jsonify({
        'model_loaded': knn_model is not None,
        'num_encodings': len(face_encodings),
        'registered_names': get_registered_names(),
        'labels': list(set(face_labels)) if face_labels else []
    })

@main_bp.route('/close_cam')
def close_cam():
    release_camera()
    return "Camera Closed", 200
