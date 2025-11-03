#!/bin/bash

echo "🚀 ITINERA Cloud Deployment Helper"
echo "=================================="
echo ""

# 检查是否安装了git
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Please install Git first."
    echo "Download from: https://git-scm.com/downloads"
    exit 1
fi

echo "📂 Initializing Git repository..."
cd /Users/hao/Desktop/ITINERA_Cloud
git init

echo "📝 Adding files to Git..."
git add .
git commit -m "Initial commit: ITINERA Travel Planner"

echo ""
echo "🎯 Next Steps:"
echo "1. Create a new repository on GitHub:"
echo "   - Go to https://github.com/new"
echo "   - Repository name: itinera-travel-planner"
echo "   - Make it public"
echo "   - Don't add README, .gitignore, or license (we already have files)"
echo ""
echo "2. Connect your local repository to GitHub:"
echo "   Replace 'YOUR_USERNAME' with your GitHub username:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/itinera-travel-planner.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "3. Deploy to Streamlit Cloud:"
echo "   - Visit https://share.streamlit.io"
echo "   - Sign in with GitHub"
echo "   - Click 'New app'"
echo "   - Select your repository: itinera-travel-planner"
echo "   - Main file path: app.py"
echo "   - Click 'Deploy!'"
echo ""
echo "4. Share the URL with your international teammates!"
echo ""
echo "🌟 Your app will be available at:"
echo "https://YOUR_USERNAME-itinera-travel-planner-app-xxxxx.streamlit.app"
echo ""
echo "Need help? Check the '部署指南.md' file for detailed instructions."