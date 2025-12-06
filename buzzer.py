"""
Buzzer Module - Handles GPIO buzzer for alert notifications

- Buzzer connected to GPIO 23
- Activates when an unregistered face is detected
- Only works on Raspberry Pi, silently skips on Windows
"""

import platform
import threading
import time

# Detect operating system
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

# GPIO setup
GPIO_AVAILABLE = False
BUZZER_PIN = 23

if IS_RASPBERRY_PI:
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
    print(f"Not running on Raspberry Pi - buzzer simulation mode", flush=True)

# Buzzer state
buzzer_active = False
buzzer_lock = threading.Lock()
last_buzz_time = 0
BUZZ_COOLDOWN = 2.0  # Minimum seconds between buzzes


def activate_buzzer(duration=0.5):
    """
    Activate the buzzer for a specified duration.
    
    Args:
        duration: How long to buzz in seconds (default 0.5)
    """
    global buzzer_active, last_buzz_time
    
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
            else:
                # Simulation mode - just print
                print(f"🔔 BUZZER: Unknown face detected! (simulated {duration}s buzz)", flush=True)
                time.sleep(duration)
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
        'buzzer_pin': BUZZER_PIN,
        'simulation_mode': not GPIO_AVAILABLE
    }
