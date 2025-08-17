# 🤖 Gemini AI Chat Application

A beautiful, secure, and feature-rich web application for chatting with Google's Gemini AI models. Built with Flask and modern web technologies.

![Gemini AI Chat](https://img.shields.io/badge/AI-Gemini-blue?style=for-the-badge&logo=google)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)

## ✨ Features

- 🔐 **Secure Authentication** - User registration and login system
- 🤖 **Multiple AI Models** - Support for Gemini 1.5 Flash, 2.0 Flash, 2.5 Flash, and 2.5 Pro
- 🔍 **Smart Web Search** - Automatic internet search integration when needed
- 💬 **Real-time Chat** - Beautiful chat interface with typing effects
- 🎨 **Modern UI** - Clean, responsive design inspired by ChatGPT
- 🔒 **Secure Storage** - Encrypted password storage and secure API key management
- 🌐 **Web Search Integration** - SerpAPI integration for current information
- 📱 **Mobile Friendly** - Responsive design that works on all devices
- ⚡ **Fast Performance** - Optimized for speed and reliability

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Google Gemini API key ([Get it here](https://makersuite.google.com/app/apikey))
- SerpAPI key for web search ([Get it here](https://serpapi.com/dashboard)) - Optional

### Local Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/gemini-ai-chat.git
   cd gemini-ai-chat
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Open your browser**
   ```
   http://localhost:5000
   ```

### 🌐 Deploy to Production

#### Railway (Recommended)
1. Fork this repository
2. Connect to [Railway](https://railway.app)
3. Deploy from GitHub repo
4. Your app will be live in minutes!

#### Render
1. Connect to [Render](https://render.com)
2. Create new Web Service
3. Connect your GitHub repo
4. Deploy automatically

#### Heroku
1. Install Heroku CLI
2. ```bash
   heroku create your-app-name
   git push heroku main
   ```

## 🛠️ Configuration

### First Time Setup

1. **Register an account** on your deployed app
2. **Go to Settings** and add your API keys:
   - **Google Gemini API Key** (Required)
   - **SerpAPI Key** (Optional - for web search)
3. **Start chatting!**

### Environment Variables (Optional)

For production deployment, you can set these environment variables:

```bash
export PORT=5000
export FLASK_ENV=production
```

## 📖 How to Use

### Basic Chat
- Type your message and press Enter
- The AI will respond using your selected Gemini model
- Use Shift+Enter for new lines

### Web Search
The app automatically detects when you need current information and searches the web:
- "Search for latest tech news"
- "What's the weather today?"
- "Find recent updates about..."

### Model Selection
Choose from available Gemini models:
- **Gemini 1.5 Flash** - Fast and efficient
- **Gemini 2.0 Flash** - Enhanced capabilities
- **Gemini 2.5 Flash** - Latest fast model
- **Gemini 2.5 Pro** - Most advanced features

## 🎨 Screenshots

### Login Screen
Modern, secure authentication with registration option.

### Chat Interface
Clean, ChatGPT-inspired design with real-time typing effects.

### Settings Page
Easy API key management and configuration.

## 🔧 Technical Details

### Built With
- **Backend**: Python Flask
- **Database**: SQLite with secure password hashing
- **Frontend**: Vanilla JavaScript with modern CSS
- **AI Integration**: Google Generative AI SDK
- **Web Search**: SerpAPI integration
- **Styling**: Custom CSS with animations and responsive design

### Security Features
- Secure password hashing with salt
- Session management
- API key encryption in database
- Input sanitization
- CSRF protection ready

### Database Schema
- **Users**: username, email, password_hash, api_keys, timestamps
- **Chat Sessions**: user_id, messages, timestamps (ready for future implementation)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Google for the Gemini AI API
- SerpAPI for web search capabilities
- Flask community for the excellent framework
- OpenAI for UI/UX inspiration

## 📞 Support

If you have any questions or need help:

1. Check the [Issues](https://github.com/yourusername/gemini-ai-chat/issues) page
2. Create a new issue if needed
3. Make sure to include:
   - Your operating system
   - Python version
   - Error messages (if any)

## 🚀 What's Next?

- [ ] Chat history saving
- [ ] File upload support
- [ ] Dark/Light theme toggle
- [ ] Multi-language support
- [ ] Voice input/output
- [ ] Mobile app version

---

Made by raziel-star

⭐ **Star this repo if you find it helpful!**
