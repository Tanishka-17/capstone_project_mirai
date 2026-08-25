<div align="center">

<img src="https://readme-typing-svg.demolab.com/?font=Orbitron&weight=900&size=44&duration=1&pause=100000&color=000000&background=FFFFFF00&center=true&vCenter=true&width=600&height=70&lines=MEHENGAAI+MITRA&repeat=false" alt="Mehengaai Mitra" />

**Smart Grocery Budget Companion**

[![Streamlit App](https://img.shields.io/badge/status-online-00C853?style=flat-square&logo=streamlit&logoColor=white)](https://capstoneprojectmirai-lbcekpwcaxw2otq4kr7ven.streamlit.app/)
[![GitHub](https://img.shields.io/badge/source-repo-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Tanishka-17/capstone_project_mirai)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Gemini](https://img.shields.io/badge/ai-gemini-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev)
[![License](https://img.shields.io/badge/license-MIT-FFD700?style=flat-square)](LICENSE)

*"Know your basket before it gets expensive."*

**🔗 [Try the live app](https://capstoneprojectmirai-lbcekpwcaxw2otq4kr7ven.streamlit.app/)**

</div>

<br>

## About

**Mehengaai Mitra** (Hindi for *"Expensive Friend"*) is an intelligent grocery budget companion that helps Indian households track prices, plan monthly shopping, and make informed purchasing decisions.

**Problem statement — Hyper-Local Inflation Tracker:** Users log the price of basic grocery items (milk, eggs, rice) over a month. The app plots inflation trends and uses AI to predict the next month's budget requirement.

<br>

## Features

<div align="center">

| ⚙️ | | ⚙️ | | ⚙️ |
|:---:|---|:---:|---|:---:|
| **💰 Budget Management**<br>Set & track monthly budget | | **🛒 Smart Lists**<br>Generate optimized lists | | **🏷️ Brand Compare**<br>Compare online/local stores |
| **❤️ Health Planning**<br>Diabetes, BP, kidney-aware | | **📊 ML Forecast**<br>Predict next month's costs | | **🌐 Real-Time Search**<br>Google-grounded prices |
| **🍳 Recipe-Based**<br>Cook anything, get a list | | **📈 Interactive Charts**<br>Altair visualizations | | **🎨 Gold-Green Theme**<br>Custom premium design |

</div>

<br>

## Screenshots

<div align="center">

**Home Page**
![Home Page](home_page.png)

**Chat Mode — Shopping List**
![Chat Mode 1](chat1.png)

**Chat Mode — AI Recommendations**
![Chat Mode 2](chat2.png)

**Dashboard & Analytics**
![Dashboard](dashboard.png)

</div>

<br>

## Architecture

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
```

<br>

<div align="center">

⚙️ *Run it locally with* `streamlit run app.py`

</div>
