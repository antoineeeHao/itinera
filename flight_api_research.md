# Flight Price API Research

## Available Free/Low-Cost Flight APIs

### 1. Amadeus Self-Service APIs
- **Free tier**: 1,000 requests per month
- **Coverage**: Real-time flight search, pricing
- **Documentation**: https://developers.amadeus.com/
- **Best for**: Production applications

### 2. Aviationstack API
- **Free tier**: 1,000 requests per month
- **Coverage**: Flight schedules, real-time data
- **URL**: https://aviationstack.com/
- **Best for**: Flight status and schedules

### 3. Kiwi (Tequila) API
- **Free tier**: Limited requests
- **Coverage**: Flight search and booking
- **Documentation**: https://docs.kiwi.com/
- **Best for**: Budget travel

### 4. RapidAPI Flight Options
- **Skyscanner API**: Flight search
- **Tripadvisor API**: Travel data
- **Various pricing tiers available

### 5. Alternative Approach: Web Scraping
- **Google Flights**: Not officially supported
- **Kayak**: Rate-limited
- **Skyscanner**: Has rate limits

## Recommended Approach for ITINERA

For your application, I recommend using **Amadeus Self-Service API** because:
1. 1,000 free requests per month is sufficient for development
2. Real-time pricing data
3. Professional grade API
4. Good documentation
5. Supports all European destinations in your app

## Implementation Plan

1. Sign up for Amadeus Developer account
2. Get API credentials
3. Implement caching to reduce API calls
4. Add fallback to static prices if API fails
5. Update price refresh mechanism