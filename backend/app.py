from flask import Flask, request, jsonify, url_for, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import logging
import random
import threading
import time
import qrcode
import io
import base64
# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='../frontend', static_folder='../frontend')

# Replace the current CORS setup with:
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://swachh-doot-2-o.onrender.com",
            "http://localhost:3000",
            "http://127.0.0.1:3000"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
}) # Enable CORS for all routes

import os
from flask_sqlalchemy import SQLAlchemy


@app.route('/')
def home():
    return render_template('index.html')

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found", "status": "error"}), 404

# Use environment variable for database URL with fallback
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///database.db').replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Add connection pool settings for production
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
    'pool_size': 10,
    'max_overflow': 20,
}
db = SQLAlchemy(app)

# Define Models
class SmartBin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(100), nullable=False)
    fill_level = db.Column(db.Float, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    name = db.Column(db.String(100), nullable=True)  # Add name field for better identification
    
    def to_dict(self):
        return {
            'id': self.id,
            'location': self.location,
            'fill_level': round(self.fill_level, 0),  # Always return whole number
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'name': self.name
        }

class LitterAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, default=0)
    image_url = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(500))
    
    def to_dict(self):
        return {
            'id': self.id,
            'location': self.location,
            'confidence': self.confidence,
            'image_url': self.image_url,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'description': self.description
        }
class QRComplaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bin_id = db.Column(db.Integer, db.ForeignKey('smart_bin.id'), nullable=False)
    complaint_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(500))
    image_url = db.Column(db.String(200))
    location = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, resolved, in_progress
    citizen_contact = db.Column(db.String(100))  # Optional contact info
    
    def to_dict(self):
        return {
            'id': self.id,
            'bin_id': self.bin_id,
            'complaint_type': self.complaint_type,
            'description': self.description,
            'image_url': self.image_url,
            'location': self.location,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'status': self.status,
            'citizen_contact': self.citizen_contact
        }

# Simulated bin locations around Rohini Sector-13 with names
SIMULATED_BINS = [
    {"id": 2, "location": "28.7415,77.1220", "name": "Sector-13 Park"},
    {"id": 3, "location": "28.7390,77.1245", "name": "Community Center"},
    {"id": 4, "location": "28.7385,77.1210", "name": "Market Area"},
    {"id": 5, "location": "28.7420,77.1250", "name": "School Road"},
    {"id": 6, "location": "28.7365,77.1235", "name": "Residential Block A"},
    {"id": 7, "location": "28.7430,77.1205", "name": "Residential Block B"},
    {"id": 8, "location": "28.7370,77.1260", "name": "Shopping Complex"},
    {"id": 9, "location": "28.7440,77.1240", "name": "Main Road"}
]

def initialize_database():
    """Initialize database with real and simulated bins"""
    with app.app_context():
        try:
            db.create_all()
            
            # Create the real bin at Bharat Apartment
            if not SmartBin.query.get(1):
                real_bin = SmartBin(
                    id=1,
                    location="28.7402,77.1234",
                    fill_level=0,
                    name="Bharat Apartment",
                    last_updated=datetime.utcnow()
                )
                db.session.add(real_bin)
                logger.info("Created initial bin #1 at Bharat Apartment")
            
            # Create simulated bins
            for bin_data in SIMULATED_BINS:
                if not SmartBin.query.get(bin_data["id"]):
                    simulated_bin = SmartBin(
                        id=bin_data["id"],
                        location=bin_data["location"],
                        fill_level=random.randint(10, 90),  # Random initial fill level
                        name=bin_data["name"],
                        last_updated=datetime.utcnow() - timedelta(hours=random.randint(1, 24))
                    )
                    db.session.add(simulated_bin)
                    logger.info(f"Created simulated bin #{bin_data['id']} at {bin_data['name']}")
            
            db.session.commit()
            logger.info("Database initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Error in database initialization: {e}")
            db.session.rollback()
            # Don't raise the exception, just log it

def update_simulated_bins():
    """Update fill levels of simulated bins randomly"""
    with app.app_context():
        try:
            simulated_bins = SmartBin.query.filter(SmartBin.id > 1).all()
            for bin in simulated_bins:
                # Random change between -15% and +20%
                change = random.randint(-5, 5)
                new_level = max(0, min(100, int(round(bin.fill_level + change))))
                
                if new_level != bin.fill_level:
                    bin.fill_level = new_level
                    bin.last_updated = datetime.utcnow()
                    logger.debug(f"Updated simulated bin #{bin.id} ({bin.name}) to {new_level}%")
            
            db.session.commit()
            logger.info(f"Updated {len(simulated_bins)} simulated bins")
        except Exception as e:
            logger.error(f"Error updating simulated bins: {e}")
            db.session.rollback()

def simulated_bin_updater():
    """Background thread to update simulated bins periodically"""
    while True:
        try:
            update_simulated_bins()
            # Update every 30-60 seconds
            time.sleep(random.randint(30, 60))
        except Exception as e:
            logger.error(f"Error in simulated bin updater: {e}")
            time.sleep(60)  # Wait longer if there's an error

# Initialize the database
initialize_database()

# Start background thread for simulated bin updates
bin_updater_thread = threading.Thread(target=simulated_bin_updater, daemon=True)
bin_updater_thread.start()
logger.info("Started simulated bin updater thread")

# --- Middleware ---
@app.before_request
def before_request():
    logger.debug(f"Request: {request.method} {request.url}")

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# --- API ROUTES ---

# Get all data for the dashboard
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    try:
        bins = SmartBin.query.order_by(SmartBin.id).all()
        alerts = LitterAlert.query.order_by(LitterAlert.timestamp.desc()).limit(10).all()
        
        logger.info(f"Dashboard requested - {len(bins)} bins, {len(alerts)} alerts")
        
        return jsonify({
            'bins': [bin.to_dict() for bin in bins],
            'alerts': [alert.to_dict() for alert in alerts],
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat(),
            'total_bins': len(bins),
            'total_alerts': len(alerts)
        })
    except Exception as e:
        logger.error(f"Error in get_dashboard_data: {e}")
        return jsonify({'error': 'Internal server error', 'status': 'error'}), 500
 
# Update a bin's fill level (This will be called by the ESP32)
@app.route('/api/bin/<int:bin_id>', methods=['POST'])
def update_bin_level(bin_id):
    try:
        # Debug logging
        print(f"=== ARDUINO REQUEST RECEIVED ===")
        print(f"Remote IP: {request.remote_addr}")
        print(f"Headers: {dict(request.headers)}")
        
        data = request.get_json()
        if not data:
            print("ERROR: No JSON data received")
            logger.warning(f"No JSON data received for bin {bin_id}")
            return jsonify({'error': 'No data provided', 'status': 'error'}), 400
        
        print(f"Received data: {data}")
        logger.debug(f"Received data for bin {bin_id}: {data}")
        
        bin = SmartBin.query.get(bin_id)
        if bin:
            fill_level = data.get('fill_level')
            if fill_level is None:
                print("ERROR: fill_level field missing")
                return jsonify({'error': 'fill_level field required', 'status': 'error'}), 400
            
            try:
                fill_level = float(fill_level)
                if not (0 <= fill_level <= 100):
                    print(f"ERROR: fill_level out of range: {fill_level}")
                    return jsonify({'error': 'fill_level must be between 0 and 100', 'status': 'error'}), 400
            except (ValueError, TypeError):
                print(f"ERROR: fill_level not a number: {fill_level}")
                return jsonify({'error': 'fill_level must be a number', 'status': 'error'}), 400
            
            bin.fill_level = fill_level
            bin.last_updated = datetime.utcnow()
            db.session.commit()
            
            print(f"SUCCESS: Updated bin {bin_id} to {fill_level}%")
            logger.info(f"Updated bin {bin_id} to {fill_level}%")
            
            return jsonify({
                'message': 'Bin updated successfully', 
                'status': 'success',
                'bin_id': bin_id,
                'fill_level': fill_level,
                'bin_name': bin.name
            })
        
        print(f"ERROR: Bin {bin_id} not found")
        logger.warning(f"Bin {bin_id} not found")
        return jsonify({'error': 'Bin not found', 'status': 'error'}), 404
        
    except Exception as e:
        print(f"EXCEPTION: {e}")
        logger.error(f"Error updating bin {bin_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error', 'status': 'error'}), 500

# Debug endpoint for testing Arduino connectivity
@app.route('/api/debug/arduino', methods=['POST'])
def debug_arduino():
    """Debug endpoint for Arduino data"""
    print(f"=== DEBUG ARDUINO REQUEST ===")
    print(f"Remote IP: {request.remote_addr}")
    print(f"Headers: {dict(request.headers)}")
    print(f"Data: {request.get_json()}")
    print("=" * 40)
    
    return jsonify({
        'status': 'success',
        'message': 'Debug data received',
        'your_ip': request.remote_addr,
        'timestamp': datetime.utcnow().isoformat()
    })

# Test connection endpoint
@app.route('/api/test/connection', methods=['GET'])
def test_connection():
    """Simple test endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'Server is reachable!',
        'server_time': datetime.utcnow().isoformat()
    })
@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all unhandled exceptions"""
    logger.error(f"Unhandled exception: {str(e)}")
    return jsonify({
        'error': 'Internal server error',
        'status': 'error',
        'message': 'Something went wrong on our end'
    }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Endpoint not found',
        'status': 'error'
    }), 404
# Create a new litter alert
@app.route('/api/alert', methods=['POST'])
def create_litter_alert():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided', 'status': 'error'}), 400
        
        location = data.get('location')
        if not location:
            return jsonify({'error': 'Location is required', 'status': 'error'}), 400
        
        new_alert = LitterAlert(
            location=location,
            confidence=data.get('confidence', 0.0),
            image_url=data.get('image_url', ''),
            description=data.get('description', ''),
            timestamp=datetime.utcnow()
        )
        db.session.add(new_alert)
        db.session.commit()
        
        logger.info(f"Created new alert at {location}")
        return jsonify({
            'message': 'Alert created successfully', 
            'status': 'success',
            'alert_id': new_alert.id
        })
        
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error', 'status': 'error'}), 500

# Get bin by ID
@app.route('/api/bin/<int:bin_id>', methods=['GET'])
def get_bin(bin_id):
    try:
        bin = SmartBin.query.get(bin_id)
        if bin:
            return jsonify({
                'status': 'success',
                'bin': bin.to_dict()
            })
        return jsonify({'error': 'Bin not found', 'status': 'error'}), 404
    except Exception as e:
        logger.error(f"Error getting bin {bin_id}: {e}")
        return jsonify({'error': 'Internal server error', 'status': 'error'}), 500

# Get all bins
@app.route('/api/bins', methods=['GET'])
def get_all_bins():
    try:
        bins = SmartBin.query.order_by(SmartBin.id).all()
        return jsonify({
            'status': 'success',
            'bins': [bin.to_dict() for bin in bins],
            'count': len(bins)
        })
    except Exception as e:
        logger.error(f"Error getting all bins: {e}")
        return jsonify({'error': 'Internal server error', 'status': 'error'}), 500

# Clear all alerts
@app.route('/api/alerts/clear', methods=['DELETE'])
def clear_all_alerts():
    try:
        # Delete all alerts from database
        deleted_count = LitterAlert.query.delete()
        db.session.commit()
        
        logger.info(f"Cleared {deleted_count} alerts")
        return jsonify({
            'message': f'All alerts cleared successfully', 
            'status': 'success',
            'deleted_count': deleted_count
        })
    except Exception as e:
        logger.error(f"Error clearing alerts: {e}")
        db.session.rollback()
        return jsonify({'error': str(e), 'status': 'error'}), 500

# Get optimized routes
@app.route('/api/optimize-routes', methods=['GET'])
def optimize_routes():
    try:
        bins = SmartBin.query.all()
        alerts = LitterAlert.query.all()
        
        # Simple optimization logic - group by area and prioritize full bins
        full_bins = [bin for bin in bins if bin.fill_level > 80]
        medium_bins = [bin for bin in bins if 50 <= bin.fill_level <= 80]
        alerts_list = [alert for alert in alerts]
        
        # Calculate efficiency gain (simplified)
        efficiency_gain = min(50, len(full_bins) * 5 + len(alerts_list) * 3)
        
        return jsonify({
            'efficiency_gain': efficiency_gain,
            'priority_bins': len(full_bins),
            'alerts_to_clear': len(alerts_list),
            'total_bins': len(bins),
            'suggested_route': f'Start → {len(full_bins)} full bins → {len(alerts_list)} alerts',
            'status': 'success'
        })
    except Exception as e:
        logger.error(f"Error optimizing routes: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

# Generate PDF report
@app.route('/api/generate-report', methods=['GET'])
def generate_report():
    try:
        bins = SmartBin.query.all()
        alerts = LitterAlert.query.all()
        
        report_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_bins': len(bins),
            'total_alerts': len(alerts),
            'average_fill_level': sum(bin.fill_level for bin in bins) / len(bins) if bins else 0,
            'full_bins': len([bin for bin in bins if bin.fill_level > 80]),
            'co2_reduction': min(100, len(bins) * 3 + len(alerts) * 2),
            'bins': [bin.to_dict() for bin in bins],
            'alerts': [alert.to_dict() for alert in alerts],
            'status': 'success'
        }
        
        logger.info("Generated PDF report data")
        return jsonify(report_data)
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        # Test database connection
        bin_count = SmartBin.query.count()
        alert_count = LitterAlert.query.count()
        simulated_bins = SmartBin.query.filter(SmartBin.id > 1).count()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'bin_count': bin_count,
            'simulated_bins': simulated_bins,
            'alert_count': alert_count,
            'timestamp': datetime.utcnow().isoformat(),
            'server_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500
# Generate QR Code for specific bin
@app.route('/api/bin/<int:bin_id>/qr', methods=['GET'])
# Add this function to generate permanent QR codes (PUT THIS AFTER THE MODELS)
def generate_permanent_qr_code(bin_id, bin_name, bin_location):
    """Generate permanent QR code with actual complaint form URL"""
    try:
        # Clean the data to avoid any encoding issues
        clean_bin_name = bin_name.replace(':', '-') if bin_name else f"Bin-{bin_id}"
        clean_location = bin_location.replace(':', '-') if bin_location else "Unknown-Location"
        
        # ✅ FIX: Create actual URL that redirects to complaint form
        base_url = "https://swachh-doot-2-o.onrender.com"
        complaint_url = f"{base_url}/complaint?bin_id={bin_id}&name={clean_bin_name}&location={clean_location}"
        
        # Use the actual URL as QR data (this will open the complaint form directly)
        qr_data = complaint_url
        
        print(f"Generating QR for: {qr_data}")  # Debug log
        
        # Check if PIL is available
        try:
            import PIL
            # Generate QR code with error handling
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=8,
                border=2,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True)
            buffer.seek(0)
            
            img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            print(f"✅ QR generated successfully for bin {bin_id}")
            return img_str, qr_data
            
        except ImportError:
            # PIL is not available, use SVG placeholder
            print(f"⚠️ PIL not available, using SVG placeholder for bin {bin_id}")
            return generate_svg_placeholder(qr_data, bin_id, clean_bin_name), qr_data
        
    except Exception as e:
        logger.error(f"Error in generate_permanent_qr_code for bin {bin_id}: {e}")
        # Fallback to simple URL
        base_url = "https://swachh-doot-2-o.onrender.com"
        fallback_url = f"{base_url}/complaint?bin_id={bin_id}"
        return generate_svg_placeholder(fallback_url, bin_id, bin_name), fallback_url

def generate_svg_placeholder(qr_data, bin_id, bin_name):
    """Generate an SVG placeholder when PIL is not available"""
    # Create a simple SVG placeholder that shows it's clickable
    svg_content = f'''<svg width="140" height="140" viewBox="0 0 140 140" xmlns="http://www.w3.org/2000/svg">
        <rect width="140" height="140" fill="#f8f9fa" stroke="#3498db" stroke-width="2" rx="8"/>
        <text x="70" y="30" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#2c3e50" font-weight="bold">SCAN ME</text>
        <text x="70" y="50" text-anchor="middle" font-family="Arial, sans-serif" font-size="10" fill="#666">{bin_name}</text>
        <text x="70" y="65" text-anchor="middle" font-family="Arial, sans-serif" font-size="8" fill="#999">Bin ID: {bin_id}</text>
        <rect x="35" y="75" width="70" height="30" fill="#3498db" rx="4"/>
        <text x="70" y="95" text-anchor="middle" font-family="Arial, sans-serif" font-size="9" fill="white">Report Issue</text>
        <text x="70" y="115" text-anchor="middle" font-family="Arial, sans-serif" font-size="6" fill="#999">Tap to open form</text>
    </svg>'''
    
    # Convert SVG to data URL
    svg_bytes = svg_content.encode('utf-8')
    svg_data_url = f"data:image/svg+xml;base64,{base64.b64encode(svg_bytes).decode('utf-8')}"
    
    return svg_data_url
# Add this simple QR codes endpoint BEFORE the get_all_qr_codes endpoint
@app.route('/api/bins/simple-qr-codes', methods=['GET'])
def get_simple_qr_codes():
    """Simplified endpoint that returns bin info without QR codes"""
    try:
        bins = SmartBin.query.all()
        
        simple_qr_data = []
        for bin in bins:
            # Just return the data needed to generate QR codes on frontend
            qr_data = f"eco-guardian:bin:{bin.id}:{bin.name or f'Bin {bin.id}'}:{bin.location}"
            
            simple_qr_data.append({
                'bin_id': bin.id,
                'bin_name': bin.name,
                'location': bin.location,
                'qr_data': qr_data,
                'fill_level': bin.fill_level
            })
        
        return jsonify({
            'status': 'success',
            'bins': simple_qr_data,
            'count': len(simple_qr_data)
        })
        
    except Exception as e:
        logger.error(f"Error in get_simple_qr_codes: {e}")
        return jsonify({'error': 'Internal server error'}), 500
# Add endpoint to get all permanent QR codes at once (ADD THIS NEW ENDPOINT)
@app.route('/api/bins/qr-codes', methods=['GET'])
def get_all_qr_codes():
    try:
        print("=== GET ALL QR CODES START ===")
        
        bins = SmartBin.query.all()
        print(f"Found {len(bins)} bins in database")
        
        if not bins:
            return jsonify({
                'status': 'success',
                'qr_codes': [],
                'count': 0,
                'message': 'No bins found'
            })
        
        qr_codes = []
        successful = 0
        failed = 0
        
        for bin in bins:
            try:
                print(f"Generating QR for bin {bin.id}: {bin.name}")
                
                qr_image, qr_data = generate_permanent_qr_code(
                    bin_id=bin.id,
                    bin_name=bin.name or f"Bin {bin.id}",
                    bin_location=bin.location
                )
                
                qr_codes.append({
                    'bin_id': bin.id,
                    'bin_name': bin.name,
                    'location': bin.location,
                    'qr_code': f"data:image/png;base64,{qr_image}",
                    'qr_data': qr_data
                })
                successful += 1
                print(f"✅ Successfully generated QR for bin {bin.id}")
                
            except Exception as e:
                failed += 1
                logger.error(f"Failed to generate QR for bin {bin.id}: {e}")
                print(f"❌ Failed to generate QR for bin {bin.id}: {e}")
                # Continue with next bin instead of failing completely
        
        print(f"=== QR GENERATION COMPLETE: {successful} successful, {failed} failed ===")
        
        return jsonify({
            'status': 'success',
            'qr_codes': qr_codes,
            'count': len(qr_codes),
            'successful': successful,
            'failed': failed,
            'permanent': True
        })
        
    except Exception as e:
        logger.error(f"Error in get_all_qr_codes: {e}")
        print(f"❌ CRITICAL ERROR in get_all_qr_codes: {e}")
        return jsonify({
            'error': 'Internal server error',
            'details': str(e)
        }), 500
@app.route('/api/debug/qr-error', methods=['GET'])
def debug_qr_error():
    """Debug endpoint to identify QR code generation issue"""
    try:
        print("=== QR DEBUG START ===")
        
        # Test 1: Check if bins exist
        bins = SmartBin.query.all()
        print(f"Found {len(bins)} bins")
        
        # Test 2: Check if we can generate a single QR code
        if bins:
            test_bin = bins[0]
            print(f"Testing with bin: {test_bin.id}, {test_bin.name}")
            
            try:
                qr_image, qr_data = generate_permanent_qr_code(
                    bin_id=test_bin.id,
                    bin_name=test_bin.name or f"Bin {test_bin.id}",
                    bin_location=test_bin.location
                )
                print("✅ QR generation successful")
                return jsonify({
                    'status': 'success',
                    'message': 'QR generation works',
                    'test_bin': test_bin.to_dict()
                })
            except Exception as e:
                print(f"❌ QR generation failed: {e}")
                return jsonify({'error': f'QR generation failed: {str(e)}'}), 500
        else:
            return jsonify({'error': 'No bins found'}), 404
            
    except Exception as e:
        print(f"❌ Debug endpoint failed: {e}")
        return jsonify({'error': f'Debug failed: {str(e)}'}), 500    
# Quick complaint endpoint via QR scan
@app.route('/api/complaint/quick', methods=['POST'])
def quick_complaint():
    try:
        data = request.get_json()
        
        # Required fields from QR code
        bin_id = data.get('bin_id')
        complaint_type = data.get('complaint_type', 'other')
        description = data.get('description', '')
        
        if not bin_id:
            return jsonify({'error': 'Bin ID is required'}), 400
        
        # Get bin info
        bin = SmartBin.query.get(bin_id)
        if not bin:
            return jsonify({'error': 'Bin not found'}), 404
        
        # Create complaint
        complaint = QRComplaint(
            bin_id=bin_id,
            complaint_type=complaint_type,
            description=description,
            location=bin.location,
            citizen_contact=data.get('citizen_contact', ''),
            timestamp=datetime.utcnow()
        )
        
        db.session.add(complaint)
        db.session.commit()
        
        # Also create an alert for this complaint
        alert = LitterAlert(
            location=bin.location,
            confidence=0.9,
            description=f"Citizen complaint: {complaint_type} - {description}",
            timestamp=datetime.utcnow()
        )
        db.session.add(alert)
        db.session.commit()
        
        logger.info(f"Quick complaint created for bin {bin_id}: {complaint_type}")
        
        return jsonify({
            'status': 'success',
            'message': 'Complaint submitted successfully',
            'complaint_id': complaint.id,
            'bin_name': bin.name
        })
        
    except Exception as e:
        logger.error(f"Error creating quick complaint: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

# Get all QR complaints
@app.route('/api/complaints', methods=['GET'])
def get_complaints():
    try:
        complaints = QRComplaint.query.order_by(QRComplaint.timestamp.desc()).all()
        return jsonify({
            'status': 'success',
            'complaints': [complaint.to_dict() for complaint in complaints],
            'count': len(complaints)
        })
    except Exception as e:
        logger.error(f"Error getting complaints: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Update complaint status
@app.route('/api/complaint/<int:complaint_id>', methods=['PUT'])
def update_complaint(complaint_id):
    try:
        data = request.get_json()
        complaint = QRComplaint.query.get(complaint_id)
        
        if not complaint:
            return jsonify({'error': 'Complaint not found'}), 404
        
        if 'status' in data:
            complaint.status = data['status']
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Complaint updated successfully',
            'complaint': complaint.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating complaint: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

# QR Complaint Form Route
# QR Complaint Form Route - Updated for permanent QR codes (REPLACE THE EXISTING ONE)
@app.route('/complaint')
def complaint_form():
    """Serve a simple complaint form when permanent QR is scanned"""
    # Get data from permanent QR code format: eco-guardian:bin:1:Bharat Apartment:28.7402,77.1234
    qr_data = request.args.get('qr_data', '')
    
    if qr_data:
        # Parse permanent QR code data
        parts = qr_data.split(':')
        if len(parts) >= 5 and parts[0] == 'eco-guardian' and parts[1] == 'bin':
            bin_id = parts[2]
            bin_name = parts[3]
            bin_location = ':'.join(parts[4:])  # Handle locations with colons
        else:
            # Fallback to old format
            bin_id = request.args.get('bin_id', 'Unknown')
            bin_location = request.args.get('location', 'Unknown location')
            bin_name = request.args.get('name', f'Bin #{bin_id}')
    else:
        # Fallback to old parameters
        bin_id = request.args.get('bin_id', 'Unknown')
        bin_location = request.args.get('location', 'Unknown location')
        bin_name = request.args.get('name', f'Bin #{bin_id}')
    
    # Get current server IP for API calls (this can change, but QR code doesn't)
    current_server_ip = request.host
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Report Bin Issue - Swachh Doot</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ 
                font-family: Arial, sans-serif; 
                max-width: 500px; 
                margin: 0 auto; 
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                background: white;
                padding: 2rem;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }}
            .form-group {{ margin-bottom: 20px; }}
            label {{ display: block; margin-bottom: 8px; font-weight: bold; color: #333; }}
            input, select, textarea {{ 
                width: 100%; 
                padding: 12px; 
                border: 2px solid #ddd; 
                border-radius: 8px;
                font-size: 16px;
            }}
            button {{ 
                background: linear-gradient(135deg, #2ecc71, #27ae60);
                color: white; 
                padding: 15px; 
                border: none; 
                border-radius: 8px; 
                cursor: pointer; 
                width: 100%;
                font-size: 18px;
                font-weight: bold;
            }}
            .bin-info {{ 
                background: #f8f9fa; 
                padding: 15px; 
                border-radius: 10px; 
                margin-bottom: 25px;
                border-left: 4px solid #2ecc71;
            }}
            .success {{ 
                background: #2ecc71; 
                color: white; 
                padding: 15px; 
                border-radius: 8px; 
                text-align: center; 
                display: none;
                margin-top: 20px;
            }}
            .permanent-badge {{
                background: #3498db;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.8rem;
                margin-left: 10px;
            }}
            h2 {{ color: #2c3e50; text-align: center; margin-bottom: 25px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🚮 Report Bin Issue <span class="permanent-badge">Permanent QR</span></h2>
            
            <div class="bin-info">
                <strong>📦 Bin: {bin_name}</strong><br>
                🗺️ Location: {bin_location}<br>
                🔢 Bin ID: {bin_id}
            </div>
            
            <form id="complaintForm">
                <div class="form-group">
                    <label>📋 Issue Type:</label>
                    <select name="complaint_type" required>
                        <option value="">Select issue type</option>
                        <option value="overflowing">🚨 Overflowing Bin</option>
                        <option value="damaged">⚡ Damaged Bin</option>
                        <option value="missing">❌ Missing Bin</option>
                        <option value="odor">👃 Bad Odor</option>
                        <option value="pests">🐀 Pests Around Bin</option>
                        <option value="other">❓ Other Issue</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label>📝 Description (optional):</label>
                    <textarea name="description" rows="4" placeholder="Please describe the issue in detail..."></textarea>
                </div>
                
                <div class="form-group">
                    <label>📞 Contact Info (optional):</label>
                    <input type="text" name="citizen_contact" placeholder="Email or phone for updates">
                </div>
                
                <button type="submit">📤 Submit Complaint</button>
            </form>
            
            <div class="success" id="successMessage">
                ✅ Complaint submitted successfully! Thank you for keeping our city clean. 🎉
            </div>
        </div>
        
        <script>
            document.getElementById('complaintForm').addEventListener('submit', async function(e) {{
                e.preventDefault();
                
                const formData = new FormData(this);
                const complaintData = {{
                    bin_id: '{bin_id}',
                    complaint_type: formData.get('complaint_type'),
                    description: formData.get('description'),
                    citizen_contact: formData.get('citizen_contact')
                }};
                
                try {{
                    // Use current server location - this can change but QR code doesn't
                    const response = await fetch('http://{current_server_ip}/api/complaint/quick', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify(complaintData)
                    }});
                    
                    if (response.ok) {{
                        document.getElementById('complaintForm').style.display = 'none';
                        document.getElementById('successMessage').style.display = 'block';
                    }} else {{
                        alert('Failed to submit complaint. Please try again.');
                    }}
                }} catch (error) {{
                    alert('Network error. Please check your internet connection and try again.');
                }}
            }});
        </script>
    </body>
    </html>
    '''
# Add this endpoint to resolve/delete alerts
@app.route('/api/alert/<int:alert_id>', methods=['DELETE'])
def resolve_alert(alert_id):
    try:
        alert = LitterAlert.query.get(alert_id)
        if not alert:
            return jsonify({'error': 'Alert not found', 'status': 'error'}), 404
        
        # Delete the alert from database
        db.session.delete(alert)
        db.session.commit()
        
        logger.info(f"Alert {alert_id} resolved and deleted")
        return jsonify({
            'message': 'Alert resolved successfully', 
            'status': 'success',
            'alert_id': alert_id
        })
        
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error', 'status': 'error'}), 500
# Manual trigger to update simulated bins
@app.route('/api/update-simulated-bins', methods=['POST'])
def manual_update_simulated_bins():
    try:
        update_simulated_bins()
        return jsonify({
            'status': 'success',
            'message': 'Simulated bins updated successfully'
        })
    except Exception as e:
        logger.error(f"Error in manual update: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Endpoint not found', 'status': 'error'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error', 'status': 'error'}), 500

if __name__ == '__main__':
    logger.info("Starting Flask server...")
    print("=" * 50)
    print("Eco-Guardian Server")
    print("=" * 50)
    print("Starting on: http://192.168.2.100:5000")
    print("Available endpoints:")
    print("  GET  /api/dashboard     - Get all data")
    print("  POST /api/bin/<id>      - Update bin level (for Arduino)")
    print("  GET  /api/bins          - Get all bins")
    print("  GET  /api/bin/<id>      - Get specific bin")
    print("  GET  /api/health        - Health check")
    print("  POST /api/alert         - Create alert")
    print("  POST /api/update-simulated-bins - Manual update")
    print("  GET  /api/test/connection - Test connection")
    print("  POST /api/debug/arduino - Debug Arduino data")
    print("=" * 50)
    
    # Display initial bin status
    with app.app_context():
        bins = SmartBin.query.order_by(SmartBin.id).all()
        print(f"Initialized {len(bins)} bins:")
        for bin in bins:
            print(f"  Bin #{bin.id}: {bin.name or 'No name'} - {bin.fill_level}% full")
    
app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)