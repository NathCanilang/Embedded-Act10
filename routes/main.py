from flask import Blueprint, render_template, Response, jsonify, request
from camera import generate_frames_with_detection, release_camera, get_detection_events, clear_detection_events
from face_detection import train_model, load_model, get_registered_names, get_model_info
from buzzer import get_buzzer_status

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
        if train_model():
            return jsonify({'success': True, 'message': 'Model retrained'})
        
        return jsonify({'success': False, 'error': 'No training data available'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/model_status')
def model_status():
    """Check the status of the face recognition model"""
    info = get_model_info()
    
    return jsonify({
        'model_loaded': info['model_loaded'],
        'num_people': info['num_people'],
        'num_encodings': info['num_people'],  # For compatibility
        'registered_names': info['registered_names']
    })

@main_bp.route('/close_cam')
def close_cam():
    release_camera()
    return "Camera Closed", 200


@main_bp.route('/detection_events')
def detection_events():
    """Get recent detection events for notifications."""
    since = request.args.get('since', 0, type=float)
    events = get_detection_events(since)
    return jsonify({
        'events': events,
        'count': len(events)
    })


@main_bp.route('/clear_events', methods=['POST'])
def clear_events():
    """Clear all detection events."""
    clear_detection_events()
    return jsonify({'success': True})


@main_bp.route('/buzzer_status')
def buzzer_status():
    """Get buzzer configuration status."""
    return jsonify(get_buzzer_status())
