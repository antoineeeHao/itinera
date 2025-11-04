# ITINERA - Real-time Flight Price Integration Guide

## 🚀 New Feature: Real-time Flight Prices

Your ITINERA app now supports real-time flight pricing! This means you can get current airline prices instead of static estimates.

## 📋 Setup Instructions

### Step 1: Get API Keys (Free)

#### Option A: Amadeus API (Recommended)
1. Visit: https://developers.amadeus.com/register
2. Create a free account
3. Get your API Key and Secret (1,000 free requests/month)
4. Copy the credentials

#### Option B: Alternative APIs (Optional)
- **RapidAPI**: https://rapidapi.com/ (Multiple flight APIs)
- **Aviationstack**: https://aviationstack.com/ (Flight schedules)

### Step 2: Configure Environment

1. Copy the template file:
   ```bash
   cp .env.template .env
   ```

2. Edit the `.env` file and add your API keys:
   ```env
   AMADEUS_API_KEY=your_actual_api_key_here
   AMADEUS_API_SECRET=your_actual_api_secret_here
   ```

### Step 3: Install Dependencies

```bash
pip install requests python-dotenv
```

### Step 4: Test the Integration

Run your app and look for these indicators:
- ✅ "Real-time flight prices" message = API working
- 📊 "Market-based pricing" message = Using fallback prices

## 🎯 How It Works

### Real-time Price Flow
1. **User Input**: You enter travel dates and preferences
2. **API Call**: App requests current prices from airlines
3. **Cache**: Prices are cached for 1 hour to reduce API calls
4. **Fallback**: If API fails, uses enhanced static prices
5. **Display**: Shows live prices with seasonal adjustments

### Price Sources
- **Primary**: Amadeus (Real airline data)
- **Fallback**: Enhanced static prices with realistic fluctuations
- **Cache**: 1-hour cache to optimize API usage

## 📊 Price Accuracy

### With Real-time API
- ✅ Current airline prices
- ✅ Real availability-based pricing
- ✅ Seasonal variations included
- ✅ Different class prices (Economy/Business/First)

### Without API (Fallback)
- 📈 Market-based estimates with ±15% fluctuation
- 📅 Seasonal adjustments
- 🏷️ Realistic price ranges
- 🔄 Dynamic pricing simulation

## 🛠️ Configuration Options

Edit your `.env` file to customize:

```env
# Cache settings
PRICE_CACHE_DURATION=3600        # 1 hour cache
MAX_CACHE_SIZE=1000              # Max cached prices

# Rate limiting
MAX_REQUESTS_PER_MINUTE=50       # API rate limit
RETRY_ATTEMPTS=3                 # Retry failed requests
TIMEOUT_SECONDS=15               # Request timeout
```

## 🔧 Troubleshooting

### Common Issues

**"Market-based pricing" always shows**
- Check your `.env` file exists
- Verify API keys are correct
- Check internet connection

**Prices seem inaccurate**
- Real prices vary significantly by date
- Try different travel dates
- Check if it's peak season

**API errors in console**
- Check API key limits (1,000/month for free)
- Verify API credentials
- Check Amadeus API status

### Debug Mode
Add to your `.env`:
```env
DEBUG_FLIGHT_API=true
```

This will show detailed API responses in the console.

## 📈 Benefits

### For Users
- **Real Pricing**: See actual current flight costs
- **Better Planning**: Make informed budget decisions
- **Seasonal Insights**: Understand price variations

### For Developers
- **Scalable**: Cached results reduce API calls
- **Reliable**: Fallback ensures app always works
- **Flexible**: Easy to add more price sources

## 🚀 Going Live

### Production Checklist
1. ✅ Get production API keys (higher limits)
2. ✅ Configure environment variables on your server
3. ✅ Set up monitoring for API usage
4. ✅ Test with real user scenarios
5. ✅ Monitor cache hit rates

### Deployment Notes
- Add `.env` to `.gitignore` (never commit API keys)
- Use environment variables in production
- Consider upgrading API plans for higher traffic
- Monitor API usage to avoid limits

## 💡 Future Enhancements

Possible improvements:
- **Hotel Prices**: Add real-time hotel pricing
- **Multi-airline**: Compare prices across airlines
- **Price Alerts**: Notify when prices drop
- **Historical Data**: Show price trends
- **Currency Support**: Multiple currencies

## 📞 Support

If you need help:
1. Check the troubleshooting section above
2. Review API documentation: https://developers.amadeus.com/
3. Test with the provided fallback mode first

Happy travels with your enhanced ITINERA app! ✈️🌍