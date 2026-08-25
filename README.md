<div align="center">
  
  # 🛒 Mehengaai Mitra
  
  ### *Your Smart Grocery Budget Companion*
  
  [![Streamlit App](https://img.shields.io/badge/🚀-Live_Demo-00C853?style=for-the-badge&logo=streamlit&logoColor=white)](https://capstone-project-mirai.streamlit.app)
  [![GitHub](https://img.shields.io/badge/📂-GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/Tanishka-17/capstone_project_mirai)
  [![Python](https://img.shields.io/badge/🐍-Python_3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
  [![Gemini](https://img.shields.io/badge/🤖-Gemini_AI-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
  [![License](https://img.shields.io/badge/📄-MIT-FFD700?style=for-the-badge)](LICENSE)
  
  > *"Know your basket before it gets expensive."*
  
  ---
  
</div>

## 🌟 About The Project

**Mehengaai Mitra** (Hindi for *"Expensive Friend"*) is an intelligent grocery budget companion that helps Indian households track prices, plan monthly shopping, and make informed purchasing decisions.

### 🎯 Problem Statement
> **Hyper-Local Inflation Tracker** — Users log the price of basic grocery items (milk, eggs, rice) over a month. The app plots inflation trends and uses AI to predict the next month's budget requirement.

---

## ✨ Features

<div align="center">

| 💰 Budget Management | 🛒 Smart Lists | 🏷️ Brand Compare |
|:---:|:---:|:---:|
| Set & track monthly budget | Generate optimized lists | Compare online/local stores |

| ❤️ Health Planning | 📊 ML Forecast | 🌐 Real-Time Search |
|:---:|:---:|:---:|
| Diabetes, BP, kidney-aware | Predict next month's costs | Google-grounded prices |

| 🍳 Recipe-Based | 📈 Interactive Charts | 🎨 Gold-Green Theme |
|:---:|:---:|:---:|
| Cook anything, get a list | Altair visualizations | Custom premium design |

</div>

---

## 📸 Screenshots

<div align="center">

### 🏠 Home Page
![Home Page](home_page.png)

---

### 💬 Chat Mode - Shopping List
![Chat Mode 1](chat1.png)

---

### 💬 Chat Mode - AI Recommendations
![Chat Mode 2](chat2.png)

---

### 📊 Dashboard & Analytics
![Dashboard](dashboard.png)

</div>

---

## 🏗️ Architecture

```mermaid
graph LR
    A[Streamlit Frontend] --> B[Session State]
    A --> C[Pandas Data Engine]
    C --> D[scikit-learn ML]
    C --> E[Altair Charts]
    B --> F[Google Gemini API]
    F --> G[AI Recommendations]
    D --> H[Price Forecast]
    E --> I[Interactive Dashboards]
