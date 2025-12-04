from flask import Flask
import os

# Import route blueprints
from routes.main import main_bp
from routes.register import register_bp

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['CAPTURES_DIR'] = 'captures'
app.config['KNOWN_FACES_DIR'] = 'known_faces'

# Ensure directories exist
for dir_name in [app.config['CAPTURES_DIR'], app.config['KNOWN_FACES_DIR']]:
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

# Register blueprints
app.register_blueprint(main_bp)
app.register_blueprint(register_bp, url_prefix='/register')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
