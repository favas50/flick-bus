from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import json

import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
CORS(app)

# --- Firebase Initialization ---
# For deployment, we load the service account key from an environment variable.
# This keeps your sensitive key out of the codebase.
# On Render, you will set an environment variable named 'FIREBASE_SERVICE_ACCOUNT_KEY_JSON'.
if not firebase_admin._apps:
    try:
        firebase_credentials_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY_JSON')
        if firebase_credentials_json:
            cred = credentials.Certificate(json.loads(firebase_credentials_json))
            firebase_admin.initialize_app(cred)
            print("Firebase Admin SDK initialized successfully from environment variable.")
        else:
            # Fallback for local development:
            # If the environment variable is not set (e.g., when running locally),
            # try to load from the local file path.
            # IMPORTANT: Ensure SERVICE_ACCOUNT_KEY_PATH is defined for local use.
            SERVICE_ACCOUNT_KEY_PATH = "D:\\flick bus\\serviceAccountKey.json" # Keep this for local testing
            cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
            firebase_admin.initialize_app(cred)
            print("Firebase Admin SDK initialized successfully from local file.")

    except Exception as e:
        print(f"Error initializing Firebase Admin SDK: {e}")
        print("Please ensure your Firebase service account credentials are correctly set up (either via env var for deployment or local file for local dev).")
        exit(1)
# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized successfully.")
    except Exception as e:
        print(f"Error initializing Firebase Admin SDK: {e}")
        exit(1)

db = firestore.client()

# ---------- Load Bus Data ----------
def load_bus_data():
    routes = {}
    buses = []
    route_prefixes = {}

    try:
        routes_ref = db.collection('routes').stream()
        for doc in routes_ref:
            route_key = doc.id
            route_data = doc.to_dict()
            routes[route_key] = route_data.get('stops', [])
            route_prefixes[route_key] = route_data.get('bus_prefix', 'N/A')

        buses_ref = db.collection('buses').stream()
        for doc in buses_ref:
            bus_data_from_db = doc.to_dict()
            if 'schedule' in bus_data_from_db and isinstance(bus_data_from_db['schedule'], list):
                for stop in bus_data_from_db['schedule']:
                    if 'departureDateTime' in stop and hasattr(stop['departureDateTime'], 'to_datetime'):
                        stop['departureDateTime'] = stop['departureDateTime'].to_datetime()

                    if 'arrivalDateTime' in stop and hasattr(stop['arrivalDateTime'], 'to_datetime'):
                        stop['arrivalDateTime'] = stop['arrivalDateTime'].to_datetime()
            buses.append(bus_data_from_db)

    except Exception as e:
        print(f"An error occurred while loading data from Firestore: {e}")
        return {}, [], {}

    return routes, buses, route_prefixes

# ---------- Validate Schedule ----------
def validate_schedule(schedule, route_stops):
    if not isinstance(schedule, list) or len(schedule) != len(route_stops):
        return False, "Schedule length mismatch."

    schedule_stations = [stop.get('station', '').lower() for stop in schedule]
    route_stop_names = [stop.lower() for stop in route_stops]
    if schedule_stations != route_stop_names and schedule_stations != route_stop_names[::-1]:
        return False, "Stations mismatch."

    previous_datetime = None
    for stop in schedule:
        dep_dt = stop.get('departureDateTime')
        arr_dt = stop.get('arrivalDateTime')

        if isinstance(dep_dt, str):
            dep_dt = datetime.fromisoformat(dep_dt)
        if isinstance(arr_dt, str):
            arr_dt = datetime.fromisoformat(arr_dt)

        if previous_datetime and arr_dt and arr_dt < previous_datetime:
            return False, f"Arrival before previous departure."

        if arr_dt and dep_dt and dep_dt < arr_dt:
            return False, f"Departure before arrival."

        previous_datetime = dep_dt or arr_dt

    return True, "Valid schedule."

# ---------- Initialize Firestore with Simulated Data ----------
routes_data, bus_data, route_bus_prefixes = load_bus_data()

if not routes_data and not bus_data:
    print("Initializing Firestore with sample data...")
    initial_routes_data = {
        "edappal-kuttippuram": ["Edappal", "A", "B", "C", "Kuttippuram"]
    }
    initial_route_bus_prefixes = {
        "edappal-kuttippuram": "Bus AA"
    }

    for route_key, stops in initial_routes_data.items():
        db.collection('routes').document(route_key).set({
            'stops': stops,
            'bus_prefix': initial_route_bus_prefixes[route_key]
        })
        routes_data[route_key] = stops
        route_bus_prefixes[route_key] = initial_route_bus_prefixes[route_key]

    now = datetime.now()
    schedule = [
        {"station": "Edappal", "departureDateTime": now + timedelta(minutes=5)},
        {"station": "A", "arrivalDateTime": now + timedelta(minutes=10), "departureDateTime": now + timedelta(minutes=12)},
        {"station": "B", "arrivalDateTime": now + timedelta(minutes=20), "departureDateTime": now + timedelta(minutes=22)},
        {"station": "C", "arrivalDateTime": now + timedelta(minutes=30), "departureDateTime": now + timedelta(minutes=32)},
        {"station": "Kuttippuram", "arrivalDateTime": now + timedelta(minutes=40)}
    ]

    db.collection('buses').add({
        "vehicle_number": "Bus AA 1",
        "route_key": "edappal-kuttippuram",
        "schedule": schedule
    })

    bus_data.append({
        "vehicle_number": "Bus AA 1",
        "route_key": "edappal-kuttippuram",
        "schedule": schedule
    })

    routes_data, bus_data, route_bus_prefixes = load_bus_data()

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/next_bus')
def next_bus():
    return render_template('next_bus.html')

@app.route('/find_bus')
def find_bus():
    return render_template('find_bus.html')

@app.route('/explore')
def explore():
    return render_template('explore.html')

# ---------- Run ----------
if __name__ == '__main__':
    app.run(debug=True, port=5000)
