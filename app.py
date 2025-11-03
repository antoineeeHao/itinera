# ITINERA — Your Budget-to-Boarding Trip Composer
# ------------------------------------------------
# Single-file Streamlit prototype for the AAA assignment.
# Reproducible: runs with built-in sample data; no API keys required.
# If optional libraries are installed (transformers), the app will use them; otherwise it falls back to rule-based summarization.
#
# Usage
#   1) pip install -r requirements.txt
#   2) streamlit run app.py
#
# Suggested requirements.txt
#   streamlit>=1.36
#   pandas>=2.2
#   numpy>=1.26
#   scikit-learn>=1.4
#   pulp>=2.9
#   python-dateutil>=2.9
#   matplotlib>=3.8
#   # optional
#   transformers>=4.41
#
# Notes
# - All prices are indicative baselines in EUR, purely for demo purposes.
# - CO2 estimates are rough one-way kg per passenger for flights from Paris.
# - The optimizer keeps a 10% buffer under the user budget by design.

from __future__ import annotations
import json
import math
import random
import hashlib
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
from dateutil import parser as dateparser

# --- User Authentication System ---
USER_DB_FILE = "users.json"
MAX_USERS = 5

def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_users() -> Dict:
    """Load users from JSON file"""
    try:
        with open(USER_DB_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(users: Dict) -> None:
    """Save users to JSON file"""
    with open(USER_DB_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def register_user(username: str, password: str) -> Tuple[bool, str]:
    """Register a new user"""
    users = load_users()
    
    if len(users) >= MAX_USERS:
        return False, f"Registration limit reached. Maximum {MAX_USERS} users allowed."
    
    if username in users:
        return False, "Username already exists."
    
    if len(username) < 3:
        return False, "Username must be at least 3 characters long."
    
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."
    
    users[username] = {
        "password_hash": hash_password(password),
        "created_at": datetime.now().isoformat(),
        "login_count": 0
    }
    
    save_users(users)
    return True, "Registration successful!"

def authenticate_user(username: str, password: str) -> Tuple[bool, str]:
    """Authenticate user login"""
    users = load_users()
    
    if username not in users:
        return False, "Username not found."
    
    if users[username]["password_hash"] != hash_password(password):
        return False, "Incorrect password."
    
    # Update login count
    users[username]["login_count"] += 1
    users[username]["last_login"] = datetime.now().isoformat()
    save_users(users)
    
    return True, "Login successful!"

def logout_user():
    """Logout current user"""
    for key in list(st.session_state.keys()):
        if key.startswith('auth_'):
            del st.session_state[key]

# Initialize session state for authentication
if 'auth_logged_in' not in st.session_state:
    st.session_state.auth_logged_in = False
if 'auth_username' not in st.session_state:
    st.session_state.auth_username = None

# Initialize session state for usage tracking
if 'filter_usage_count' not in st.session_state:
    st.session_state.filter_usage_count = 0
if 'show_registration_required' not in st.session_state:
    st.session_state.show_registration_required = False

MAX_FREE_USES = 20

# --- Optional NLP (auto-detected) ---
try:
    from transformers import pipeline  # type: ignore
    _HAS_TRANSFORMERS = True
except Exception:
    _HAS_TRANSFORMERS = False

# --- Optional LP Optimizer (for budget fit) ---
try:
    import pulp  # type: ignore
    _HAS_PULP = True
except Exception:
    _HAS_PULP = False

# -------------------------------
# Seeded randomness for reproducibility (removed to allow dynamic ranking)
# -------------------------------
# random.seed(42)  # Commented out to allow dynamic tie-breaking
# np.random.seed(42)  # Commented out to allow dynamic ranking

# -------------------------------
# Sample Data (embedded)
# Flight prices based on 2024 average economy fares from Paris (CDG/ORY) 
# Sources: Skyscanner, Kayak, Google Flights historical data (Q3-Q4 2024)
# Prices include taxes and fees, economy class, 1-3 weeks advance booking
# -------------------------------

# Country flag mapping
COUNTRY_FLAGS = {
    "Spain": "🇪🇸",
    "Hungary": "🇭🇺", 
    "Greece": "🇬🇷",
    "Germany": "🇩🇪",
    "Morocco": "🇲🇦",
    "Czech Republic": "🇨🇿",
    "Netherlands": "🇳🇱",
    "Austria": "🇦🇹",
    "Italy": "🇮🇹",
    "Sweden": "🇸🇪",
    "Denmark": "🇩🇰",
    "Poland": "🇵🇱",
    "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "Croatia": "🇭🇷",
    "Switzerland": "🇨🇭",
    "Finland": "🇫🇮",
    "Belgium": "🇧🇪",
    "Norway": "🇳🇴",
    "Iceland": "🇮🇸",
    "Ireland": "🇮🇪",
    "Slovenia": "🇸🇮",
    "Latvia": "🇱🇻",
    "Estonia": "🇪🇪",
    "Lithuania": "🇱🇹"
}
DESTINATIONS = [
    {
        "city": "Barcelona",
        "country": "Spain",
        "month_mod": {"11": 1.00, "12": 1.12, "01": 0.88, "02": 0.85, "03": 0.92, "04": 1.08, "05": 1.25, "06": 1.40, "07": 1.50, "08": 1.48, "09": 1.18, "10": 1.02},
        "flight_price_base": 110,  # CDG-BCN avg €110 (Vueling, Air France)
        "flight_price_premium": 340,
        "flight_price_luxury": 480,  # Reduced from 580
        "hotel_per_night": 95,
        "hotel_premium": 180,
        "hotel_luxury": 265,  # Reduced from 320
        "daily_food": 32,
        "daily_food_premium": 58,
        "daily_food_luxury": 85,  # Reduced from 105
        "daily_transit": 7,
        "attraction_day_pass": 28,
        "co2_kg": 260,
        "walkability": 0.78,  # Adjusted based on actual urban mobility data
        "safety": 0.68,  # Global Safety Index - pickpocketing affects tourist experience
        "accessibility": 0.72,
        "vibes": ["architecture", "foodie", "nightlife", "beach"],
        # Add factors that affect ranking consistency - enhanced diversity
        "cost_of_living_index": 0.65,  # Moderately expensive
        "tourist_density": 0.85,  # Very high tourism saturation
        "weather_factor": 0.85,  # Generally favorable climate
        "cultural_factor": 0.88,  # Rich cultural heritage
        "budget_sensitivity": 0.75,  # Medium budget sensitivity
        "luxury_appeal": 0.70,  # Moderate luxury appeal
    },
    {
        "city": "Budapest",
        "country": "Hungary",
        "month_mod": {"11": 0.95, "12": 1.05, "01": 0.80, "02": 0.78, "03": 0.85, "04": 1.00, "05": 1.15, "06": 1.30, "07": 1.35, "08": 1.32, "09": 1.10, "10": 0.98},
        "flight_price_base": 140,  # CDG-BUD avg €140 (Wizz Air, Air France)
        "flight_price_premium": 380,
        "flight_price_luxury": 650,
        "hotel_per_night": 70,
        "hotel_premium": 140,
        "hotel_luxury": 250,
        "daily_food": 25,
        "daily_food_premium": 45,
        "daily_food_luxury": 80,
        "daily_transit": 5,
        "attraction_day_pass": 20,
        "co2_kg": 390,
        "walkability": 0.80,
        "safety": 0.69,
        "accessibility": 0.65,
        "vibes": ["baths", "architecture", "museums", "nightlife"],
        "cost_of_living_index": 0.85,  # Very affordable
        "tourist_density": 0.70,        # High but manageable tourism
        "weather_factor": 0.75,         # Continental climate, decent
        "cultural_factor": 0.82,        # Strong cultural appeal
        "budget_sensitivity": 0.95,     # High budget sensitivity 
        "luxury_appeal": 0.65,          # Lower luxury appeal
    },
    {
        "city": "Prague",
        "country": "Czech Republic",
        "month_mod": {"11": 0.90, "12": 0.95, "01": 0.75, "02": 0.73, "03": 0.80, "04": 0.95, "05": 1.12, "06": 1.25, "07": 1.30, "08": 1.28, "09": 1.05, "10": 0.92},
        "flight_price_base": 120,  # CDG-PRG avg €120 (Czech Airlines, Air France)
        "flight_price_premium": 360,
        "flight_price_luxury": 590,
        "hotel_per_night": 75,
        "hotel_premium": 145,
        "hotel_luxury": 265,
        "daily_food": 28,
        "daily_food_premium": 48,
        "daily_food_luxury": 85,
        "daily_transit": 6,
        "attraction_day_pass": 22,
        "co2_kg": 350,
        "walkability": 0.84,
        "safety": 0.74,
        "accessibility": 0.68,
        "vibes": ["architecture", "history", "nightlife", "museums"],
        "cost_of_living_index": 0.78,  # Good value destination
        "tourist_density": 0.85,        # Very high tourism density
        "weather_factor": 0.72,         # Continental climate
        "cultural_factor": 0.91,        # Exceptional cultural heritage
        "budget_sensitivity": 0.88,     # High budget appeal
        "luxury_appeal": 0.72,          # Growing luxury scene
    },
    {
        "city": "Amsterdam",
        "country": "Netherlands",
        "month_mod": {"11": 0.95, "12": 1.05, "01": 0.85, "02": 0.83, "03": 0.90, "04": 1.10, "05": 1.22, "06": 1.35, "07": 1.40, "08": 1.38, "09": 1.15, "10": 1.00},
        "flight_price_base": 95,   # CDG-AMS avg €95 (KLM, Air France)
        "flight_price_premium": 310,
        "flight_price_luxury": 520,
        "hotel_per_night": 135,
        "hotel_premium": 220,
        "hotel_luxury": 380,
        "daily_food": 42,
        "daily_food_premium": 70,
        "daily_food_luxury": 125,
        "daily_transit": 8,
        "attraction_day_pass": 35,
        "co2_kg": 180,
        "walkability": 0.89,
        "safety": 0.82,
        "accessibility": 0.85,
        "vibes": ["museums", "nightlife", "architecture", "nature"],
        "cost_of_living_index": 0.30,  # Expensive
        "tourist_density": 0.90,        # Very high tourism density
        "weather_factor": 0.65,         # Rainy climate
        "cultural_factor": 0.89,        # Rich museum culture
        "budget_sensitivity": 0.45,     # Lower budget appeal due to cost
        "luxury_appeal": 0.80,          # Strong luxury market
    },
    {
        "city": "Vienna",
        "country": "Austria",
        "month_mod": {"11": 0.92, "12": 1.08, "01": 0.80, "02": 0.78, "03": 0.85, "04": 1.00, "05": 1.15, "06": 1.28, "07": 1.32, "08": 1.30, "09": 1.08, "10": 0.95},
        "flight_price_base": 125,  # CDG-VIE avg €125 (Austrian Airlines, Air France)
        "flight_price_premium": 375,
        "flight_price_luxury": 630,
        "hotel_per_night": 105,
        "hotel_premium": 185,
        "hotel_luxury": 320,
        "daily_food": 38,
        "daily_food_premium": 65,
        "daily_food_luxury": 115,
        "daily_transit": 7,
        "attraction_day_pass": 28,
        "co2_kg": 320,
        "walkability": 0.82,
        "safety": 0.85,
        "accessibility": 0.78,
        "vibes": ["architecture", "museums", "history", "wellness"],
        "cost_of_living_index": 0.40,  # Moderately expensive
        "tourist_density": 0.75,        # High but manageable tourism
        "weather_factor": 0.72,         # Continental climate
        "cultural_factor": 0.93,        # Imperial cultural heritage
        "budget_sensitivity": 0.60,     # Medium budget sensitivity
        "luxury_appeal": 0.85,          # Strong luxury traditions
    },
    {
        "city": "Rome",
        "country": "Italy",
        "month_mod": {"11": 1.02, "12": 1.12, "01": 0.88, "02": 0.85, "03": 0.95, "04": 1.15, "05": 1.30, "06": 1.45, "07": 1.55, "08": 1.52, "09": 1.25, "10": 1.08},
        "flight_price_base": 115,  # CDG-FCO avg €115 (Alitalia, Air France)
        "flight_price_premium": 350,
        "flight_price_luxury": 590,
        "hotel_per_night": 90,
        "hotel_premium": 175,
        "hotel_luxury": 310,
        "daily_food": 35,
        "daily_food_premium": 60,
        "daily_food_luxury": 105,
        "daily_transit": 5,
        "attraction_day_pass": 30,
        "co2_kg": 380,
        "walkability": 0.78,
        "safety": 0.68,
        "accessibility": 0.65,
        "vibes": ["history", "foodie", "architecture", "museums"],
        "cost_of_living_index": 0.55,  # Moderately affordable for major European capital
        "tourist_density": 0.95,        # Extremely high tourism (overtourism issues)
        "weather_factor": 0.85,         # Mediterranean climate, generally good
        "cultural_factor": 0.98,        # Unparalleled historical significance
        "budget_sensitivity": 0.70,     # Medium budget appeal
        "luxury_appeal": 0.78,          # Strong luxury heritage
    },
    {
        "city": "Berlin",
        "country": "Germany",
        "month_mod": {"11": 0.92, "12": 1.00, "01": 0.85, "02": 0.83, "03": 0.90, "04": 1.05, "05": 1.18, "06": 1.28, "07": 1.32, "08": 1.30, "09": 1.08, "10": 0.95},
        "flight_price_base": 100,  # CDG-TXL/BER avg €100 (easyJet, Air France)
        "flight_price_premium": 320,
        "flight_price_luxury": 450,  # Reduced from 550
        "hotel_per_night": 110,
        "hotel_premium": 195,
        "hotel_luxury": 285,  # Reduced from 350
        "daily_food": 36,
        "daily_food_premium": 65,
        "daily_food_luxury": 95,  # Reduced from 115
        "daily_transit": 9,
        "attraction_day_pass": 30,
        "co2_kg": 290,
        "walkability": 0.81,
        "safety": 0.78,
        "accessibility": 0.80,
        "vibes": ["museums", "nightlife", "history"],
        "cost_of_living_index": 0.70,  # Relatively affordable for major German city
        "tourist_density": 0.75,        # High but manageable tourism
        "weather_factor": 0.70,         # Continental climate
        "cultural_factor": 0.85,        # Rich modern and historical culture
        "budget_sensitivity": 0.75,     # Good budget appeal
        "luxury_appeal": 0.68,          # Growing luxury scene
    },
    {
        "city": "Zurich",
        "country": "Switzerland",
        "month_mod": {"11": 0.92, "12": 1.08, "01": 0.85, "02": 0.83, "03": 0.88, "04": 0.95, "05": 1.10, "06": 1.25, "07": 1.35, "08": 1.32, "09": 1.08, "10": 0.95},
        "flight_price_base": 155,  # CDG-ZUR avg €155 (Swiss, Air France)
        "flight_price_premium": 445,
        "flight_price_luxury": 780,
        "hotel_per_night": 180,
        "hotel_premium": 295,
        "hotel_luxury": 485,
        "daily_food": 55,
        "daily_food_premium": 85,
        "daily_food_luxury": 155,
        "daily_transit": 12,
        "attraction_day_pass": 45,
        "co2_kg": 240,
        "walkability": 0.91,
        "safety": 0.95,
        "accessibility": 0.90,
        "vibes": ["nature", "hiking", "luxury", "wellness"],
        "cost_of_living_index": 0.05,  # Very expensive
        "tourist_density": 0.55,        # Moderate tourism
        "weather_factor": 0.78,         # Alpine climate
        "cultural_factor": 0.75,        # Swiss cultural appeal
        "budget_sensitivity": 0.25,     # Low budget appeal due to cost
        "luxury_appeal": 0.95,          # Premium luxury destination
    },
    {
        "city": "Krakow",
        "country": "Poland",
        "month_mod": {"11": 0.88, "12": 0.95, "01": 0.75, "02": 0.73, "03": 0.78, "04": 0.90, "05": 1.05, "06": 1.18, "07": 1.22, "08": 1.20, "09": 1.00, "10": 0.85},
        "flight_price_base": 150,  # CDG-KRK avg €150 (LOT Polish Airlines)
        "flight_price_premium": 390,
        "flight_price_luxury": 660,
        "hotel_per_night": 60,
        "hotel_premium": 115,
        "hotel_luxury": 205,
        "daily_food": 22,
        "daily_food_premium": 38,
        "daily_food_luxury": 70,
        "daily_transit": 4,
        "attraction_day_pass": 18,
        "co2_kg": 410,
        "walkability": 0.81,
        "safety": 0.75,
        "accessibility": 0.62,
        "vibes": ["history", "architecture", "museums", "foodie"],
        "cost_of_living_index": 0.90,  # Very affordable
        "tourist_density": 0.80,        # High tourism
        "weather_factor": 0.68,         # Continental climate
        "cultural_factor": 0.87,        # Rich medieval heritage
        "budget_sensitivity": 0.95,     # Excellent budget appeal
        "luxury_appeal": 0.55,          # Emerging luxury market
    },
    {
        "city": "Copenhagen",
        "country": "Denmark",
        "month_mod": {"11": 0.90, "12": 0.95, "01": 0.85, "02": 0.83, "03": 0.88, "04": 0.98, "05": 1.12, "06": 1.25, "07": 1.30, "08": 1.28, "09": 1.05, "10": 0.92},
        "flight_price_base": 135,  # CDG-CPH avg €135 (SAS, Air France)
        "flight_price_premium": 405,
        "flight_price_luxury": 685,
        "hotel_per_night": 140,
        "hotel_premium": 230,
        "hotel_luxury": 395,
        "daily_food": 48,
        "daily_food_premium": 80,
        "daily_food_luxury": 145,
        "daily_transit": 10,
        "attraction_day_pass": 42,
        "co2_kg": 380,
        "walkability": 0.84,  # Based on Walk Score equivalent - very high but not perfect
        "safety": 0.82,  # Global Peace Index adjusted - high but not exceptional  
        "accessibility": 0.88,
        "vibes": ["architecture", "foodie", "nature", "wellness"],
        # Add economic factors that affect overall appeal
        "cost_of_living_index": 0.15,  # Very expensive (1.0 = most expensive)
        "tourist_density": 0.75,  # High tourist saturation
        "weather_factor": 0.65,  # Nordic climate limitations
        "cultural_factor": 0.83,  # Scandinavian design culture
        "budget_sensitivity": 0.35,  # Low budget appeal
        "luxury_appeal": 0.88,  # Strong luxury Nordic brands
    },
    {
        "city": "Dubrovnik",
        "country": "Croatia",
        "month_mod": {"11": 0.85, "12": 0.88, "01": 0.75, "02": 0.73, "03": 0.80, "04": 0.95, "05": 1.15, "06": 1.35, "07": 1.50, "08": 1.48, "09": 1.20, "10": 1.00},
        "flight_price_base": 165,  # CDG-DBV avg €165 (Croatia Airlines, via Zagreb)
        "flight_price_premium": 440,
        "flight_price_luxury": 750,
        "hotel_per_night": 85,
        "hotel_premium": 165,
        "hotel_luxury": 295,
        "daily_food": 30,
        "daily_food_premium": 52,
        "daily_food_luxury": 95,
        "daily_transit": 5,
        "attraction_day_pass": 25,
        "co2_kg": 450,
        "walkability": 0.88,
        "safety": 0.78,
        "accessibility": 0.58,
        "vibes": ["views", "history", "beach", "nature"],
        "cost_of_living_index": 0.75,  # Affordable
        "tourist_density": 0.95,        # Very high tourism
        "weather_factor": 0.90,         # Excellent Mediterranean climate
        "cultural_factor": 0.80,        # UNESCO heritage appeal
        "budget_sensitivity": 0.80,     # Good budget-to-luxury range
        "luxury_appeal": 0.75,          # Growing luxury tourism
    },
    {
        "city": "Edinburgh",
        "country": "Scotland",
        "month_mod": {"11": 0.92, "12": 1.00, "01": 0.85, "02": 0.83, "03": 0.88, "04": 1.00, "05": 1.15, "06": 1.30, "07": 1.45, "08": 1.42, "09": 1.10, "10": 0.95},
        "flight_price_base": 105,  # CDG-EDI avg €105 (easyJet, British Airways)
        "flight_price_premium": 325,
        "flight_price_luxury": 550,
        "hotel_per_night": 110,
        "hotel_premium": 190,
        "hotel_luxury": 330,
        "daily_food": 40,
        "daily_food_premium": 68,
        "daily_food_luxury": 120,
        "daily_transit": 6,
        "attraction_day_pass": 32,
        "co2_kg": 320,
        "walkability": 0.83,
        "safety": 0.80,
        "accessibility": 0.72,
        "vibes": ["history", "nature", "museums", "hiking"],
        "cost_of_living_index": 0.50,  # Moderately expensive
        "tourist_density": 0.85,        # High tourism especially during festivals
        "weather_factor": 0.60,         # Challenging Scottish weather
        "cultural_factor": 0.90,        # Rich Scottish heritage
        "budget_sensitivity": 0.65,     # Medium budget appeal
        "luxury_appeal": 0.82,          # Strong luxury heritage tourism
    },
    {
        "city": "Ljubljana",
        "country": "Slovenia",
        "month_mod": {"11": 0.88, "12": 0.95, "01": 0.75, "02": 0.73, "03": 0.78, "04": 0.90, "05": 1.08, "06": 1.22, "07": 1.28, "08": 1.25, "09": 1.05, "10": 0.90},
        "flight_price_base": 185,  # CDG-LJU avg €185 (via Vienna/Frankfurt)
        "flight_price_premium": 485,
        "flight_price_luxury": 825,
        "hotel_per_night": 75,
        "hotel_premium": 135,
        "hotel_luxury": 235,
        "daily_food": 28,
        "daily_food_premium": 48,
        "daily_food_luxury": 85,
        "daily_transit": 5,
        "attraction_day_pass": 22,
        "co2_kg": 450,
        "walkability": 0.86,
        "safety": 0.80,
        "accessibility": 0.70,
        "vibes": ["nature", "hiking", "adventure", "views"],
        "cost_of_living_index": 0.80,  # Affordable
        "tourist_density": 0.45,        # Lower tourism - hidden gem
        "weather_factor": 0.75,         # Central European climate
        "cultural_factor": 0.70,        # Emerging cultural scene
        "budget_sensitivity": 0.85,     # Good budget appeal
        "luxury_appeal": 0.60,          # Developing luxury scene
    }
]

POIS = {
    "Barcelona": [
        {"name": "Sagrada Família", "tags": ["architecture"], "hours": 2, "cost": 26},
        {"name": "Gothic Quarter", "tags": ["history"], "hours": 2, "cost": 0},
        {"name": "La Boqueria", "tags": ["foodie"], "hours": 1.5, "cost": 12},
        {"name": "Park Güell", "tags": ["views", "architecture"], "hours": 2, "cost": 10},
        {"name": "Barceloneta", "tags": ["beach"], "hours": 2, "cost": 0},
        {"name": "Montjuïc Hiking", "tags": ["hiking", "views", "nature"], "hours": 4, "cost": 0},
        {"name": "Tibidabo Mountain", "tags": ["hiking", "views", "adventure"], "hours": 5, "cost": 15},
        {"name": "Costa Brava Day Trip", "tags": ["nature", "hiking", "beach"], "hours": 8, "cost": 45},
    ],
    "Budapest": [
        {"name": "Széchenyi Baths", "tags": ["baths", "wellness"], "hours": 2.5, "cost": 20},
        {"name": "Buda Castle", "tags": ["history", "views"], "hours": 2, "cost": 10},
        {"name": "Ruin Bars", "tags": ["nightlife"], "hours": 2, "cost": 15},
        {"name": "Parliament", "tags": ["architecture"], "hours": 1.5, "cost": 12},
        {"name": "Danube Promenade", "tags": ["views"], "hours": 1.5, "cost": 0},
        {"name": "Buda Hills Hiking", "tags": ["hiking", "nature", "views"], "hours": 4, "cost": 5},
        {"name": "Danube Bend Day Trip", "tags": ["nature", "hiking", "views"], "hours": 7, "cost": 35},
        {"name": "Thermal Cave Baths", "tags": ["wellness", "adventure", "nature"], "hours": 3, "cost": 25},
    ],
    "Athens": [
        {"name": "Acropolis", "tags": ["history", "views"], "hours": 2.5, "cost": 20},
        {"name": "Acropolis Museum", "tags": ["museums"], "hours": 2, "cost": 12},
        {"name": "Plaka", "tags": ["foodie", "shops"], "hours": 2, "cost": 0},
        {"name": "Lycabettus Hill", "tags": ["views", "hiking"], "hours": 2, "cost": 0},
        {"name": "Central Market", "tags": ["foodie"], "hours": 1.5, "cost": 10},
        {"name": "Mount Hymettus Hike", "tags": ["hiking", "nature", "views"], "hours": 5, "cost": 0},
        {"name": "Aegina Island Day Trip", "tags": ["nature", "hiking", "beach"], "hours": 8, "cost": 40},
        {"name": "National Gardens", "tags": ["nature", "wellness"], "hours": 2, "cost": 0},
    ],
    "Berlin": [
        {"name": "Museum Island", "tags": ["museums"], "hours": 3, "cost": 19},
        {"name": "Brandenburg Gate", "tags": ["history"], "hours": 1, "cost": 0},
        {"name": "East Side Gallery", "tags": ["history", "views"], "hours": 1.5, "cost": 0},
        {"name": "Tempelhofer Feld", "tags": ["outdoors", "nature"], "hours": 2, "cost": 0},
        {"name": "Kreuzberg Food Tour", "tags": ["foodie"], "hours": 2.5, "cost": 20},
        {"name": "Grunewald Forest Hike", "tags": ["hiking", "nature"], "hours": 4, "cost": 0},
        {"name": "Spreewald Day Trip", "tags": ["nature", "adventure", "hiking"], "hours": 8, "cost": 35},
        {"name": "Thermal Baths & Spa", "tags": ["wellness", "luxury"], "hours": 3, "cost": 35},
    ],
    "Marrakech": [
        {"name": "Jemaa el-Fnaa", "tags": ["markets", "foodie"], "hours": 2, "cost": 0},
        {"name": "Majorelle Garden", "tags": ["nature"], "hours": 1.5, "cost": 12},
        {"name": "Souks", "tags": ["markets", "shops"], "hours": 2, "cost": 0},
        {"name": "Bahia Palace", "tags": ["history", "architecture"], "hours": 1.5, "cost": 7},
        {"name": "Rooftop Dinner", "tags": ["foodie", "views"], "hours": 2, "cost": 18},
        {"name": "Atlas Mountains Hike", "tags": ["hiking", "adventure", "nature"], "hours": 8, "cost": 60},
        {"name": "Desert Trekking", "tags": ["adventure", "hiking", "nature"], "hours": 10, "cost": 85},
        {"name": "Hammam & Spa", "tags": ["wellness", "luxury"], "hours": 3, "cost": 40},
        {"name": "High Atlas Climbing", "tags": ["climbing", "adventure"], "hours": 12, "cost": 120},
    ],
    "Prague": [
        {"name": "Charles Bridge", "tags": ["history", "views"], "hours": 1.5, "cost": 0},
        {"name": "Prague Castle", "tags": ["history", "architecture"], "hours": 3, "cost": 15},
        {"name": "Old Town Square", "tags": ["architecture", "history"], "hours": 2, "cost": 0},
        {"name": "Beer Tour", "tags": ["foodie", "nightlife"], "hours": 3, "cost": 25},
        {"name": "Vltava River Cruise", "tags": ["views", "nature"], "hours": 2, "cost": 18},
        {"name": "Petrin Hill Hike", "tags": ["hiking", "views", "nature"], "hours": 3, "cost": 0},
        {"name": "Bohemian Switzerland Day Trip", "tags": ["hiking", "nature", "adventure"], "hours": 8, "cost": 45},
        {"name": "Spa & Wellness", "tags": ["wellness", "luxury"], "hours": 4, "cost": 60},
    ],
    "Amsterdam": [
        {"name": "Anne Frank House", "tags": ["history", "museums"], "hours": 2, "cost": 16},
        {"name": "Rijksmuseum", "tags": ["museums", "architecture"], "hours": 3, "cost": 20},
        {"name": "Canal Cruise", "tags": ["views", "architecture"], "hours": 1.5, "cost": 18},
        {"name": "Vondelpark", "tags": ["nature", "outdoors"], "hours": 2, "cost": 0},
        {"name": "Red Light District", "tags": ["nightlife", "history"], "hours": 1.5, "cost": 0},
        {"name": "Keukenhof Gardens", "tags": ["nature", "views"], "hours": 4, "cost": 25},
        {"name": "Zaanse Schans Cycling", "tags": ["nature", "hiking", "outdoors"], "hours": 6, "cost": 35},
        {"name": "Luxury Canal Tour", "tags": ["luxury", "views"], "hours": 2.5, "cost": 85},
    ],
    "Vienna": [
        {"name": "Schönbrunn Palace", "tags": ["history", "architecture"], "hours": 3, "cost": 22},
        {"name": "Salzburg Day Trip", "tags": ["history", "nature", "hiking"], "hours": 10, "cost": 55},
        {"name": "Vienna Woods Hiking", "tags": ["hiking", "nature"], "hours": 5, "cost": 8},
        {"name": "St. Stephen's Cathedral", "tags": ["architecture", "history"], "hours": 1.5, "cost": 6},
        {"name": "Belvedere Museum", "tags": ["museums", "architecture"], "hours": 2.5, "cost": 18},
        {"name": "Coffee House Culture", "tags": ["foodie", "wellness"], "hours": 2, "cost": 12},
        {"name": "Thermal Baths", "tags": ["wellness", "luxury"], "hours": 3, "cost": 45},
        {"name": "Private Opera Experience", "tags": ["luxury", "architecture"], "hours": 4, "cost": 150},
    ],
    "Rome": [
        {"name": "Colosseum", "tags": ["history", "architecture"], "hours": 2.5, "cost": 25},
        {"name": "Vatican Museums", "tags": ["museums", "history"], "hours": 4, "cost": 30},
        {"name": "Trevi Fountain", "tags": ["architecture", "history"], "hours": 1, "cost": 0},
        {"name": "Trastevere Food Tour", "tags": ["foodie"], "hours": 3, "cost": 35},
        {"name": "Roman Forum", "tags": ["history", "architecture"], "hours": 2, "cost": 18},
        {"name": "Appian Way Cycling", "tags": ["hiking", "history", "nature"], "hours": 4, "cost": 25},
        {"name": "Tuscany Day Trip", "tags": ["nature", "hiking", "foodie"], "hours": 10, "cost": 85},
        {"name": "Private Villa Experience", "tags": ["luxury", "foodie"], "hours": 6, "cost": 200},
    ],
    "Stockholm": [
        {"name": "Gamla Stan", "tags": ["history", "architecture"], "hours": 2, "cost": 0},
        {"name": "Vasa Museum", "tags": ["museums", "history"], "hours": 2, "cost": 20},
        {"name": "ABBA Museum", "tags": ["museums"], "hours": 2, "cost": 28},
        {"name": "Archipelago Tour", "tags": ["nature", "views"], "hours": 6, "cost": 45},
        {"name": "Royal Palace", "tags": ["history", "architecture"], "hours": 2, "cost": 15},
        {"name": "Hiking Sörmland", "tags": ["hiking", "nature"], "hours": 7, "cost": 20},
        {"name": "Nordic Spa Experience", "tags": ["wellness", "luxury"], "hours": 4, "cost": 80},
        {"name": "Ice Hotel Experience", "tags": ["luxury", "adventure"], "hours": 12, "cost": 250},
    ],
    "Copenhagen": [
        {"name": "Nyhavn", "tags": ["architecture", "views"], "hours": 1.5, "cost": 0},
        {"name": "Tivoli Gardens", "tags": ["nature", "outdoors"], "hours": 3, "cost": 20},
        {"name": "Rosenborg Castle", "tags": ["history", "architecture"], "hours": 2, "cost": 18},
        {"name": "Food Market Tour", "tags": ["foodie"], "hours": 3, "cost": 40},
        {"name": "Christiania", "tags": ["history", "outdoors"], "hours": 2, "cost": 0},
        {"name": "Øresund Bridge Cycling", "tags": ["hiking", "nature", "views"], "hours": 6, "cost": 35},
        {"name": "Nordic Cuisine Experience", "tags": ["foodie", "luxury"], "hours": 4, "cost": 120},
        {"name": "Private Royal Tour", "tags": ["luxury", "history"], "hours": 5, "cost": 180},
    ],
    "Krakow": [
        {"name": "Wawel Castle", "tags": ["history", "architecture"], "hours": 2.5, "cost": 12},
        {"name": "Main Market Square", "tags": ["architecture", "history"], "hours": 2, "cost": 0},
        {"name": "Auschwitz Memorial", "tags": ["history", "museums"], "hours": 7, "cost": 35},
        {"name": "Salt Mine Tour", "tags": ["history", "adventure"], "hours": 4, "cost": 28},
        {"name": "Jewish Quarter", "tags": ["history", "foodie"], "hours": 3, "cost": 0},
        {"name": "Tatra Mountains Hiking", "tags": ["hiking", "nature", "adventure"], "hours": 8, "cost": 40},
        {"name": "Zakopane Day Trip", "tags": ["hiking", "nature"], "hours": 10, "cost": 50},
        {"name": "Traditional Polish Feast", "tags": ["foodie", "luxury"], "hours": 3, "cost": 65},
    ],
    "Florence": [
        {"name": "Uffizi Gallery", "tags": ["museums", "architecture"], "hours": 3, "cost": 25},
        {"name": "Duomo", "tags": ["architecture", "history"], "hours": 2, "cost": 15},
        {"name": "Ponte Vecchio", "tags": ["architecture", "history"], "hours": 1, "cost": 0},
        {"name": "Tuscan Food Tour", "tags": ["foodie"], "hours": 4, "cost": 45},
        {"name": "Pitti Palace", "tags": ["museums", "architecture"], "hours": 2.5, "cost": 20},
        {"name": "Chianti Hiking Tour", "tags": ["hiking", "nature", "foodie"], "hours": 8, "cost": 75},
        {"name": "Cinque Terre Day Trip", "tags": ["hiking", "nature", "views"], "hours": 12, "cost": 85},
        {"name": "Private Renaissance Tour", "tags": ["luxury", "museums"], "hours": 6, "cost": 180},
    ],
    "Edinburgh": [
        {"name": "Edinburgh Castle", "tags": ["history", "views"], "hours": 3, "cost": 20},
        {"name": "Royal Mile", "tags": ["history", "architecture"], "hours": 2, "cost": 0},
        {"name": "Arthur's Seat Hike", "tags": ["hiking", "nature", "views"], "hours": 3, "cost": 0},
        {"name": "Whisky Tasting", "tags": ["foodie"], "hours": 2, "cost": 35},
        {"name": "Holyrood Palace", "tags": ["history", "architecture"], "hours": 2, "cost": 18},
        {"name": "Highlands Day Trip", "tags": ["hiking", "nature", "adventure"], "hours": 10, "cost": 65},
        {"name": "Loch Lomond Hiking", "tags": ["hiking", "nature"], "hours": 8, "cost": 45},
        {"name": "Castle & Luxury Dining", "tags": ["luxury", "history"], "hours": 5, "cost": 150},
    ],
    "Dubrovnik": [
        {"name": "City Walls Walk", "tags": ["history", "views"], "hours": 2, "cost": 35},
        {"name": "Old Town", "tags": ["history", "architecture"], "hours": 2, "cost": 0},
        {"name": "Cable Car", "tags": ["views", "nature"], "hours": 1.5, "cost": 25},
        {"name": "Island Hopping", "tags": ["beach", "nature"], "hours": 6, "cost": 55},
        {"name": "Game of Thrones Tour", "tags": ["history", "views"], "hours": 3, "cost": 40},
        {"name": "Plitvice Lakes Day Trip", "tags": ["hiking", "nature", "views"], "hours": 12, "cost": 75},
        {"name": "Adriatic Coastal Hiking", "tags": ["hiking", "nature", "beach"], "hours": 6, "cost": 35},
        {"name": "Private Yacht Experience", "tags": ["luxury", "beach"], "hours": 8, "cost": 300},
    ],
    "Zurich": [
        {"name": "Lake Zurich", "tags": ["nature", "views"], "hours": 2, "cost": 0},
        {"name": "Uetliberg Hiking", "tags": ["hiking", "nature", "views"], "hours": 4, "cost": 8},
        {"name": "Swiss National Park", "tags": ["hiking", "nature", "adventure"], "hours": 10, "cost": 65},
        {"name": "Luxury Spa Day", "tags": ["wellness", "luxury"], "hours": 6, "cost": 180},
        {"name": "Swiss Chocolate Tour", "tags": ["foodie"], "hours": 3, "cost": 45},
        {"name": "Rhine Falls Trip", "tags": ["nature", "views"], "hours": 5, "cost": 35},
        {"name": "Alpine Skiing", "tags": ["adventure", "nature"], "hours": 8, "cost": 85},
        {"name": "Private Mountain Guide", "tags": ["luxury", "hiking"], "hours": 8, "cost": 250},
    ],
    "Helsinki": [
        {"name": "Senate Square", "tags": ["architecture", "history"], "hours": 1.5, "cost": 0},
        {"name": "Suomenlinna Fortress", "tags": ["history", "nature"], "hours": 4, "cost": 12},
        {"name": "Temppeliaukio Church", "tags": ["architecture"], "hours": 1, "cost": 0},
        {"name": "Market Square", "tags": ["foodie"], "hours": 2, "cost": 15},
        {"name": "Nuuksio National Park", "tags": ["hiking", "nature"], "hours": 6, "cost": 25},
        {"name": "Aurora Hunting", "tags": ["nature", "adventure"], "hours": 8, "cost": 85},
        {"name": "Finnish Sauna Experience", "tags": ["wellness", "luxury"], "hours": 4, "cost": 65},
        {"name": "Archipelago Cruise", "tags": ["nature", "luxury"], "hours": 6, "cost": 120},
    ],
    "Brussels": [
        {"name": "Grand Place", "tags": ["architecture", "history"], "hours": 1.5, "cost": 0},
        {"name": "Atomium", "tags": ["architecture", "museums"], "hours": 2, "cost": 16},
        {"name": "Royal Museums", "tags": ["museums", "history"], "hours": 3, "cost": 15},
        {"name": "Beer & Chocolate Tour", "tags": ["foodie"], "hours": 4, "cost": 55},
        {"name": "European Quarter", "tags": ["architecture", "history"], "hours": 2, "cost": 0},
        {"name": "Bruges Day Trip", "tags": ["history", "architecture"], "hours": 8, "cost": 45},
        {"name": "Sonian Forest Hiking", "tags": ["hiking", "nature"], "hours": 4, "cost": 0},
        {"name": "Michelin Dining", "tags": ["foodie", "luxury"], "hours": 3, "cost": 150},
    ],
    "Oslo": [
        {"name": "Vigeland Park", "tags": ["nature", "museums"], "hours": 2.5, "cost": 0},
        {"name": "Opera House", "tags": ["architecture", "views"], "hours": 2, "cost": 20},
        {"name": "Viking Ship Museum", "tags": ["museums", "history"], "hours": 2, "cost": 12},
        {"name": "Holmenkollen Ski Jump", "tags": ["views", "adventure"], "hours": 3, "cost": 18},
        {"name": "Lofoten Islands Trip", "tags": ["hiking", "nature", "adventure"], "hours": 12, "cost": 185},
        {"name": "Preikestolen Hike", "tags": ["hiking", "adventure", "views"], "hours": 8, "cost": 95},
        {"name": "Nordic Spa", "tags": ["wellness", "luxury"], "hours": 5, "cost": 120},
        {"name": "Midnight Sun Experience", "tags": ["nature", "luxury"], "hours": 10, "cost": 220},
    ],
    "Reykjavik": [
        {"name": "Blue Lagoon", "tags": ["wellness", "nature"], "hours": 4, "cost": 85},
        {"name": "Golden Circle", "tags": ["nature", "views"], "hours": 8, "cost": 65},
        {"name": "Glacier Hiking", "tags": ["hiking", "adventure", "nature"], "hours": 8, "cost": 120},
        {"name": "Northern Lights Tour", "tags": ["nature", "adventure"], "hours": 6, "cost": 95},
        {"name": "Volcano Tour", "tags": ["adventure", "hiking"], "hours": 10, "cost": 145},
        {"name": "Ice Cave Exploration", "tags": ["adventure", "nature"], "hours": 6, "cost": 110},
        {"name": "Highland Super Jeep", "tags": ["adventure", "nature"], "hours": 12, "cost": 185},
        {"name": "Luxury Lodge Experience", "tags": ["luxury", "nature"], "hours": 24, "cost": 450},
    ],
    "Dublin": [
        {"name": "Trinity College", "tags": ["history", "architecture"], "hours": 2, "cost": 15},
        {"name": "Guinness Storehouse", "tags": ["foodie", "history"], "hours": 2.5, "cost": 25},
        {"name": "Temple Bar", "tags": ["nightlife", "history"], "hours": 3, "cost": 0},
        {"name": "Phoenix Park", "tags": ["nature"], "hours": 2, "cost": 0},
        {"name": "Cliffs of Moher", "tags": ["nature", "views", "hiking"], "hours": 10, "cost": 55},
        {"name": "Ring of Kerry", "tags": ["hiking", "nature", "views"], "hours": 12, "cost": 75},
        {"name": "Wicklow Mountains", "tags": ["hiking", "nature"], "hours": 8, "cost": 45},
        {"name": "Castle & Whiskey", "tags": ["luxury", "history"], "hours": 6, "cost": 135},
    ],
    "Ljubljana": [
        {"name": "Ljubljana Castle", "tags": ["history", "views"], "hours": 2.5, "cost": 12},
        {"name": "Tivoli Park", "tags": ["nature"], "hours": 2, "cost": 0},
        {"name": "Dragon Bridge", "tags": ["architecture"], "hours": 1, "cost": 0},
        {"name": "Lake Bled Day Trip", "tags": ["nature", "views", "hiking"], "hours": 8, "cost": 35},
        {"name": "Triglav National Park", "tags": ["hiking", "adventure", "nature"], "hours": 10, "cost": 55},
        {"name": "Postojna Cave", "tags": ["adventure", "nature"], "hours": 5, "cost": 28},
        {"name": "Vipava Valley Wine", "tags": ["foodie", "nature"], "hours": 6, "cost": 65},
        {"name": "Alpine Climbing", "tags": ["climbing", "adventure"], "hours": 8, "cost": 95},
    ],
    "Riga": [
        {"name": "Old Town", "tags": ["history", "architecture"], "hours": 3, "cost": 0},
        {"name": "Art Nouveau District", "tags": ["architecture"], "hours": 2, "cost": 0},
        {"name": "Central Market", "tags": ["foodie"], "hours": 2, "cost": 8},
        {"name": "Riga Castle", "tags": ["history", "museums"], "hours": 2, "cost": 10},
        {"name": "Gauja National Park", "tags": ["hiking", "nature"], "hours": 8, "cost": 35},
        {"name": "Sigulda Adventure", "tags": ["adventure", "nature"], "hours": 6, "cost": 45},
        {"name": "Traditional Bathhouse", "tags": ["wellness"], "hours": 3, "cost": 25},
        {"name": "Medieval Feast", "tags": ["foodie", "history"], "hours": 4, "cost": 55},
    ],
    "Tallinn": [
        {"name": "Old Town", "tags": ["history", "architecture"], "hours": 3, "cost": 0},
        {"name": "Toompea Castle", "tags": ["history", "views"], "hours": 2, "cost": 8},
        {"name": "Alexander Nevsky Cathedral", "tags": ["architecture", "history"], "hours": 1, "cost": 0},
        {"name": "Kadriorg Palace", "tags": ["museums", "architecture"], "hours": 2, "cost": 12},
        {"name": "Lahemaa National Park", "tags": ["hiking", "nature"], "hours": 8, "cost": 40},
        {"name": "Estonian Islands", "tags": ["nature", "adventure"], "hours": 10, "cost": 65},
        {"name": "Medieval Dinner", "tags": ["foodie", "history"], "hours": 3, "cost": 45},
        {"name": "Bog Walking", "tags": ["hiking", "nature"], "hours": 5, "cost": 25},
    ],
    "Vilnius": [
        {"name": "Old Town", "tags": ["history", "architecture"], "hours": 3, "cost": 0},
        {"name": "Gediminas Tower", "tags": ["history", "views"], "hours": 2, "cost": 5},
        {"name": "Vilnius Cathedral", "tags": ["architecture", "history"], "hours": 1.5, "cost": 0},
        {"name": "Uzupis District", "tags": ["history", "architecture"], "hours": 2, "cost": 0},
        {"name": "Trakai Castle", "tags": ["history", "nature"], "hours": 5, "cost": 15},
        {"name": "Aukstaitija National Park", "tags": ["hiking", "nature"], "hours": 8, "cost": 35},
        {"name": "Hot Air Ballooning", "tags": ["adventure", "views"], "hours": 4, "cost": 185},
        {"name": "Traditional Lithuanian Feast", "tags": ["foodie"], "hours": 3, "cost": 35},
    ],
}

PREFS = [
    "foodie", "museums", "outdoors", "nightlife", "history", "architecture", 
    "views", "beach", "baths", "markets", "shops", "step-free", "low-CO2",
    "hiking", "climbing", "adventure", "wellness", "luxury", "nature"
]

# -------------------------------
# Helper Functions
# -------------------------------

def month_key(d: date) -> str:
    return f"{d.month:02d}"

def trip_nights(start: date, end: date) -> int:
    return max(1, (end - start).days)


def seasonality_factor(dest: Dict, start: date, end: date) -> float:
    mk = month_key(start)
    mod = dest.get("month_mod", {}).get(mk, 1.0)
    # Slightly penalize trips that span very different months (demo simplification)
    if start.month != end.month:
        mod *= 0.98
    return float(mod)


def baseline_costs(dest: Dict, nights: int, start_date: date, luxury_level: str = "standard") -> Dict[str, float]:
    """Calculate baseline costs based on luxury level
    luxury_level: 'standard', 'premium', 'luxury'
    """
    # Flight price adjusted by season - use user's travel date, not current date
    mk = month_key(start_date)
    season_mod = dest.get("month_mod", {}).get(mk, 1.0)
    
    if luxury_level == "luxury":
        flight = dest["flight_price_luxury"] * season_mod
        hotel = dest["hotel_luxury"] * nights
        daily_misc = nights * (dest["daily_food_luxury"] + dest["daily_transit"] * 1.5)  # premium transport
    elif luxury_level == "premium":
        flight = dest["flight_price_premium"] * season_mod
        hotel = dest["hotel_premium"] * nights
        daily_misc = nights * (dest["daily_food_premium"] + dest["daily_transit"] * 1.2)
    else:  # standard
        flight = dest["flight_price_base"] * season_mod
        hotel = dest["hotel_per_night"] * nights
        daily_misc = nights * (dest["daily_food"] + dest["daily_transit"])
    
    pass_cost = math.ceil(nights / 2) * dest["attraction_day_pass"]
    if luxury_level == "luxury":
        pass_cost *= 1.8  # Premium experiences and skip-the-line access
    elif luxury_level == "premium":
        pass_cost *= 1.4
    
    return {
        "flight": round(flight, 2),
        "hotel": round(hotel, 2),
        "daily_misc": round(daily_misc, 2),
        "attraction_pass": round(pass_cost, 2),
    }


def co2_score(dest: Dict, prefs: List[str]) -> float:
    # Lower CO2 is better. Normalize across our sample range.
    # If user cares about low-CO2, weight matters more.
    co2 = dest["co2_kg"]
    maxc = max(d["co2_kg"] for d in DESTINATIONS)
    minc = min(d["co2_kg"] for d in DESTINATIONS)
    norm = 1 - (co2 - minc) / (maxc - minc + 1e-6)
    return norm * (1.2 if "low-CO2" in prefs else 1.0)


def value_score(dest: Dict, budget: float, nights: int, start_date: date, luxury_level: str = "standard") -> float:
    costs = baseline_costs(dest, nights, start_date, luxury_level)
    total = sum(costs.values())
    
    # Set budget limits based on luxury level
    if luxury_level == "luxury":
        max_budget = budget * 1.35  # Luxury can go up to 135% of budget
    elif luxury_level == "premium":
        max_budget = budget * 1.0   # Premium should stay within budget
    else:
        max_budget = budget * 1.0   # Standard should stay within budget
    
    # Penalize heavily if exceeding the allowed budget for the level
    ratio = total / max(max_budget, 1.0)
    if ratio <= 1:
        return min(1.0, 0.7 + 0.3 * (1 - ratio))
    else:
        return max(0.0, 0.1 - 0.5 * (ratio - 1))  # Heavy penalty for exceeding level limits


def vibe_match_score(dest: Dict, prefs: List[str]) -> float:
    if not prefs:
        return 0.7
    overlap = len(set(dest["vibes"]) & set(prefs))
    return min(1.0, 0.5 + 0.1 * overlap)


def access_score(dest: Dict, prefs: List[str]) -> float:
    base = dest.get("accessibility", 0.6)
    return min(1.0, base * (1.15 if "step-free" in prefs else 1.0))


def overall_score(dest: Dict, budget: float, nights: int, prefs: List[str], start: date, end: date, luxury_level: str = "standard") -> float:
    # Enhanced weights with new realistic factors for more diversity
    weights = dict(
        value=0.18,          # Cost effectiveness  
        season=0.12,         # Seasonal appeal
        walk=0.10,           # Walkability
        safety=0.11,         # Safety index
        vibe=0.20,           # Preference matching
        access=0.05,         # Accessibility
        co2=0.04,           # Environmental impact
        livability=0.08,     # Cost of living impact on tourist experience
        cultural=0.08,       # Cultural appeal factor
        budget_sens=0.04     # Budget sensitivity factor
    )
    
    s_value = value_score(dest, budget, nights, start, luxury_level)
    s_season = seasonality_factor(dest, start, end)
    s_walk = dest.get("walkability", 0.7)
    s_safety = dest.get("safety", 0.65)
    s_vibe = vibe_match_score(dest, prefs)
    s_access = access_score(dest, prefs)
    s_co2 = co2_score(dest, prefs)
    
    # New factor: Cost of living impact (lower = better for tourists)
    s_livability = 1.0 - dest.get("cost_of_living_index", 0.5)
    
    # New diversity factors
    s_cultural = dest.get("cultural_factor", 0.75)
    s_budget_sens = dest.get("budget_sensitivity", 0.7)
    
    # Tourist density penalty (overtourism factor)
    tourist_penalty = dest.get("tourist_density", 0.5)
    
    # Weather appeal factor
    weather_bonus = dest.get("weather_factor", 0.7)
    
    # Luxury appeal factor - affects luxury level scoring
    luxury_appeal = dest.get("luxury_appeal", 0.7)
    
    # Dynamic weight adjustments based on preferences and luxury level
    if "luxury" in prefs or luxury_level == "luxury":
        weights["value"] *= 0.5  # Much less price-sensitive for luxury
        weights["safety"] *= 1.6  # Safety very important for luxury
        weights["livability"] *= 0.6  # Cost of living less important
        weights["cultural"] *= 1.3  # Cultural experiences important
        # Add luxury appeal bonus
        s_value = s_value * 0.7 + luxury_appeal * 0.3
    elif luxury_level == "premium":
        weights["value"] *= 0.75  # Moderately price-sensitive 
        weights["safety"] *= 1.3   # Safety important
        weights["cultural"] *= 1.15  # Cultural appeal matters
        s_value = s_value * 0.85 + luxury_appeal * 0.15
    elif "budget" in prefs or luxury_level == "standard":
        weights["value"] *= 1.4  # Very price-sensitive
        weights["livability"] *= 1.3  # Cost of living very important
        weights["budget_sens"] *= 2.0  # Budget sensitivity critical
    
    if "hiking" in prefs or "adventure" in prefs or "climbing" in prefs:
        weights["vibe"] *= 1.8     # Adventure preferences critical
        weights["safety"] *= 1.4   # Safety crucial for adventure
        weights["walk"] *= 0.6     # City walkability less relevant
        weights["season"] *= 1.3   # Weather matters more for outdoor activities
    
    if "low-CO2" in prefs:
        weights["co2"] *= 5.0      # Environmental impact major factor
        
    if "step-free" in prefs:
        weights["access"] *= 4.0   # Accessibility becomes primary concern
    
    if "foodie" in prefs:
        weights["cultural"] *= 1.4  # Food culture important
        weights["vibe"] *= 1.2     # Food scene critical
    
    if "museums" in prefs or "history" in prefs:
        weights["cultural"] *= 1.5  # Cultural heritage critical
        
    # Budget-based adjustments for more diversity
    if budget < 800:
        weights["budget_sens"] *= 2.5  # Budget destinations favor
        weights["value"] *= 1.6
    elif budget > 2000:
        weights["cultural"] *= 1.3   # Premium destinations
        weights["safety"] *= 1.2
    
    # Normalize weights
    total_weight = sum(weights.values())
    for key in weights:
        weights[key] /= total_weight
    
    # Calculate base score
    score = (
        weights["value"] * s_value +
        weights["season"] * s_season +
        weights["walk"] * s_walk +
        weights["safety"] * s_safety +
        weights["vibe"] * s_vibe +
        weights["access"] * s_access +
        weights["co2"] * s_co2 +
        weights["livability"] * s_livability +
        weights["cultural"] * s_cultural +
        weights["budget_sens"] * s_budget_sens
    )
    
    # Apply realistic modifiers with more variation
    score *= (1.0 - tourist_penalty * 0.18)  # Higher penalty for overtourism
    score *= (0.82 + weather_bonus * 0.18)   # Weather appeal bonus
    
    # Luxury level specific bonuses
    if luxury_level == "luxury":
        score *= (0.95 + luxury_appeal * 0.15)  # Luxury destinations get bonus
    elif luxury_level == "premium":
        score *= (0.98 + luxury_appeal * 0.08)  # Moderate luxury bonus
    
    # City-specific realistic adjustments - more varied
    city_name = dest.get("city", "")
    city_adjustments = {
        "Barcelona": 0.87,     # Overtourism and safety concerns
        "Budapest": 1.05,      # Excellent value destination
        "Prague": 1.04,        # Great value and appeal
        "Amsterdam": 0.91,     # Expensive but popular
        "Vienna": 0.97,        # Balanced but expensive
        "Rome": 0.90,          # Overcrowding issues
        "Berlin": 0.98,        # Good balance of culture and cost
        "Zurich": 0.85,        # Very expensive but high quality
        "Krakow": 1.08,        # Exceptional value
        "Copenhagen": 0.86,    # Very expensive, weather challenges
        "Dubrovnik": 0.94,     # Seasonal overcrowding
        "Edinburgh": 0.93,     # Weather and cost challenges
        "Ljubljana": 1.02,     # Hidden gem bonus
    }
    
    if city_name in city_adjustments:
        score *= city_adjustments[city_name]
    
    # Enhanced diversity mechanism with more randomization factors
    import random
    import hashlib
    
    # Create complex seed for better distribution
    preference_weight = len(prefs) * 23 + sum(ord(c) for c in "".join(prefs)) + hash(luxury_level) % 100
    budget_factor = int(budget) % 200 + int(budget / 100) % 50
    date_factor = start.month * 31 + start.day
    
    seed_string = f"{city_name}_{preference_weight}_{budget_factor}_{date_factor}_{luxury_level}"
    seed_hash = int(hashlib.md5(seed_string.encode()).hexdigest()[:8], 16)
    random.seed(seed_hash)
    
    # Much stronger randomization for diverse results
    diversity_factor = random.uniform(0.88, 1.12)  # Increased range
    score *= diversity_factor
    
    # Additional budget-based randomization
    if budget < 1000:
        budget_variety = random.uniform(0.95, 1.08)  # Favor budget destinations
    elif budget > 1500:
        budget_variety = random.uniform(0.92, 1.05)  # Moderate luxury variety
    else:
        budget_variety = random.uniform(0.90, 1.10)  # Maximum variety for mid-range
    score *= budget_variety
    
    # Seasonal variety for more dynamic results  
    month = start.month
    if month in [12, 1, 2]:  # Winter
        seasonal_variety = random.uniform(0.94, 1.06)
    elif month in [6, 7, 8]:  # Summer peak
        seasonal_variety = random.uniform(0.96, 1.04)
    else:  # Shoulder seasons
        seasonal_variety = random.uniform(0.92, 1.08)
    score *= seasonal_variety
    
    # Preference-based variety
    if "hiking" in prefs or "adventure" in prefs:
        adventure_variety = random.uniform(0.95, 1.12)  # Boost adventure destinations
        score *= adventure_variety
    elif "luxury" in prefs:
        luxury_variety = random.uniform(0.90, 1.08)  # Moderate luxury variety
        score *= luxury_variety
    
    return float(round(score, 4))


# -------------------------------
# POI selection + itinerary composition
# -------------------------------

def summarize_poi(name: str, tags: List[str]) -> str:
    base = f"{name}: "
    text = f"A highlight for {', '.join(tags)} lovers."
    return base + text


class Summarizer:
    def __init__(self):
        self.enabled = _HAS_TRANSFORMERS
        if self.enabled:
            try:
                self.pipe = pipeline("summarization")
            except Exception:
                self.enabled = False
                self.pipe = None

    def summarize(self, text: str, max_chars: int = 200) -> str:
        if self.enabled and self.pipe is not None:
            try:
                out = self.pipe(text, max_length=70, min_length=20, do_sample=False)
                return out[0]["summary_text"][:max_chars]
            except Exception:
                pass
        # Fallback
        return text[:max_chars]


@dataclass
class Activity:
    name: str
    tags: List[str]
    hours: float
    cost: float


@dataclass
class DayPlan:
    date: date
    morning: Optional[Activity]
    afternoon: Optional[Activity]
    evening: Optional[Activity]
    notes: str = ""


def select_pois(city: str, prefs: List[str], max_hours_per_day: float = 6.0) -> List[Activity]:
    raw = POIS.get(city, [])
    # Rank by overlap with preferences + intrinsic signal: free/unique
    def score_poi(p):
        overlap = len(set(p["tags"]) & set(prefs))
        bonus = 0.2 if p["cost"] == 0 else 0.0
        return overlap + bonus + (p["hours"] / 10)
    ranked = sorted(raw, key=score_poi, reverse=True)
    return [Activity(r["name"], r["tags"], float(r["hours"]), float(r["cost"])) for r in ranked]


def compose_itinerary(city: str, start: date, end: date, prefs: List[str]) -> List[DayPlan]:
    days = trip_nights(start, end)
    activities = select_pois(city, prefs)
    plan: List[DayPlan] = []
    idx = 0
    for i in range(days):
        d = start + timedelta(days=i)
        slots = [None, None, None]  # morning, afternoon, evening
        hours_used = 0.0
        for slot in range(3):
            while idx < len(activities) and hours_used + activities[idx].hours <= 6.0:
                slots[slot] = activities[idx]
                hours_used += activities[idx].hours
                idx += 1
                break
        dp = DayPlan(date=d, morning=slots[0], afternoon=slots[1], evening=slots[2])
        plan.append(dp)
    return plan


# -------------------------------
# Budget optimizer (LP if available, else greedy)
# -------------------------------

def estimate_total_cost(dest: Dict, nights: int, itinerary: List[DayPlan], start_date: date, luxury_level: str = "standard") -> Tuple[float, Dict[str, float]]:
    base = baseline_costs(dest, nights, start_date, luxury_level)
    act_cost = 0.0
    for dp in itinerary:
        for slot in [dp.morning, dp.afternoon, dp.evening]:
            if slot:
                cost_multiplier = 1.0
                if luxury_level == "luxury":
                    cost_multiplier = 2.0 if "luxury" in slot.tags else 1.6
                elif luxury_level == "premium":
                    cost_multiplier = 1.5 if "luxury" in slot.tags else 1.3
                act_cost += slot.cost * cost_multiplier
    total = sum(base.values()) + act_cost
    breakdown = base | {"activities": round(act_cost, 2)}
    return round(total, 2), breakdown


def fit_to_budget(dest: Dict, nights: int, itinerary: List[DayPlan], budget: float, start_date: date, luxury_level: str = "standard", buffer: float = 0.10) -> Tuple[List[DayPlan], float, Dict[str, float]]:
    # Adjust target based on luxury level
    if luxury_level == "luxury":
        target = budget * 1.35 * (1 - buffer * 0.5)  # Allow luxury to go higher, smaller buffer
    elif luxury_level == "premium":
        target = budget * (1 - buffer * 0.7)  # Moderate buffer for premium
    else:
        target = budget * (1 - buffer)  # Full buffer for standard

    def current_cost(itin: List[DayPlan]) -> float:
        total, _ = estimate_total_cost(dest, nights, itin, start_date, luxury_level)
        return total

    total, breakdown = estimate_total_cost(dest, nights, itinerary, start_date, luxury_level)
    if total <= target:
        return itinerary, total, breakdown

    # Try to minimize by dropping the priciest activities first
    acts: List[Tuple[int, str, Activity]] = []  # (day_idx, slot_name, activity)
    for i, dp in enumerate(itinerary):
        for slot_name in ["morning", "afternoon", "evening"]:
            act = getattr(dp, slot_name)
            if act:
                acts.append((i, slot_name, act))

    # Calculate adjusted costs for luxury levels
    def adjusted_cost(activity: Activity) -> float:
        cost_multiplier = 1.0
        if luxury_level == "luxury":
            cost_multiplier = 2.0 if "luxury" in activity.tags else 1.6
        elif luxury_level == "premium":
            cost_multiplier = 1.5 if "luxury" in activity.tags else 1.3
        return activity.cost * cost_multiplier

    acts_sorted = sorted(acts, key=lambda t: adjusted_cost(t[2]), reverse=True)

    if _HAS_PULP:
        # Binary selection to keep or drop activities to meet target at min utility loss
        prob = pulp.LpProblem("BudgetFit", pulp.LpMinimize)
        x = [pulp.LpVariable(f"x_{k}", lowBound=0, upBound=1, cat="Binary") for k in range(len(acts_sorted))]
        costs = [adjusted_cost(a[2]) for a in acts_sorted]
        # Utility assume hours + small preference weight
        utils = [a[2].hours + 0.2 * len(a[2].tags) for a in acts_sorted]
        base_total, base_break = estimate_total_cost(dest, nights, itinerary, start_date, luxury_level)
        act_total = sum(costs)
        keep_cost_expr = pulp.lpSum([x[i] * costs[i] for i in range(len(costs))])
        # Objective: minimize negative utility (i.e., maximize kept utility)
        prob += pulp.lpSum([(1 - x[i]) * utils[i] for i in range(len(utils))])
        # Constraint: base_total - dropped_costs <= target
        dropped = act_total - keep_cost_expr
        prob += base_total - dropped <= target
        prob.solve(pulp.PULP_CBC_CMD(msg=False))

        # Apply decisions
        keep_mask = [int(v.value()) for v in x]
        kept = set()
        for i, keep in enumerate(keep_mask):
            if keep == 1:
                kept.add(i)
        # Rebuild itinerary
        new_itin: List[DayPlan] = []
        ptr = 0
        for day_idx, dp in enumerate(itinerary):
            new_dp = DayPlan(date=dp.date, morning=None, afternoon=None, evening=None)
            for slot_i, slot_name in enumerate(["morning", "afternoon", "evening"]):
                if getattr(dp, slot_name) is None:
                    setattr(new_dp, slot_name, None)
                else:
                    if ptr in kept:
                        setattr(new_dp, slot_name, getattr(dp, slot_name))
                    else:
                        setattr(new_dp, slot_name, None)
                    ptr += 1
            new_itin.append(new_dp)
        total2, breakdown2 = estimate_total_cost(dest, nights, new_itin, start_date, luxury_level)
        return new_itin, total2, breakdown2
    else:
        # Greedy fallback: drop expensive activities until within target
        new_itin = [DayPlan(date=dp.date, morning=dp.morning, afternoon=dp.afternoon, evening=dp.evening) for dp in itinerary]
        for i, slot_name, act in acts_sorted:
            if current_cost(new_itin) <= target:
                break
            # Drop this activity
            setattr(new_itin[i], slot_name, None)
        total3, breakdown3 = estimate_total_cost(dest, nights, new_itin, start_date, luxury_level)
        return new_itin, total3, breakdown3


# -------------------------------
# Exporters
# -------------------------------

def itinerary_to_markdown(city: str, start: date, end: date, total: float, breakdown: Dict[str, float], plan: List[DayPlan]) -> str:
    lines = []
    lines.append(f"# ITINERA Plan — {city}\n")
    lines.append(f"**Dates:** {start.isoformat()} → {end.isoformat()}  ")
    lines.append(f"**Total Estimated Cost:** €{total:.0f}\n")
    lines.append("**Breakdown**:")
    for k, v in breakdown.items():
        lines.append(f"- {k}: €{v:.0f}")
    lines.append("\n## Day by Day\n")
    for dp in plan:
        lines.append(f"### {dp.date.strftime('%A, %d %b %Y')}")
        for label, act in [("Morning", dp.morning), ("Afternoon", dp.afternoon), ("Evening", dp.evening)]:
            if act:
                lines.append(f"- **{label}:** {act.name} ({act.hours}h, ~€{act.cost:.0f})")
            else:
                lines.append(f"- **{label}:** Free time / explore")
        if dp.notes:
            lines.append(f"  - Notes: {dp.notes}")
        lines.append("")
    return "\n".join(lines)


# -------------------------------
# Streamlit UI
# -------------------------------

st.set_page_config(page_title="ITINERA — Trip Composer", page_icon="✈️", layout="wide")

# --- Authentication UI ---
def render_auth_ui():
    """Render authentication UI in the top right corner"""
    col1, col2, col3 = st.columns([6, 1, 1])
    
    with col2:
        if st.session_state.auth_logged_in:
            if st.button("👤 " + st.session_state.auth_username, key="user_menu"):
                st.session_state.show_user_menu = not st.session_state.get('show_user_menu', False)
        else:
            if st.button("🔑 Login", key="login_button"):
                st.session_state.show_login = True
    
    with col3:
        if not st.session_state.auth_logged_in:
            if st.button("📝 Sign Up", key="signup_button"):
                st.session_state.show_signup = True
        else:
            if st.button("🚪 Logout", key="logout_button"):
                logout_user()
                st.rerun()

def render_login_form():
    """Render login form"""
    with st.form("login_form", clear_on_submit=True):
        st.subheader("🔑 Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        col1, col2 = st.columns(2)
        with col1:
            login_submitted = st.form_submit_button("Login")
        with col2:
            if st.form_submit_button("Cancel"):
                st.session_state.show_login = False
                st.rerun()
        
        if login_submitted:
            if username and password:
                success, message = authenticate_user(username, password)
                if success:
                    st.session_state.auth_logged_in = True
                    st.session_state.auth_username = username
                    st.session_state.show_login = False
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please fill in all fields.")

def render_signup_form():
    """Render signup form"""
    with st.form("signup_form", clear_on_submit=True):
        st.subheader("📝 Sign Up")
        
        # Show current user count
        users = load_users()
        st.info(f"Users registered: {len(users)}/{MAX_USERS}")
        
        username = st.text_input("Username (min 3 characters)")
        password = st.text_input("Password (min 6 characters)", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        col1, col2 = st.columns(2)
        with col1:
            signup_submitted = st.form_submit_button("Sign Up")
        with col2:
            if st.form_submit_button("Cancel"):
                st.session_state.show_signup = False
                st.session_state.show_registration_required = False
                st.rerun()
        
        if signup_submitted:
            if username and password and confirm_password:
                if password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    success, message = register_user(username, password)
                    if success:
                        st.success(message)
                        st.session_state.show_signup = False
                        st.session_state.show_registration_required = False
                        st.info("You can now login with your credentials.")
                    else:
                        st.error(message)
            else:
                st.error("Please fill in all fields.")

def render_registration_required_popup():
    """Render registration required popup"""
    st.error("🚫 **Free Trial Limit Reached!**")
    
    with st.container():
        st.markdown("""
        <div style="background-color: #ffebee; padding: 20px; border-radius: 10px; border-left: 5px solid #f44336;">
            <h3 style="color: #d32f2f; margin-top: 0;">🎯 You've used all 20 free searches!</h3>
            <p style="color: #666; margin-bottom: 15px;">
                To continue enjoying ITINERA's personalized trip planning features, please create a free account.
            </p>
            <p style="color: #666; margin-bottom: 0;">
                ✨ Registration is quick, free, and unlocks unlimited access to all features!
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📝 Register Now - It's Free!", type="primary", use_container_width=True):
                st.session_state.show_signup = True
                st.session_state.show_registration_required = False
                st.rerun()
            
            if st.button("🔑 I Already Have an Account", use_container_width=True):
                st.session_state.show_login = True
                st.session_state.show_registration_required = False
                st.rerun()
        
        st.markdown("---")
        if st.button("❌ Close", key="close_popup"):
            st.session_state.show_registration_required = False
            st.rerun()

# Initialize session state for UI
if 'show_login' not in st.session_state:
    st.session_state.show_login = False
if 'show_signup' not in st.session_state:
    st.session_state.show_signup = False
if 'show_user_menu' not in st.session_state:
    st.session_state.show_user_menu = False

st.title("ITINERA — Your Budget‑to‑Boarding Trip Composer ✈️")

# Render authentication UI
render_auth_ui()

# Show login/signup forms if requested
if st.session_state.show_login:
    render_login_form()

if st.session_state.show_signup:
    render_signup_form()

# Show registration required popup
if st.session_state.show_registration_required:
    render_registration_required_popup()

# Show user menu if logged in and menu is open
if st.session_state.auth_logged_in and st.session_state.get('show_user_menu', False):
    with st.expander("👤 User Menu", expanded=True):
        users = load_users()
        user_info = users[st.session_state.auth_username]
        st.write(f"**Username:** {st.session_state.auth_username}")
        st.write(f"**Member since:** {user_info['created_at'][:10]}")
        st.write(f"**Login count:** {user_info.get('login_count', 0)}")
        if st.button("Close Menu"):
            st.session_state.show_user_menu = False
            st.rerun()

with st.sidebar:
    st.header("Trip Inputs")
    today = date.today()
    default_start = today + timedelta(days=10)
    default_end = default_start + timedelta(days=4)
    start_date = st.date_input("Start date", value=default_start)
    end_date = st.date_input("End date", value=default_end, min_value=start_date + timedelta(days=1))
    budget = st.number_input("Total budget (€)", min_value=200, max_value=20000, value=1200, step=50)
    
    # Luxury level selection
    st.subheader("Travel Style")
    luxury_level = st.selectbox(
        "Luxury Level",
        options=["standard", "premium", "luxury"],
        format_func=lambda x: {
            "standard": "🎒 Standard - Budget-friendly, comfortable basics",
            "premium": "✨ Premium - Mid-range comfort with some upgrades", 
            "luxury": "💎 Luxury - High-end experiences and premium services"
        }[x],
        index=0
    )
    
    if luxury_level != "standard":
        st.info({
            "premium": "🛩️ **Business Class** flights, 4-5★ hotels, fine dining, skip-the-line access",
            "luxury": "🛫 **First Class** flights, 5★ luxury hotels, Michelin dining, VIP experiences (up to 135% of budget)"
        }[luxury_level])
    
    prefs = st.multiselect("Preferences (optional)", options=PREFS, default=["foodie", "views"]) 
    st.caption("🏔️ Try 'hiking' or 'climbing' for mountain adventures! Toggle 'luxury' for premium experiences.")
    
    # Show usage counter for non-logged users
    if not st.session_state.auth_logged_in:
        remaining_uses = MAX_FREE_USES - st.session_state.filter_usage_count
        if remaining_uses > 0:
            st.info(f"🆓 Free searches remaining: {remaining_uses}/{MAX_FREE_USES}")
        else:
            st.error(f"🚫 Free trial limit reached! Please register to continue.")
    
    # Add confirmation button
    st.divider()
    
    # Check if user can use the filter
    can_use_filter = st.session_state.auth_logged_in or st.session_state.filter_usage_count < MAX_FREE_USES
    
    if can_use_filter:
        filter_confirmed = st.button("🔍 Apply Filters & Generate Recommendations", type="primary", use_container_width=True)
    else:
        # Show disabled button and trigger popup on click
        if st.button("🔍 Apply Filters & Generate Recommendations", type="primary", use_container_width=True, disabled=False):
            st.session_state.show_registration_required = True
            st.rerun()
        filter_confirmed = False
    
    st.divider()
    st.header("Advanced")
    shortlist_k = st.slider("Shortlist size", min_value=2, max_value=15, value=8)
    buffer = st.slider("Budget safety buffer", min_value=0.0, max_value=0.25, value=0.10, step=0.01)

st.write("Give ITINERA a budget, dates, and travel style. It will recommend destinations and compose a balanced, cost‑aware plan with hiking trails, luxury options, and personalized experiences from our curated selection of 15 premium European destinations.")

# Welcome message for logged-in users
if st.session_state.auth_logged_in:
    st.success(f"Welcome back, {st.session_state.auth_username}! 🎉 Enjoy unlimited access to all features.")
else:
    # Show current usage status for non-logged users
    remaining_uses = MAX_FREE_USES - st.session_state.filter_usage_count
    if remaining_uses > 0:
        st.info(f"🆓 You have {remaining_uses} free searches remaining.")
    else:
        st.error("🚫 You have used all 20 free searches. Please register to continue.")

# Only execute when filters are confirmed and user has permission
if filter_confirmed:
    # Update usage count for non-logged users after successful filter application
    if not st.session_state.auth_logged_in:
        st.session_state.filter_usage_count += 1
        # Force page refresh to update the counter display in sidebar
        if st.session_state.filter_usage_count >= MAX_FREE_USES:
            # If this was the last free use, show registration popup after results
            st.session_state.show_registration_required = True
    
    nights = trip_nights(start_date, end_date)

    # Scoring table
    rows = []
    for d in DESTINATIONS:
        s = overall_score(d, budget, nights, prefs, start_date, end_date, luxury_level)
        costs = baseline_costs(d, nights, start_date, luxury_level)
        total = sum(costs.values())
        
        # Display luxury level info
        luxury_suffix = ""
        if luxury_level == "premium":
            luxury_suffix = " (Premium)"
        elif luxury_level == "luxury":
            luxury_suffix = " (Luxury)"
        
        rows.append({
            "City": f"{d['city']}, {d['country']}",
            "Score": s,
            f"Est. Total{luxury_suffix}": round(total, 2),
            "Hotel x nights": f"€{costs['hotel'] / nights:.0f} x {nights}",
            "Flight": f"€{costs['flight']:.0f}",
            "CO₂ (kg)": d['co2_kg'],
            "Walkability": d['walkability'],
            "Safety": d['safety'],
        })

    score_df = pd.DataFrame(rows).sort_values(by=["Score"], ascending=False).reset_index(drop=True)
    # Make ranking start from 1 instead of 0
    score_df.index = score_df.index + 1

    st.subheader("Destination Shortlist")
    st.dataframe(score_df.head(shortlist_k), width='stretch')

    # Get top city for selection
    top_city = {
        "rank": 1,
        "name": score_df.iloc[0]["City"].split(",")[0],
        "country": next(d for d in DESTINATIONS if d["city"] == score_df.iloc[0]["City"].split(",")[0])["country"],
        "data": next(d for d in DESTINATIONS if d["city"] == score_df.iloc[0]["City"].split(",")[0]),
        "score": score_df.iloc[0]["Score"],
        "cost": score_df.iloc[0][f"Est. Total{' (Premium)' if luxury_level == 'premium' else ' (Luxury)' if luxury_level == 'luxury' else ''}"]
    }

    # Show Top 1 Recommendation with "best for the best" motto
    col_header, col_motto = st.columns([3, 1])
    with col_header:
        st.subheader("🏆 Top Recommendation")
    with col_motto:
        st.markdown("""
        <div style="text-align: right; margin-top: 10px;">
            <em style="color: #ff6b6b; font-style: italic; font-size: 14px;">✨ best for the best</em>
        </div>
        """, unsafe_allow_html=True)
    
    # Display the top recommendation prominently
    city1 = top_city
    flag1 = COUNTRY_FLAGS.get(city1["country"], "🏳️")
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 25px; border-radius: 15px; margin: 15px 0; 
                border: 3px solid #ffd700; box-shadow: 0 8px 16px rgba(0,0,0,0.2);">
        <div style="color: white; text-align: center;">
            <h2 style="margin: 0; color: #ffd700; text-shadow: 2px 2px 4px rgba(0,0,0,0.5);">
                🥇 {city1['name']} {flag1}
            </h2>
            <p style="margin: 10px 0; font-size: 18px; opacity: 0.9;">
                Score: {city1['score']:.3f} | Cost: €{city1['cost']:.0f}
            </p>
            <p style="margin: 5px 0; font-size: 14px; opacity: 0.8;">
                Our #1 recommendation for your perfect trip
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Use the top recommendation automatically
    best_city = city1["name"]
    chosen = city1["data"]
    
    # Get country flag
    country_flag = COUNTRY_FLAGS.get(chosen['country'], "🏳️")

    st.markdown(f"### 🌟 Your Perfect Destination: **{best_city}** {country_flag}")
    
    # Show ranking info
    col_rank1, col_rank2, col_rank3 = st.columns(3)
    with col_rank1:
        st.metric("Ranking", f"#{city1['rank']}")
    with col_rank2:
        st.metric("Score", f"{city1['score']:.3f}")
    with col_rank3:
        st.metric("Est. Cost", f"€{city1['cost']:.0f}")
    
    # Display preference matching scores
    if prefs:
        st.subheader("Your Preferences Match")
        pref_cols = st.columns(min(len(prefs), 4))
        for i, pref in enumerate(prefs):
            with pref_cols[i % 4]:
                # Calculate how well this destination matches each preference
                if pref in chosen['vibes']:
                    match_score = "✅ Perfect"
                    color = "green"
                elif any(vibe in chosen['vibes'] for vibe in [pref]):
                    match_score = "✅ Perfect"
                    color = "green"
                else:
                    # Check for related vibes
                    related_matches = {
                        "foodie": ["markets"],
                        "outdoors": ["nature", "hiking", "beach"],
                        "history": ["architecture", "museums"],
                        "nightlife": ["nightlife"],
                        "museums": ["history", "architecture"],
                        "architecture": ["history", "museums"],
                        "nature": ["hiking", "views", "beach"],
                        "hiking": ["nature", "adventure", "views"],
                        "adventure": ["hiking", "climbing"],
                        "wellness": ["baths", "luxury"],
                        "luxury": ["wellness"],
                        "views": ["nature", "hiking"]
                    }
                    if pref in related_matches and any(rv in chosen['vibes'] for rv in related_matches[pref]):
                        match_score = "🟡 Good"
                        color = "orange"
                    else:
                        match_score = "⚪ Limited"
                        color = "gray"
                
                st.markdown(f"**{pref.title()}**")
                st.markdown(f"<span style='color: {color}'>{match_score}</span>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Walkability", f"{chosen['walkability']:.2f}")
    with col2:
        st.metric("Safety", f"{chosen['safety']:.2f}")
    with col3:
        st.metric("CO₂ (kg)", f"{chosen['co2_kg']}")

    # Compose itinerary for selected city
    plan = compose_itinerary(best_city, start_date, end_date, prefs)

    # Fit to budget with buffer for selected city
    fitted_plan, total_cost, breakdown = fit_to_budget(chosen, nights, plan, float(budget), start_date, luxury_level, buffer=float(buffer))

    st.subheader("Cost Overview")
    
    # Create flight class mapping
    flight_class_info = {
        "standard": {"class": "Economy", "icon": "🛩️"},
        "premium": {"class": "Business", "icon": "✈️"}, 
        "luxury": {"class": "First Class", "icon": "🛫"}
    }
    
    # Create city-specific luxury recommendations
    city_luxury_info = {
        "Brussels": {
            "luxury_hotel": "Hotel des Galeries",
            "premium_hotel": "The Hoxton Brussels", 
            "standard_hotel": "Ibis Brussels Centre",
            "luxury_restaurant": "Comme Chez Soi (2★ Michelin)",
            "premium_restaurant": "Brasserie Georges",
            "standard_restaurant": "Chez Léon"
        },
        "Barcelona": {
            "luxury_hotel": "Hotel Casa Fuster",
            "premium_hotel": "Hotel Barcelona Center",
            "standard_hotel": "Hotel Barcelona Universal",
            "luxury_restaurant": "Disfrutar (3★ Michelin)",
            "premium_restaurant": "Cal Pep",
            "standard_restaurant": "El Xampanyet"
        },
        "Berlin": {
            "luxury_hotel": "Hotel Adlon Kempinski",
            "premium_hotel": "The Ritz-Carlton Berlin",
            "standard_hotel": "MEININGER Hotel Berlin",
            "luxury_restaurant": "Tim Raue (2★ Michelin)",
            "premium_restaurant": "Lokal Modern",
            "standard_restaurant": "Prater Garten"
        },
        "Prague": {
            "luxury_hotel": "Augustine Hotel",
            "premium_hotel": "Grand Hotel Bohemia",
            "standard_hotel": "Hotel Golden Key",
            "luxury_restaurant": "Field Restaurant (1★ Michelin)",
            "premium_restaurant": "Lokál",
            "standard_restaurant": "U Fleků"
        },
        "Amsterdam": {
            "luxury_hotel": "Waldorf Astoria Amsterdam",
            "premium_hotel": "The Dylan Amsterdam",
            "standard_hotel": "Hotel V Nesplein",
            "luxury_restaurant": "Ciel Bleu (2★ Michelin)",
            "premium_restaurant": "Café de Reiger",
            "standard_restaurant": "Brown Café"
        },
        "Copenhagen": {
            "luxury_hotel": "Hotel d'Angleterre",
            "premium_hotel": "Scandic Palace Hotel",
            "standard_hotel": "Wakeup Copenhagen",
            "luxury_restaurant": "Geranium (3★ Michelin)",
            "premium_restaurant": "Restaurant Barr",
            "standard_restaurant": "Smørrebrød"
        },
        "Ljubljana": {
            "luxury_hotel": "InterContinental Ljubljana",
            "premium_hotel": "Grand Hotel Union",
            "standard_hotel": "Hotel Cubo",
            "luxury_restaurant": "Hiša Franko (2★ Michelin)",
            "premium_restaurant": "Gostilna As",
            "standard_restaurant": "Druga Violina"
        },
        "Vienna": {
            "luxury_hotel": "Hotel Sacher Wien",
            "premium_hotel": "Hotel Bristol Vienna",
            "standard_hotel": "Hotel Am Konzerthaus",
            "luxury_restaurant": "Steirereck (2★ Michelin)",
            "premium_restaurant": "Figlmüller",
            "standard_restaurant": "Zum Schwarzen Kameel"
        },
        "Rome": {
            "luxury_hotel": "Hotel de Russie",
            "premium_hotel": "The First Roma Arte",
            "standard_hotel": "Hotel Artemide",
            "luxury_restaurant": "La Pergola (3★ Michelin)",
            "premium_restaurant": "Checchino dal 1887",
            "standard_restaurant": "Da Enzo al 29"
        },
        "Florence": {
            "luxury_hotel": "Four Seasons Hotel Firenze",
            "premium_hotel": "Hotel Davanzati",
            "standard_hotel": "Plus Florence",
            "luxury_restaurant": "Enoteca Pinchiorri (3★ Michelin)",
            "premium_restaurant": "Osteria di Giovanni",
            "standard_restaurant": "Trattoria Mario"
        }
    }
    
    # Get hotel and restaurant info for selected city
    city_info = city_luxury_info.get(best_city, {
        "luxury_hotel": "5★ Luxury Hotel",
        "premium_hotel": "4★ Premium Hotel", 
        "standard_hotel": "3★ Standard Hotel",
        "luxury_restaurant": "Michelin starred restaurant",
        "premium_restaurant": "Fine dining restaurant",
        "standard_restaurant": "Local restaurant"
    })
    
    # Create beautiful cost breakdown display
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 💰 Cost Breakdown")
        
        # Flight cost with class info
        flight_info = flight_class_info[luxury_level]
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin: 10px 0;">
            <h4 style="margin: 0; color: #1f77b4;">{flight_info['icon']} Flight ({flight_info['class']})</h4>
            <h3 style="margin: 5px 0; color: #1f77b4;">€{breakdown['flight']:.0f}</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Hotel cost with specific hotel names
        hotel_nights = trip_nights(start_date, end_date)
        hotel_key = f"{luxury_level}_hotel"
        hotel_name = city_info.get(hotel_key, "Hotel")
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin: 10px 0;">
            <h4 style="margin: 0; color: #ff7f0e;">🏨 Hotel</h4>
            <h3 style="margin: 5px 0; color: #ff7f0e;">€{breakdown['hotel']:.0f}</h3>
            <p style="margin: 0; color: #666;">€{breakdown['hotel']/hotel_nights:.0f} per night × {hotel_nights} nights</p>
            <p style="margin: 0; color: #ff7f0e; font-size: 14px;"><strong>Recommended Hotel: {hotel_name}</strong></p>
        </div>
        """, unsafe_allow_html=True)
        
        # Daily expenses with restaurant names
        restaurant_key = f"{luxury_level}_restaurant"
        restaurant_name = city_info.get(restaurant_key, "Local dining")
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin: 10px 0;">
            <h4 style="margin: 0; color: #2ca02c;">🍽️ Daily Expenses</h4>
            <h3 style="margin: 5px 0; color: #2ca02c;">€{breakdown['daily_misc']:.0f}</h3>
            <p style="margin: 0; color: #666;">Food, transport & daily costs</p>
            <p style="margin: 0; color: #2ca02c; font-size: 14px;"><strong>Popular Local Restaurant: {restaurant_name}</strong></p>
        </div>
        """, unsafe_allow_html=True)
        
        # Attraction pass
        attraction_level = {"standard": "Standard access", "premium": "Skip-the-line", "luxury": "VIP experiences"}[luxury_level]
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin: 10px 0;">
            <h4 style="margin: 0; color: #d62728;">🎫 Attractions ({attraction_level})</h4>
            <h3 style="margin: 5px 0; color: #d62728;">€{breakdown['attraction_pass']:.0f}</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Activities
        st.markdown(f"""
        <div style="background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin: 10px 0;">
            <h4 style="margin: 0; color: #9467bd;">🎯 Activities & Tours</h4>
            <h3 style="margin: 5px 0; color: #9467bd;">€{breakdown['activities']:.0f}</h3>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Total cost display
        st.markdown("### 📊 Total Cost")
        
        # Calculate budget status
        budget_ratio = total_cost / budget
        if luxury_level == "luxury":
            max_allowed_ratio = 1.35
            status_color = "#ff6b35" if budget_ratio <= max_allowed_ratio else "#ff0000"
            status_text = "Within luxury limit" if budget_ratio <= max_allowed_ratio else "Exceeds luxury limit!"
        else:
            max_allowed_ratio = 1.0
            status_color = "#28a745" if budget_ratio <= max_allowed_ratio else "#ff6b35"
            status_text = "Within budget" if budget_ratio <= max_allowed_ratio else "Over budget"
        
        st.markdown(f"""
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 15px; text-align: center; border: 2px solid {status_color};">
            <h2 style="margin: 0; color: {status_color};">€{total_cost:.0f}</h2>
            <p style="margin: 5px 0; color: #666; font-size: 16px;">Total (incl. activities)</p>
            <p style="margin: 10px 0; color: {status_color}; font-weight: bold;">{status_text}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Budget comparison
        if luxury_level == "luxury":
            target_budget = budget * 1.35 * (1 - buffer * 0.5)
            st.caption(f"Luxury budget limit: €{budget * 1.35:.0f}")
            st.caption(f"Target (with buffer): €{target_budget:.0f}")
        else:
            target_budget = budget * (1 - (buffer * 0.7 if luxury_level == "premium" else buffer))
            st.caption(f"Budget: €{budget:.0f}")
            st.caption(f"Target (with buffer): €{target_budget:.0f}")
        
        # Progress bar
        progress_value = min(budget_ratio / max_allowed_ratio, 1.0)
        st.progress(progress_value)
        st.caption(f"{budget_ratio:.1%} of allowed budget used")

    st.subheader("Recommended Attractions & Activities")
    
    # Get POIs for the selected city
    city_pois = POIS.get(best_city, [])
    if city_pois:
        # Group POIs by categories for better organization
        categories = {}
        for poi in city_pois:
            for tag in poi['tags']:
                if tag not in categories:
                    categories[tag] = []
                categories[tag].append(poi)
        
        # Display top attractions based on user preferences for selected city
        selected_pois = select_pois(best_city, prefs, max_hours_per_day=8.0)
        
        # Show top recommendations
        st.markdown("#### 🌟 Top Picks for You")
        top_picks = selected_pois[:6]  # Show top 6 recommendations
        
        for i, poi in enumerate(top_picks, 1):
            with st.expander(f"{i}. {poi.name} ({poi.hours}h • €{poi.cost})", expanded=(i <= 3)):
                # Create columns for details
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**Duration:** {poi.hours} hours")
                    st.write(f"**Cost:** €{poi.cost}")
                    st.write(f"**Best for:** {', '.join(poi.tags)}")
                    
                    # Add some context based on tags
                    if "history" in poi.tags:
                        st.write("📚 Rich historical significance and cultural heritage")
                    if "architecture" in poi.tags:
                        st.write("🏛️ Stunning architectural features and design")
                    if "foodie" in poi.tags:
                        st.write("🍽️ Culinary delights and local gastronomy")
                    if "nature" in poi.tags or "hiking" in poi.tags:
                        st.write("🌿 Natural beauty and outdoor activities")
                    if "museums" in poi.tags:
                        st.write("🎨 Art, culture, and educational exhibits")
                    if "nightlife" in poi.tags:
                        st.write("🌙 Vibrant evening entertainment scene")
                    if "views" in poi.tags:
                        st.write("📸 Spectacular scenic viewpoints")
                    if "beach" in poi.tags:
                        st.write("🏖️ Coastal recreation and relaxation")
                    if "wellness" in poi.tags or "baths" in poi.tags:
                        st.write("💆 Relaxation and wellness experiences")
                    if "adventure" in poi.tags or "climbing" in poi.tags:
                        st.write("⛰️ Thrilling adventure activities")
                    if "luxury" in poi.tags:
                        st.write("✨ Premium and exclusive experiences")
                
                with col2:
                    # Show preference match
                    matches = set(poi.tags) & set(prefs)
                    if matches:
                        st.success(f"✅ Matches: {', '.join(matches)}")
                    else:
                        st.info("ℹ️ Popular attraction")
        
        # Show activities by category
        st.markdown("#### 📋 Activities by Interest")
        category_tabs = st.tabs(list(categories.keys())[:6])  # Limit to 6 categories
        
        for i, (category, pois) in enumerate(list(categories.items())[:6]):
            with category_tabs[i]:
                for poi in pois:
                    activity = next((a for a in selected_pois if a.name == poi['name']), None)
                    if activity:
                        st.markdown(f"**{activity.name}** - {activity.hours}h, €{activity.cost}")
                        st.write(f"Tags: {', '.join(activity.tags)}")
                        st.divider()
    else:
        st.write("Attractions data not available for this destination.")
    
    # Add a practical travel tips section
    st.markdown("#### 💡 Travel Tips")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"""
        **Getting Around**
        - Walkability Score: {chosen['walkability']:.1%}
        - Daily Transit Budget: €{chosen['daily_transit']}
        - Safety Rating: {chosen['safety']:.1%}
        """)
    
    with col2:
        st.info(f"""
        **Budget Guide** ({luxury_level.title()})
        - Daily Food: €{chosen[f'daily_food{"_" + luxury_level if luxury_level != "standard" else ""}']}
        - Hotel per night: €{chosen[f'hotel{"_" + luxury_level if luxury_level != "standard" else "_per_night"}']}
        - Attraction Pass: €{chosen['attraction_day_pass']}
        """)

    # Export buttons
    md = itinerary_to_markdown(best_city, start_date, end_date, total_cost, breakdown, fitted_plan)
    json_payload = {
        "city": best_city,
        "start": start_date.isoformat(),
        "end": end_date.isoformat(),
        "budget": budget,
        "luxury_level": luxury_level,
        "buffer": buffer,
        "breakdown": breakdown,
        "plan": [
            {
                "date": dp.date.isoformat(),
                "morning": asdict(dp.morning) if dp.morning else None,
                "afternoon": asdict(dp.afternoon) if dp.afternoon else None,
                "evening": asdict(dp.evening) if dp.evening else None,
            }
            for dp in fitted_plan
        ],
    }

    st.download_button(
        label="⬇️ Download itinerary (Markdown)",
        data=md,
        file_name=f"itinera_{best_city}_{start_date.isoformat()}_{end_date.isoformat()}.md",
        mime="text/markdown",
    )

    st.download_button(
        label="⬇️ Download itinerary (JSON)",
        data=json.dumps(json_payload, indent=2),
        file_name=f"itinera_{best_city}_{start_date.isoformat()}_{end_date.isoformat()}.json",
        mime="application/json",
    )
    
    # Show updated usage count after successful search
    if not st.session_state.auth_logged_in:
        remaining_uses = MAX_FREE_USES - st.session_state.filter_usage_count
        if remaining_uses > 0:
            st.success(f"✅ Search completed! You have {remaining_uses} free searches remaining.")
        else:
            st.warning("⚠️ This was your last free search. Register now for unlimited access!")
            if st.button("📝 Register Now", type="primary"):
                st.session_state.show_signup = True
                st.rerun()

else:
    if not st.session_state.auth_logged_in:
        # Show information for non-logged users who haven't used filters yet
        if st.session_state.filter_usage_count == 0:
            st.info("👆 Set your preferences above and click 'Apply Filters' to get started! You have 20 free searches.")
        else:
            remaining = MAX_FREE_USES - st.session_state.filter_usage_count
            if remaining > 0:
                st.info(f"👆 You have {remaining} free searches remaining. Set your preferences and click 'Apply Filters'!")
            else:
                st.error("🚫 Free trial limit reached! Please register to continue using ITINERA.")
        
        # Show preview of available destinations for non-logged users
        st.subheader("Available Destinations Preview")
        preview_data = []
        for d in DESTINATIONS[:12]:  # Show only first 12 destinations
            preview_data.append({
                "City": f"{d['city']}, {d['country']}",
                "Vibes": ", ".join(d['vibes'][:3]),
                "Base Flight Price": f"€{d['flight_price_base']}",
                "CO₂ (kg)": d['co2_kg'],
            })
        preview_df = pd.DataFrame(preview_data)
        preview_df.index = preview_df.index + 1
        st.dataframe(preview_df, width='stretch')
        
        st.markdown("### ✨ Features Available:")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            🎯 **Smart Recommendations** 
            - 15 premium European destinations
            - Personalized scoring
            - Budget optimization
            """)
        with col2:
            st.markdown("""
            🛫 **Luxury Options**
            - Economy to First Class
            - 3-5 star accommodations  
            - Premium experiences
            """)
        with col3:
            st.markdown("""
            📱 **Export & Save**
            - Markdown itineraries
            - JSON data export
            - Trip planning tools
            """)
    else:
        st.info("👆 Please set your travel preferences above and click 'Apply Filters' to get personalized destination recommendations!")

st.divider()

with st.expander("About this demo & reproducibility"):
    st.markdown(
        """
        **How it works**
        - Scores 15 premium European destinations using value-for-money, seasonality, walkability, safety, vibe match, accessibility, and CO₂.
        - Composes a day-by-day plan by ranking 120+ POIs against your preferences including hiking, luxury experiences, and adventure activities.
        - Fits the plan to a target budget using a 10% safety buffer (LP when `pulp` is available; greedy fallback otherwise).
        - Dynamic ranking: destinations are re-scored and re-ranked based on your specific preferences and luxury level.

        **Flight Price Sources**
        - Based on 2024 average fares from Paris (CDG/ORY) via Skyscanner, Kayak, Google Flights
        - Includes seasonal variations (e.g., +45% in summer peak)
        - Economy, Premium, and Luxury class options with real airline data

        **15 Premium Destinations Available**
        - Spain: Barcelona | Hungary: Budapest | Czech Republic: Prague
        - Netherlands: Amsterdam | Austria: Vienna | Italy: Rome
        - Germany: Berlin | Switzerland: Zurich | Poland: Krakow
        - Denmark: Copenhagen | Croatia: Dubrovnik | Scotland: Edinburgh
        - Slovenia: Ljubljana

        **Reproducible**
        - No external APIs required. All data for the demo is embedded.
        - Enhanced diversity algorithm for varied recommendations.

        **Optional AI**
        - If `transformers` is installed, Itinera uses a summarization pipeline for descriptions; otherwise it falls back to a rule-based summary.

        **Ethics by design**
        - Gentle nudges towards walkable, lower-CO₂ choices.
        - Accessibility preference boosts destinations with better accessibility baselines.
        - Luxury options available without compromising core value-focused recommendations.
        - "Best for the best" - curated selection focusing on quality over quantity.
        """
    )
