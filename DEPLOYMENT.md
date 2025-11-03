# 🚀 Quick Cloud Deployment Guide

## Option 1: Streamlit Cloud (Recommended - FREE)

### Step 1: Upload to GitHub
1. Create a new GitHub repository at https://github.com/new
2. Name it: `itinera-travel-planner`
3. Make it **Public**
4. Upload all files from `ITINERA_Cloud` folder

### Step 2: Deploy to Streamlit Cloud
1. Go to https://share.streamlit.io
2. Sign in with your GitHub account
3. Click **"New app"**
4. Select your repository: `itinera-travel-planner`
5. Main file path: `app.py`
6. Click **"Deploy!"**

### Step 3: Get Your URL
After 2-3 minutes, you'll get a URL like:
```
https://your-username-itinera-travel-planner-app-xxxxx.streamlit.app
```

**Share this URL with your international teammates!** 🌍

---

## Option 2: Alternative Platforms

### Railway (railway.app)
- Connect GitHub repo
- Auto-deploy
- Free tier: 500 hours/month

### Render (render.com)
- Connect GitHub repo
- Build command: `pip install -r requirements.txt`
- Start command: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`

### Heroku (heroku.com)
- Requires credit card (even for free tier)
- More complex setup

---

## 💡 Tips for International Users

1. **Language**: The app interface is in Chinese, but all destination names and core functionality work in English
2. **Currency**: All prices are in Euros (€)
3. **Destinations**: 15 European cities included
4. **Mobile Friendly**: Works on all devices

## 🆘 Need Help?
- Check `部署指南.md` for detailed Chinese instructions
- GitHub issues: Create issues in your repository
- Streamlit docs: https://docs.streamlit.io

**Happy deploying!** ✨