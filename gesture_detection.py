"""
Gesture Detection Module using MediaPipe Hands

Detects hand gestures for controlling the registration process:
- 👍 Thumbs Up: Start/continue capturing faces
- 👎 Thumbs Down: Cancel captured images
- ☝️ Index Finger (Number 1): Register another user
"""

import cv2
import mediapipe as mp
import numpy as np

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Global hand detector instance
hands_detector = None

# Gesture cooldown to prevent rapid triggers
GESTURE_COOLDOWN = 1.0  # seconds between gesture detections
last_gesture_time = 0


def get_hands_detector():
    """Get or initialize MediaPipe hands detector."""
    global hands_detector
    if hands_detector is None:
        hands_detector = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
    return hands_detector


def detect_gesture(frame):
    """
    Detect hand gesture in frame.
    
    Args:
        frame: BGR image from camera
    
    Returns:
        Tuple (gesture_name, confidence, landmarks) or (None, 0, None)
        gesture_name: 'thumbs_up', 'thumbs_down', 'one', or None
    """
    detector = get_hands_detector()
    
    # Convert BGR to RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Process frame
    results = detector.process(rgb_frame)
    
    if not results.multi_hand_landmarks:
        return None, 0, None
    
    # Get first hand detected
    hand_landmarks = results.multi_hand_landmarks[0]
    handedness = results.multi_handedness[0].classification[0]
    
    # Analyze gesture
    gesture = analyze_hand_gesture(hand_landmarks, handedness.label)
    
    return gesture, handedness.score, hand_landmarks


def analyze_hand_gesture(landmarks, handedness):
    """
    Analyze hand landmarks to determine gesture.
    
    Args:
        landmarks: MediaPipe hand landmarks
        handedness: 'Left' or 'Right'
    
    Returns:
        Gesture name: 'thumbs_up', 'thumbs_down', 'one', or None
    """
    # Get landmark positions
    lm = landmarks.landmark
    
    # Key landmark indices
    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20
    
    # Check if fingers are extended or closed
    # Thumb: compare tip x position relative to IP joint (depends on handedness)
    thumb_extended = False
    if handedness == 'Right':
        thumb_extended = lm[THUMB_TIP].x < lm[THUMB_IP].x
    else:
        thumb_extended = lm[THUMB_TIP].x > lm[THUMB_IP].x
    
    # Other fingers: tip y is above PIP y (lower y = higher on screen)
    index_extended = lm[INDEX_TIP].y < lm[INDEX_PIP].y
    middle_extended = lm[MIDDLE_TIP].y < lm[MIDDLE_PIP].y
    ring_extended = lm[RING_TIP].y < lm[RING_PIP].y
    pinky_extended = lm[PINKY_TIP].y < lm[PINKY_PIP].y
    
    # Check thumb orientation (up or down)
    thumb_pointing_up = lm[THUMB_TIP].y < lm[THUMB_MCP].y
    thumb_pointing_down = lm[THUMB_TIP].y > lm[THUMB_MCP].y
    
    # Detect gestures
    
    # 👍 Thumbs Up: Thumb extended and pointing up, other fingers closed
    if (thumb_extended and thumb_pointing_up and 
        not index_extended and not middle_extended and 
        not ring_extended and not pinky_extended):
        return 'thumbs_up'
    
    # 👎 Thumbs Down: Thumb extended and pointing down, other fingers closed
    if (thumb_extended and thumb_pointing_down and 
        not index_extended and not middle_extended and 
        not ring_extended and not pinky_extended):
        return 'thumbs_down'
    
    # ☝️ Number One: Only index finger extended
    if (index_extended and not middle_extended and 
        not ring_extended and not pinky_extended):
        return 'one'
    
    return None


def draw_hand_landmarks(frame, landmarks):
    """
    Draw hand landmarks on frame.
    
    Args:
        frame: BGR image
        landmarks: MediaPipe hand landmarks
    
    Returns:
        Frame with landmarks drawn
    """
    if landmarks is None:
        return frame
    
    mp_drawing.draw_landmarks(
        frame,
        landmarks,
        mp_hands.HAND_CONNECTIONS,
        mp_drawing_styles.get_default_hand_landmarks_style(),
        mp_drawing_styles.get_default_hand_connections_style()
    )
    
    return frame


def draw_gesture_indicator(frame, gesture, confidence=0):
    """
    Draw gesture indicator on frame.
    
    Args:
        frame: BGR image
        gesture: Gesture name or None
        confidence: Detection confidence
    
    Returns:
        Frame with gesture indicator
    """
    if gesture is None:
        return frame
    
    # Gesture display info
    gesture_info = {
        'thumbs_up': ('👍 THUMBS UP - Capturing!', (0, 255, 0)),
        'thumbs_down': ('👎 THUMBS DOWN - Cancel', (0, 0, 255)),
        'one': ('☝️ ONE - New User', (255, 165, 0))
    }
    
    if gesture in gesture_info:
        text, color = gesture_info[gesture]
        
        # Draw background rectangle
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (10, h - 60), (350, h - 10), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, h - 60), (350, h - 10), color, 2)
        
        # Draw text
        cv2.putText(frame, text, (20, h - 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    
    return frame


def release_hands_detector():
    """Release the hands detector resources."""
    global hands_detector
    if hands_detector is not None:
        hands_detector.close()
        hands_detector = None
