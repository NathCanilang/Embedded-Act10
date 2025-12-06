"""
Buzzer Module - Handles GPIO buzzer for alert notifications

- Buzzer connected to GPIO 23
- Activates when an unregistered face is detected
- Only works on Linux/Raspberry Pi, completely disabled on Windows
"""

import platform
import threading
import time

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

# GPIO setup - ONLY on Linux/Raspberry Pi
GPIO_AVAILABLE = False
BUZZER_PIN = 23
BUZZER_ENABLED = IS_LINUX  # Only enable buzzer functionality on Linux

if IS_LINUX:
    try:
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        GPIO_AVAILABLE = True
        print(f"Buzzer initialized on GPIO {BUZZER_PIN}", flush=True)
    except ImportError:
        print("RPi.GPIO not available - buzzer disabled", flush=True)
    except Exception as e:
        print(f"Failed to initialize GPIO: {e}", flush=True)
else:
    # Windows - buzzer completely disabled, no simulation
    print(f"Running on {platform.system()} - buzzer disabled (Linux/RPi only)", flush=True)

# Buzzer state
buzzer_active = False
buzzer_lock = threading.Lock()
last_buzz_time = 0
BUZZ_COOLDOWN = 2.0  # Minimum seconds between buzzes


def activate_buzzer(duration=0.5):
    """
    Activate the buzzer for a specified duration.
    Only works on Linux/Raspberry Pi - silently does nothing on Windows.
    
    Args:
        duration: How long to buzz in seconds (default 0.5)
    
    Returns:
        True if buzzer was activated, False otherwise
    """
    global buzzer_active, last_buzz_time
    
    # Skip entirely on non-Linux systems
    if not BUZZER_ENABLED:
        return False
    
    current_time = time.time()
    
    # Check cooldown to prevent rapid buzzing
    with buzzer_lock:
        if current_time - last_buzz_time < BUZZ_COOLDOWN:
            return False
        
        if buzzer_active:
            return False
        
        buzzer_active = True
        last_buzz_time = current_time
    
    def buzz():
        global buzzer_active
        try:
            if GPIO_AVAILABLE:
                GPIO.output(BUZZER_PIN, GPIO.HIGH)
                time.sleep(duration)
                GPIO.output(BUZZER_PIN, GPIO.LOW)
                print(f"🔔 BUZZER: Alert triggered ({duration}s)", flush=True)
        finally:
            with buzzer_lock:
                buzzer_active = False
    
    # Run buzzer in background thread to not block video feed
    thread = threading.Thread(target=buzz, daemon=True)
    thread.start()
    return True


def deactivate_buzzer():
    """Manually turn off the buzzer."""
    if GPIO_AVAILABLE:
        GPIO.output(BUZZER_PIN, GPIO.LOW)


def cleanup():
    """Clean up GPIO resources."""
    if GPIO_AVAILABLE:
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        GPIO.cleanup(BUZZER_PIN)
        print("Buzzer GPIO cleaned up", flush=True)


def get_buzzer_status():
    """Get the current buzzer configuration status."""
    return {
        'gpio_available': GPIO_AVAILABLE,
        'is_raspberry_pi': IS_RASPBERRY_PI,
        'is_linux': IS_LINUX,
        'buzzer_enabled': BUZZER_ENABLED,
        'buzzer_pin': BUZZER_PIN,
        'platform': platform.system()
    }
