
# ToneGuard AI
### AI-Powered Tone Analysis, Grammar Correction & Professional Communication

ToneGuard AI is an intelligent text communication assistant designed to identify potentially harsh or misunderstood language, correct basic grammatical errors, and rewrite messages in a polite and professional tone.

## Project Overview

Written communication can sometimes create misunderstandings because the intended tone may not match how the reader interprets a message.

ToneGuard AI helps users improve their written communication by analysing text, identifying potentially harsh expressions, correcting grammar, and suggesting professional alternatives.

## Key Features

- **Tone Analysis:** Identifies potentially harsh, neutral, friendly, or professional language.
- **Grammar Correction:** Corrects selected grammatical errors and basic sentence issues.
- **Professional Rewriting:** Rewrites messages into a more polite and professional style.
- **AI Integration:** Uses the Google Gemini API when available.
- **Fallback Processing:** Provides local rule-based processing when the AI service is unavailable.
- **Interactive Dashboard:** Simple web interface for entering messages and viewing results.

## Technologies Used

| Component | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| AI Integration | Google Gemini API |
| Data Validation | Pydantic |
| API Testing | Swagger UI |
| Environment Management | Python Virtual Environment |

## System Architecture

1. User enters text through the web dashboard.
2. The frontend sends a request to the FastAPI backend.
3. The backend processes the input using the relevant feature.
4. Gemini AI is attempted for tone analysis and professional rewriting.
5. Local rule-based processing is used if Gemini is unavailable.
6. The processed result is returned to the frontend and displayed to the user.

## Project Structure

```text
AITone-Misinterpretation/
│
├── android-app/
│   └── index.html
│
├── backend/
│   └── main.py
│
├── datasets/
├── models/
├── .gitignore
└── README.md
```

## Installation and Execution

### 1. Clone the Repository

```bash
git clone https://github.com/aishwaryakumaran14/AITone-Misinterpretation.git
cd AITone-Misinterpretation
```

### 2. Create and Activate a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install fastapi uvicorn python-dotenv google-genai
```

### 4. Configure the Gemini API Key

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_api_key_here
```

Replace the placeholder with your own Gemini API key. Never upload your `.env` file to GitHub.

### 5. Start the Backend

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

Backend API:
http://127.0.0.1:8000

Swagger documentation:
http://127.0.0.1:8000/docs

### 6. Start the Frontend

Open another terminal and run:

```bash
python3 -m http.server 5500
```

Open the dashboard:

http://127.0.0.1:5500/android-app/

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Backend status |
| GET | `/health` | Health check |
| POST | `/analyze` | Analyse message tone |
| POST | `/grammar` | Correct grammar |
| POST | `/rewrite` | Rewrite professionally |

## Expected Applications

- Professional email communication
- Academic and workplace messaging
- Improving clarity and politeness
- Reducing misunderstandings in written communication

## Future Enhancements

- Advanced grammar correction using NLP.
- Support for multiple languages.
- Context-aware emotion and sentiment detection.
- User authentication and communication history.
- Downloadable analysis reports.

## Project Information

**Project Name:** ToneGuard AI  
**Project Domain:** Artificial Intelligence and Natural Language Processing  
**Repository:** [AITone-Misinterpretation](https://github.com/aishwaryakumaran14/AITone-Misinterpretation)

---

*Developed as an academic project to promote clear, respectful, and effective digital communication.*
