# Real-time Flight Price Integration for ITINERA
# This module handles fetching real-time flight prices from various APIs

import os
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import json

# Load environment configuration
try:
    from env_config import get_env_var
except ImportError:
    def get_env_var(key: str, default: Optional[str] = None) -> Optional[str]:
        return os.getenv(key, default)

class FlightPriceAPI:
    """
    Flight price API handler with multiple provider support and fallback mechanisms
    """
    
    def __init__(self):
        # API Configuration
        self.amadeus_api_key = get_env_var('AMADEUS_API_KEY')
        self.amadeus_api_secret = get_env_var('AMADEUS_API_SECRET')
        cache_duration_str = get_env_var('PRICE_CACHE_DURATION', '3600')
        self.cache_duration = int(cache_duration_str) if cache_duration_str else 3600  # 1 hour cache
        self.price_cache = {}
        
        # Initialize Amadeus token
        self.amadeus_token = None
        self.token_expires = None
        
    def get_amadeus_token(self) -> Optional[str]:
        """Get or refresh Amadeus access token"""
        if self.amadeus_token and self.token_expires and datetime.now() < self.token_expires:
            return self.amadeus_token
            
        if not self.amadeus_api_key or not self.amadeus_api_secret:
            return None
            
        url = "https://test.api.amadeus.com/v1/security/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.amadeus_api_key,
            "client_secret": self.amadeus_api_secret
        }
        
        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            if response.status_code == 200:
                token_data = response.json()
                self.amadeus_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 1799)
                self.token_expires = datetime.now() + timedelta(seconds=expires_in - 60)
                return self.amadeus_token
        except Exception as e:
            print(f"Error getting Amadeus token: {e}")
            
        return None
    
    def search_flights_amadeus(self, origin: str, destination: str, departure_date: str, 
                              return_date: Optional[str] = None, adults: int = 1,
                              travel_class: str = "ECONOMY") -> Optional[Dict]:
        """
        Search flights using Amadeus API
        
        Args:
            origin: IATA airport code (e.g., 'CDG' for Paris)
            destination: IATA airport code (e.g., 'BCN' for Barcelona)
            departure_date: Date in YYYY-MM-DD format
            return_date: Optional return date for round-trip
            adults: Number of adult passengers
            travel_class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, or FIRST
        """
        token = self.get_amadeus_token()
        if not token:
            return None
            
        url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": adults,
            "travelClass": travel_class,
            "max": 5  # Limit results
        }
        
        if return_date:
            params["returnDate"] = return_date
            
        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error searching flights: {e}")
            
        return None
    
    def get_flight_price(self, city: str, country: str, departure_date: str, 
                        luxury_level: str = "standard") -> Dict[str, float]:
        """
        Get flight prices for a destination with caching
        
        Args:
            city: Destination city
            country: Destination country
            departure_date: Departure date string
            luxury_level: standard, premium, or luxury
        
        Returns:
            Dictionary with flight prices for different classes
        """
        # Create cache key
        cache_key = f"{city}_{country}_{departure_date}_{luxury_level}"
        
        # Check cache first
        if cache_key in self.price_cache:
            cached_data = self.price_cache[cache_key]
            if time.time() - cached_data['timestamp'] < self.cache_duration:
                return cached_data['prices']
        
        # Airport mapping for major European cities
        airport_codes = {
            "Barcelona": "BCN",
            "Budapest": "BUD", 
            "Prague": "PRG",
            "Amsterdam": "AMS",
            "Vienna": "VIE",
            "Rome": "FCO",
            "Berlin": "BER",
            "Zurich": "ZUR",
            "Krakow": "KRK",
            "Copenhagen": "CPH",
            "Dubrovnik": "DBV",
            "Edinburgh": "EDI",
            "Ljubljana": "LJU"
        }
        
        destination_code = airport_codes.get(city)
        if not destination_code:
            return self._get_fallback_prices(city, luxury_level)
        
        # Search flights from Paris (CDG) - main hub for the app
        origin = "CDG"
        
        # Map luxury levels to travel classes
        class_mapping = {
            "standard": "ECONOMY",
            "premium": "PREMIUM_ECONOMY", 
            "luxury": "BUSINESS"
        }
        
        travel_class = class_mapping.get(luxury_level, "ECONOMY")
        
        # Try to get real-time prices
        flight_data = self.search_flights_amadeus(
            origin=origin,
            destination=destination_code,
            departure_date=departure_date,
            travel_class=travel_class
        )
        
        if flight_data and 'data' in flight_data and flight_data['data']:
            prices = self._parse_amadeus_response(flight_data, luxury_level, city)
            
            # Cache the results
            self.price_cache[cache_key] = {
                'prices': prices,
                'timestamp': time.time()
            }
            
            return prices
        
        # Fallback to static prices with real-time adjustment
        return self._get_fallback_prices(city, luxury_level)
    
    def _parse_amadeus_response(self, flight_data: Dict, luxury_level: str, destination_city: str = "") -> Dict[str, Any]:
        """Parse Amadeus API response and extract price information"""
        try:
            offers = flight_data.get('data', [])
            if not offers:
                return {}
                
            # Get the cheapest offer with airline info
            min_price = float('inf')
            best_offer = None
            for offer in offers:
                price = float(offer.get('price', {}).get('total', 0))
                if price < min_price:
                    min_price = price
                    best_offer = offer
                    
            if min_price == float('inf') or not best_offer:
                return {}
            
            # Extract airline information
            airline_code = "Unknown"
            aircraft_code = "Unknown"
            try:
                segments = best_offer.get('itineraries', [{}])[0].get('segments', [])
                if segments:
                    airline_code = segments[0].get('carrierCode', 'Unknown')
                    aircraft_code = segments[0].get('aircraft', {}).get('code', 'Unknown')
            except (IndexError, KeyError):
                pass
            
            # Generate prices for all classes based on the base price
            base_price = min_price
            
            return {
                "flight_price_base": round(base_price, 2),
                "flight_price_premium": round(base_price * 2.8, 2),
                "flight_price_luxury": round(base_price * 4.5, 2),
                "airline_code": airline_code,
                "aircraft_code": aircraft_code,
                "data_source": "Amadeus Real-time API",
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "route_info": f"Paris CDG → {destination_city}"
            }
            
        except Exception as e:
            print(f"Error parsing Amadeus response: {e}")
            return {}
    
    def _get_fallback_prices(self, city: str, luxury_level: str) -> Dict[str, Any]:
        """
        Fallback to enhanced static prices with seasonal adjustments
        and market-based fluctuations
        """
        # Enhanced static prices with real-world adjustments
        base_prices = {
            "Barcelona": {"base": 110, "premium": 340, "luxury": 480},
            "Budapest": {"base": 140, "premium": 380, "luxury": 650},
            "Prague": {"base": 120, "premium": 360, "luxury": 590},
            "Amsterdam": {"base": 95, "premium": 310, "luxury": 520},
            "Vienna": {"base": 125, "premium": 375, "luxury": 630},
            "Rome": {"base": 115, "premium": 350, "luxury": 590},
            "Berlin": {"base": 100, "premium": 320, "luxury": 450},
            "Zurich": {"base": 155, "premium": 445, "luxury": 780},
            "Krakow": {"base": 150, "premium": 390, "luxury": 660},
            "Copenhagen": {"base": 135, "premium": 405, "luxury": 685},
            "Dubrovnik": {"base": 165, "premium": 440, "luxury": 750},
            "Edinburgh": {"base": 105, "premium": 325, "luxury": 550},
            "Ljubljana": {"base": 185, "premium": 485, "luxury": 825}
        }
        
        city_prices = base_prices.get(city, {"base": 150, "premium": 400, "luxury": 650})
        
        # Add some realistic price fluctuation (±15%)
        import random
        fluctuation = random.uniform(0.85, 1.15)
        
        # Select realistic airline and aircraft
        airline_info = self._get_airline_info(city)
        
        return {
            "flight_price_base": round(city_prices["base"] * fluctuation, 2),
            "flight_price_premium": round(city_prices["premium"] * fluctuation, 2),
            "flight_price_luxury": round(city_prices["luxury"] * fluctuation, 2),
            "airline_code": airline_info["code"],
            "airline_name": airline_info["name"],
            "aircraft_code": airline_info["aircraft"],
            "data_source": "Enhanced Simulation (Amadeus API credentials required for real-time data)",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "route_info": f"Paris CDG → {city}"
        }
    
    def _get_airline_info(self, destination_city: str) -> Dict[str, str]:
        """Get realistic airline information for Paris to European destinations"""
        # Airlines that actually operate from Paris CDG to European cities
        paris_to_europe_airlines = {
            # Major European carriers with Paris routes
            "Barcelona": [
                {"code": "AF", "name": "Air France", "aircraft": "A320"},
                {"code": "VY", "name": "Vueling", "aircraft": "A320"},
                {"code": "IB", "name": "Iberia", "aircraft": "A321"}
            ],
            "Budapest": [
                {"code": "AF", "name": "Air France", "aircraft": "A319"},
                {"code": "W6", "name": "Wizz Air", "aircraft": "A320"},
                {"code": "LO", "name": "LOT Polish Airlines", "aircraft": "E195"}
            ],
            "Prague": [
                {"code": "AF", "name": "Air France", "aircraft": "A318"},
                {"code": "OK", "name": "Czech Airlines", "aircraft": "A319"},
                {"code": "U2", "name": "easyJet", "aircraft": "A320"}
            ],
            "Amsterdam": [
                {"code": "AF", "name": "Air France", "aircraft": "A321"},
                {"code": "KL", "name": "KLM", "aircraft": "B737"},
                {"code": "HV", "name": "Transavia", "aircraft": "B737"}
            ],
            "Vienna": [
                {"code": "AF", "name": "Air France", "aircraft": "A320"},
                {"code": "OS", "name": "Austrian Airlines", "aircraft": "A320"},
                {"code": "U2", "name": "easyJet", "aircraft": "A319"}
            ],
            "Rome": [
                {"code": "AF", "name": "Air France", "aircraft": "A321"},
                {"code": "AZ", "name": "ITA Airways", "aircraft": "A320"},
                {"code": "U2", "name": "easyJet", "aircraft": "A320"}
            ],
            "Berlin": [
                {"code": "AF", "name": "Air France", "aircraft": "A319"},
                {"code": "LH", "name": "Lufthansa", "aircraft": "A320"},
                {"code": "U2", "name": "easyJet", "aircraft": "A319"}
            ],
            "Zurich": [
                {"code": "AF", "name": "Air France", "aircraft": "A320"},
                {"code": "LX", "name": "Swiss International", "aircraft": "A220"},
                {"code": "LH", "name": "Lufthansa", "aircraft": "A320"}
            ],
            "Krakow": [
                {"code": "AF", "name": "Air France", "aircraft": "E190"},
                {"code": "LO", "name": "LOT Polish Airlines", "aircraft": "E195"},
                {"code": "W6", "name": "Wizz Air", "aircraft": "A320"}
            ],
            "Copenhagen": [
                {"code": "AF", "name": "Air France", "aircraft": "A319"},
                {"code": "SK", "name": "SAS", "aircraft": "A320"},
                {"code": "U2", "name": "easyJet", "aircraft": "A320"}
            ],
            "Dubrovnik": [
                {"code": "AF", "name": "Air France", "aircraft": "A319"},
                {"code": "OU", "name": "Croatia Airlines", "aircraft": "A319"},
                {"code": "U2", "name": "easyJet", "aircraft": "A320"}
            ],
            "Edinburgh": [
                {"code": "AF", "name": "Air France", "aircraft": "A318"},
                {"code": "BA", "name": "British Airways", "aircraft": "A319"},
                {"code": "U2", "name": "easyJet", "aircraft": "A319"}
            ],
            "Ljubljana": [
                {"code": "AF", "name": "Air France", "aircraft": "E190"},
                {"code": "JP", "name": "Adria Airways", "aircraft": "CRJ9"},
                {"code": "LH", "name": "Lufthansa", "aircraft": "CRJ9"}
            ]
        }
        
        import random
        # Get specific airlines for the destination, or use default European carriers
        city_airlines = paris_to_europe_airlines.get(destination_city, [
            {"code": "AF", "name": "Air France", "aircraft": "A320"},
            {"code": "LH", "name": "Lufthansa", "aircraft": "A320"},
            {"code": "U2", "name": "easyJet", "aircraft": "A319"}
        ])
        
        return random.choice(city_airlines)

# Global instance
flight_api = FlightPriceAPI()

def get_real_time_flight_price(city: str, country: str, departure_date: str, 
                              luxury_level: str = "standard") -> Dict[str, Any]:
    """
    Public function to get real-time flight prices
    
    This function can be called from the main app to get current flight prices
    """
    return flight_api.get_flight_price(city, country, departure_date, luxury_level)