
import os
import json
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai


# =====================================
# PROJECT PATH AND GEMINI CONFIGURATION
# =====================================

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

MODEL_NAME = "gemini-3.8-flash"


# =====================================
# FASTAPI APPLICATION
# =====================================

app = FastAPI(
    title="AI Tone Misinterpretation API",
    description="AI-powered grammar correction and tone analysis",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================
# REQUEST MODEL
# =====================================

class TextRequest(BaseModel):
    text: str


# =====================================
# HOME AND HEALTH
# =====================================

@app.get("/")
def home():
    dashboard_file = BASE_DIR / "android-app" / "index.html"
    return FileResponse(dashboard_file)


@app.get("/health")
def health():
    return {"status": "healthy"}


# =====================================
# LOCAL TONE ANALYSIS
# =====================================

def local_tone_analysis(text):

    lower_text = text.lower()

    harsh_words = [
        "immediately", "again", "stupid", "never",
        "always", "useless", "failed", "ridiculous",
        "must", "wrong"
    ]

    polite_words = [
        "please", "kindly", "thank you",
        "appreciate", "could you", "would you"
    ]

    detected_words = [
        word for word in harsh_words
        if re.search(r"\b" + re.escape(word) + r"\b", lower_text)
    ]

    polite_found = any(
        phrase in lower_text for phrase in polite_words
    )

    if detected_words:
        tone = "Harsh / Potentially Rude"
        suggestion = (
            "Some words may sound demanding. "
            "Consider using polite and professional wording."
        )
        confidence = 0.80

    elif polite_found:
        tone = "Professional / Friendly"
        suggestion = (
            "The message sounds polite and respectful. "
            "It is suitable for professional communication."
        )
        confidence = 0.85

    else:
        tone = "Neutral"
        suggestion = (
            "The message has a generally neutral tone. "
            "You can add polite expressions to make it warmer."
        )
        confidence = 0.75

    return {
        "original_text": text,
        "detected_tone": tone,
        "confidence": confidence,
        "detected_words": detected_words,
        "suggestion": suggestion
    }


# =====================================
# TONE ANALYSIS ENDPOINT
# =====================================

@app.post("/analyze")
def analyze_text(request: TextRequest):

    text = request.text.strip()

    if not text:
        return {
            "original_text": text,
            "detected_tone": "No text provided",
            "confidence": 0,
            "detected_words": [],
            "suggestion": "Please enter a message to analyse."
        }

    if client:
        try:
            prompt = f"""
You are an expert AI assistant for professional communication.

Analyse this message:
{text}

Identify:
1. Emotional tone.
2. Words or phrases that may sound harsh.
3. A recommendation to improve the message.

Return ONLY valid JSON:

{{
    "detected_tone": "Professional / Neutral / Harsh / Friendly / Formal",
    "confidence": 0.90,
    "detected_words": ["word1"],
    "suggestion": "Your recommendation"
}}

Confidence must be between 0 and 1.
"""

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )

            result_text = (response.text or "").strip()
            result_text = result_text.replace("```json", "")
            result_text = result_text.replace("```", "")

            result = json.loads(result_text)

            return {
                "original_text": text,
                "detected_tone": result["detected_tone"],
                "confidence": result["confidence"],
                "detected_words": result["detected_words"],
                "suggestion": result["suggestion"]
            }

        except Exception as error:
            print("Gemini tone analysis unavailable:", error)

    return local_tone_analysis(text)


# =====================================
# GRAMMAR CORRECTION
# =====================================

@app.post("/grammar")
def correct_grammar(request: TextRequest):

    text = request.text.strip()

    if not text:
        return {
            "original_text": text,
            "corrected_text": ""
        }

    corrected_text = text

    corrections = [

        # Context-based past tense
        (
            r"\b(he|she|it|i|they|we|you)\s+go(?=\s+to\b[^.!?]*\byesterday\b)",
            r"\1 went"
        ),

        # Subject and verb agreement
        (r"\bshe\s+don't\b", "she doesn't"),
        (r"\bhe\s+don't\b", "he doesn't"),
        (r"\bit\s+don't\b", "it doesn't"),

        (r"\bshe\s+dont\b", "she doesn't"),
        (r"\bhe\s+dont\b", "he doesn't"),
        (r"\bit\s+dont\b", "it doesn't"),
        (r"\bi\s+dont\b", "I don't"),
        (r"\byou\s+dont\b", "you don't"),
        (r"\bthey\s+dont\b", "they don't"),
        (r"\bwe\s+dont\b", "we don't"),

        (r"\bshe\s+have\b", "she has"),
        (r"\bhe\s+have\b", "he has"),
        (r"\bit\s+have\b", "it has"),
        (r"\bi\s+has\b", "I have"),

        (r"\bshe\s+are\b", "she is"),
        (r"\bhe\s+are\b", "he is"),
        (r"\bit\s+are\b", "it is"),
        (r"\bthey\s+is\b", "they are"),
        (r"\bwe\s+is\b", "we are"),
        (r"\byou\s+is\b", "you are"),

        (r"\bthey\s+was\b", "they were"),
        (r"\bwe\s+was\b", "we were"),
        (r"\byou\s+was\b", "you were"),

        # Doesn't / don't verb agreement
        (r"\bdoesn't\s+(likes|goes|plays|works|knows|wants)\b",
         lambda m: "doesn't " + {
             "likes": "like",
             "goes": "go",
             "plays": "play",
             "works": "work",
             "knows": "know",
             "wants": "want"
         }[m.group(1).lower()]),

        (r"\bdon't\s+(likes|goes|plays|works)\b",
         lambda m: "don't " + {
             "likes": "like",
             "goes": "go",
             "plays": "play",
             "works": "work"
         }[m.group(1).lower()]),

        # Common contractions
        (r"\bdoesnt\b", "doesn't"),
        (r"\bdont\b", "don't"),
        (r"\bdidnt\b", "didn't"),
        (r"\bcant\b", "can't"),
        (r"\bwont\b", "won't"),
        (r"\bisnt\b", "isn't"),
        (r"\barent\b", "aren't"),
        (r"\bhasnt\b", "hasn't"),
        (r"\bhavent\b", "haven't"),
        (r"\bwasnt\b", "wasn't"),
        (r"\bwerent\b", "weren't"),

        # Common sentence corrections
        (r"\bthe meeting are\b", "the meeting is"),
        (r"\bmeeting are\b", "meeting is"),
        (r"\bis postpone\b", "is postponed"),
        (r"\bare postpone\b", "are postponed"),

        # Articles
        (r"\bto office\b", "to the office"),

        # First-person pronoun
        (r"\bi am\b", "I am"),
        (r"\bi have\b", "I have"),
        (r"\bi will\b", "I will"),
        (r"\bi want\b", "I want"),
        (r"\bi need\b", "I need"),
    ]

    for wrong, right in corrections:
        corrected_text = re.sub(
            wrong,
            right,
            corrected_text,
            flags=re.IGNORECASE
        )

    # Capitalize the first character
    if corrected_text:
        corrected_text = (
            corrected_text[0].upper() + corrected_text[1:]
        )

        # Add punctuation if missing
        if corrected_text[-1] not in ".!?":
            corrected_text += "."

    return {
        "original_text": text,
        "corrected_text": corrected_text,
        "method": "Rule-Based Grammar Correction"
    }


# =====================================
# LOCAL PROFESSIONAL REWRITING
# =====================================

def local_professional_rewrite(text):

    rewritten_text = text.strip()

    replacements = [
        (
            r"\bi am tired of asking you again\b",
            "I would appreciate your response, as I have followed up previously"
        ),
        (
            r"\byou are delaying everything\b",
            "There seems to be a delay"
        ),
        (
            r"\bsend me\b",
            "Could you please send me"
        ),
        (
            r"\bsend it fast\b",
            "Please send it at your earliest convenience"
        ),
        (
            r"\bimmediately\b",
            "at your earliest convenience"
        ),
        (
            r"\bdo it now\b",
            "Could you please complete this at your earliest convenience"
        ),
        (
            r"\bgive me\b",
            "Could you please provide me with"
        ),
        (
            r"\byou must\b",
            "I kindly request that you"
        ),
        (
            r"\bthis is wrong\b",
            "This may need some correction"
        ),
        (
            r"\bi need\b",
            "I would appreciate"
        )
    ]

    for old, new in replacements:
        rewritten_text = re.sub(
            old,
            new,
            rewritten_text,
            flags=re.IGNORECASE
        )

    if rewritten_text:
        rewritten_text = (
            rewritten_text[0].upper() + rewritten_text[1:]
        )

        if rewritten_text[-1] not in ".!?":
            rewritten_text += "."

    return rewritten_text


# =====================================
# PROFESSIONAL MESSAGE REWRITING
# =====================================

@app.post("/rewrite")
def rewrite_message(request: TextRequest):

    text = request.text.strip()

    if not text:
        return {
            "original_text": text,
            "rewritten_text": "",
            "message": "Please enter a message."
        }

    if client:
        try:
            prompt = f"""
Rewrite the following message in a polite,
clear and professional tone.

Preserve the original meaning and important details.
Do not add facts or change the intention.

Original message:
{text}

Return only the rewritten message.
"""

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )

            rewritten_text = (response.text or "").strip()

            if not rewritten_text:
                raise ValueError("Gemini returned an empty response.")

            return {
                "original_text": text,
                "rewritten_text": rewritten_text,
                "method": "Gemini AI"
            }

        except Exception as error:
            print("Gemini rewrite unavailable:", error)

    rewritten_text = local_professional_rewrite(text)

    return {
        "original_text": text,
        "rewritten_text": rewritten_text,
        "method": "Local Professional Rewriting",
        "message": "Message rewritten using local language rules."
    }
