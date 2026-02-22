from flask import Flask, render_template, request, redirect, flash, session, url_for, jsonify
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import pickle
import re
import os
import numpy as np
import time
import threading
import webbrowser
from datetime import datetime
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# MongoDB Configuration
app.config["MONGO_URI"] = "mongodb://localhost:27017/agrisense"
mongo = PyMongo(app)

# Load ML Model
try:
    with open('trained_model.pkl', 'rb') as f:
        model = pickle.load(f)
    print("✅ ML model loaded successfully")
except Exception as e:
    print(f"❌ ML model loading failed: {str(e)}")
    print("⚠️ Using dummy model for testing")
    model = None

# ===== ROUTES =====

@app.route('/')
def index():
    """Redirect to login page"""
    return redirect(url_for('auth'))

@app.route('/auth')
def auth():
    """Login page"""
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration"""
    if request.method == 'GET':
        return render_template('signup.html')
    
    # Handle POST request
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Validation
    if not name or not email or not password:
        flash('All fields are required!', 'danger')
        return redirect(url_for('signup'))

    if password != confirm_password:
        flash('Passwords do not match!', 'danger')
        return redirect(url_for('signup'))

    if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
        flash('Invalid email address!', 'danger')
        return redirect(url_for('signup'))

    if len(password) < 6:
        flash('Password must be at least 6 characters long!', 'danger')
        return redirect(url_for('signup'))

    try:
        # Check if user already exists
        existing_user = mongo.db.users.find_one({'email': email})

        if existing_user:
            flash("Email already registered! Please login.", "warning")
            return redirect(url_for('signup'))
        else:
            # Insert new user with HASHED password
            user_data = {
                'name': name,
                'email': email,
                'password': generate_password_hash(password),
                'created_at': datetime.utcnow(),
                'last_login': None
            }
            
            result = mongo.db.users.insert_one(user_data)
            flash("Signup successful! Please login.", "success")
            return redirect(url_for('auth'))
            
    except Exception as e:
        flash(f"Error during signup: {str(e)}", "danger")
        return redirect(url_for('signup'))

@app.route('/login', methods=['POST'])
def login():
    """User authentication"""
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not email or not password:
        flash('Please enter both email and password', 'danger')
        return redirect(url_for('auth'))

    try:
        # Find user by email only
        user = mongo.db.users.find_one({'email': email})

        if user and check_password_hash(user['password'], password):
            # Update last login
            mongo.db.users.update_one(
                {'_id': user['_id']},
                {'$set': {'last_login': datetime.utcnow()}}
            )
            
            # Create session
            session['loggedin'] = True
            session['user_id'] = str(user['_id'])
            session['name'] = user['name']
            session['email'] = user['email']
            
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for('home'))
        else:
            flash("Invalid email or password!", "danger")
            return redirect(url_for('auth'))
            
    except Exception as e:
        flash(f"Login error: {str(e)}", "danger")
        return redirect(url_for('auth'))

@app.route('/home')
def home():
    """User dashboard"""
    if 'loggedin' not in session:
        flash('Please login to access the dashboard', 'warning')
        return redirect(url_for('auth'))
    
    try:
        # Get user's prediction count for stats
        prediction_count = mongo.db.predictions.count_documents({
            'user_id': session['user_id']
        })
        
        # Get recent predictions for display
        recent_predictions = list(mongo.db.predictions.find(
            {'user_id': session['user_id']}
        ).sort('created_at', -1).limit(5))
        
        # Convert ObjectIds for template and add prediction_id
        for pred in recent_predictions:
            orig_id = pred.get('_id')
            pred['_id'] = str(orig_id)
            pred['prediction_id'] = str(orig_id)
        
        return render_template('home.html', 
                             user_name=session['name'],
                             prediction_count=prediction_count,
                             recent_predictions=recent_predictions)
    
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return redirect(url_for('auth'))

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    """Crop prediction page"""
    if 'loggedin' not in session:
        flash('Please login to make predictions', 'warning')
        return redirect(url_for('auth'))
    
    if request.method == 'POST':
        try:
            # Get form data safely, defaulting to 0
            nitrogen = float(request.form.get('N', 0) or 0)
            phosphorus = float(request.form.get('P', 0) or 0)
            potassium = float(request.form.get('K', 0) or 0)
            temperature = float(request.form.get('temperature', 0) or 0)
            humidity = float(request.form.get('humidity', 0) or 0)
            ph = float(request.form.get('ph', 0) or 0)
            rainfall = float(request.form.get('rainfall', 0) or 0)

            # Make prediction
            if model:
                features = [[nitrogen, phosphorus, potassium, temperature, humidity, ph, rainfall]]
                prediction = model.predict(features)[0]

                # Try to get probability/confidence if available
                confidence = None
                try:
                    proba = model.predict_proba(features)
                    confidence = float(np.max(proba) * 100)
                except Exception:
                    # model has no predict_proba — fallback to None
                    confidence = None

                if confidence is not None:
                    confidence = round(confidence, 2)
                else:
                    # if no probability, set a placeholder confidence
                    confidence = 0.0
            else:
                # Fallback dummy predictions
                crops = ['rice', 'wheat', 'maize', 'banana', 'mango', 'cotton', 'sugarcane']
                prediction = crops[np.random.randint(0, len(crops))]
                confidence = round(np.random.uniform(85, 96), 2)

            # Save prediction to database
            prediction_data = {
                'user_id': session['user_id'],
                'N': nitrogen,
                'P': phosphorus,
                'K': potassium,
                'temperature': temperature,
                'humidity': humidity,
                'ph': ph,
                'rainfall': rainfall,
                'predicted_crop': prediction,
                'confidence': confidence,
                'created_at': datetime.utcnow()
            }
            
            result = mongo.db.predictions.insert_one(prediction_data)
            prediction_id = str(result.inserted_id)
            prediction_data['_id'] = prediction_id
            prediction_data['prediction_id'] = prediction_id
            
            flash(f'Prediction successful! Recommended crop: {prediction}', 'success')
            return render_template('result.html', prediction=prediction_data)
            
        except Exception as e:
            flash(f'Prediction error: {str(e)}', 'danger')
            return redirect(url_for('predict'))
    
    # GET request - show prediction form
    return render_template('predict.html')

@app.route('/delete-prediction/<prediction_id>', methods=['POST'])
def delete_prediction(prediction_id):
    """Delete a prediction"""
    if 'loggedin' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    try:
        result = mongo.db.predictions.delete_one({
            '_id': ObjectId(prediction_id),
            'user_id': session['user_id']
        })
        
        if result.deleted_count > 0:
            return jsonify({'success': True, 'message': 'Prediction deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Prediction not found'}), 404
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/history')
def history():
    """Prediction history page"""
    if 'loggedin' not in session:
        flash('Please login to view history', 'warning')
        return redirect(url_for('auth'))
    
    try:
        predictions = list(mongo.db.predictions.find(
            {'user_id': session['user_id']}
        ).sort('created_at', -1))
        
        # Convert ObjectId to string for templates
        for prediction in predictions:
            orig_id = prediction.get('_id')
            prediction['_id'] = str(orig_id)
            prediction['prediction_id'] = str(orig_id)
        
        # Calculate unique crops and distribution for template
        unique_crops = list({p['predicted_crop'] for p in predictions})
        crop_distribution = {}
        for prediction in predictions:
            crop = prediction['predicted_crop']
            crop_distribution[crop] = crop_distribution.get(crop, 0) + 1
        
        return render_template('history.html', 
                             predictions=predictions,
                             unique_crops=unique_crops,
                             crop_distribution=crop_distribution)
    except Exception as e:
        flash(f'Error loading history: {str(e)}', 'danger')
        return redirect(url_for('home'))    

@app.route('/weather')
def weather():
    """Weather information page"""
    if 'loggedin' not in session:
        flash('Please login to view weather', 'warning')
        return redirect(url_for('auth'))
    
    return render_template('weather.html')

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('auth'))

# ======= START SERVER (auto-open browser) =======
def _open_browser_later(url="http://127.0.0.1:5000", delay=2.0):
    """Wait a short time, then open the browser. Runs in a background thread."""
    try:
        time.sleep(delay)
        webbrowser.open(url, new=2)  # new=2 -> new tab if possible
    except Exception as e:
        print(f"Could not open browser automatically: {e}")

if __name__ == "__main__":
    print("🚀 Starting AgriSense AI Server...")
    print("📍 Access your app at: http://127.0.0.1:5000")
    print("🌱 AgriSense AI - Smart Farming Solutions")
    print("=" * 50)

    # Start thread to open the browser (do this BEFORE app.run)
    threading.Thread(target=_open_browser_later, daemon=True).start()

    # IMPORTANT: disable the reloader so the browser-opening thread doesn't run twice
    app.run(debug=True, use_reloader=False, host='127.0.0.1', port=5000)
