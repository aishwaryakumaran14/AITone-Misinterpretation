import os
import re
import time
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from google import genai
from google.genai import types


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("toneguard")

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
client = None
if API_KEY:
    try:
        client = genai.Client(api_key=API_KEY)
        logger.info("Gemini client initialized.")
    except Exception:
        logger.exception("Could not initialize Gemini client.")
else:
    logger.warning("GEMINI_API_KEY not found. Local fallback mode enabled.")

MAX_TEXT_LENGTH = 12000


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="ToneGuard AI API",
    description="Context-aware tone analysis, grammar correction and professional rewriting.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ============================================================
# REQUEST MODEL AND VALIDATION
# ============================================================

class TextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)


def clean_input(text: str) -> str:
    if not isinstance(text, str):
        raise HTTPException(status_code=422, detail="Text must be a string.")

    text = text.strip()

    if not text:
        raise HTTPException(status_code=400, detail="Please enter some text.")

    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Text must not exceed {MAX_TEXT_LENGTH} characters."
        )

    return text


# ============================================================
# GEMINI HELPER
# ============================================================


def gemini_json(prompt: str) -> Dict[str, Any]:
    """
    Generate structured JSON using Gemini with automatic retries.
    """
    if client is None:
        raise RuntimeError("Gemini API is not configured.")

    last_error = None

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )

            response_text = (response.text or "").strip()

            if not response_text:
                raise ValueError("Gemini returned an empty response.")

            response_text = re.sub(
                r"^```(?:json)?\s*|\s*```$",
                "",
                response_text,
                flags=re.IGNORECASE
            ).strip()

            result = json.loads(response_text)

            if not isinstance(result, dict):
                raise ValueError("Gemini response was not a JSON object.")

            return result

        except Exception as e:
            last_error = e
            print(f"Gemini attempt {attempt + 1} failed: {e}")

            if attempt < 2:
                time.sleep(2 ** (attempt + 1))

    raise RuntimeError(f"Gemini failed after 3 attempts: {last_error}")



def safe_string(value: Any, default: str = "") -> str:
    return value.strip() if isinstance(value, str) else default


def safe_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []

    return [
        str(item).strip()
        for item in value
        if isinstance(item, (str, int, float)) and str(item).strip()
    ]


# ============================================================
# HOME AND HEALTH
# ============================================================

@app.get("/")
def home():
    dashboard_file = BASE_DIR / "android-app" / "index.html"

    if dashboard_file.exists():
        return FileResponse(dashboard_file)

    return {
        "application": "ToneGuard AI",
        "status": "running",
        "message": "ToneGuard AI backend is active."
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "application": "ToneGuard AI",
        "ai_configured": client is not None,
        "model": MODEL_NAME if client else None
    }


# ============================================================
# LOCAL TONE ANALYSIS FALLBACK
# ============================================================

TONE_PATTERNS = {
    "Aggressive": [
    r"\bshut up\b",
    r"\bdo it now\b",
    r"\bwhat is wrong with you\b",
    r"\byou are useless\b",
    r"\bstop making excuses\b",
    r"\bi don't care\b",
    r"\bstop wasting my time\b",
    r"\bfinish .* immediately\b",
    r"\bdo this immediately\b",
    r"\bget it done now\b",
    r"\bi am not going to tolerate\b"
],
    "Harsh": [
        r"\byou never\b",
        r"\byou always\b",
        r"\bthis is ridiculous\b",
        r"\bterrible work\b",
        r"\bcompletely wrong\b",
        r"\bnot acceptable\b"
    ],
    "Frustrated": [
        r"\bi am tired of\b",
        r"\bi'm tired of\b",
        r"\bhow many times\b",
        r"\bstill not done\b",
        r"\bthis is frustrating\b",
        r"\bwhy is this taking so long\b"
    ],
    "Disappointed": [
        r"\bi am disappointed\b",
        r"\bi'm disappointed\b",
        r"\bexpected better\b",
        r"\blet me down\b",
        r"\bnot what i expected\b"
    ],
    "Apologetic": [
        r"\bi apologize\b",
        r"\bi'm sorry\b",
        r"\bi am sorry\b",
        r"\bmy mistake\b",
        r"\bplease forgive me\b"
    ],
    "Friendly": [
        r"\bgreat job\b",
        r"\bwell done\b",
        r"\bhappy to help\b",
        r"\bhope you are doing well\b",
        r"\blooking forward to\b"
    ],
    "Polite": [
    r"\bcould you please\b",
    r"\bwould you please\b",
    r"\bwould you mind\b",
    r"\bthank you\b",
    r"\bkindly\b",
    r"\bplease let me know\b",
    r"\bplease send\b",
    r"\bi appreciate your help\b",
    r"\bthank you so much\b"
],
    "Persuasive": [
        r"\bi recommend\b",
        r"\bwe should consider\b",
        r"\bthe best option\b",
        r"\bi strongly suggest\b",
        r"\bthis would help\b"
    ],
    "Assertive": [
        r"\bi disagree\b",
        r"\bi believe\b",
        r"\bi expect\b",
        r"\bwe need to\b",
        r"\bi cannot agree\b"
    ]
}


def local_tone_analysis(text: str) -> Dict[str, Any]:
    """
    Basic offline fallback.
    This is deliberately labelled as heuristic, not AI analysis.
    """

    lower = text.lower()
    found_tones = []
    detected_phrases = []

    for tone, patterns in TONE_PATTERNS.items():
        matches = []

        for pattern in patterns:
            for match in re.finditer(pattern, lower):
                matches.append(match.group(0))

        if matches:
            found_tones.append(tone)
            detected_phrases.extend(matches)

    if "Aggressive" in found_tones:
        primary = "Aggressive"
    elif "Harsh" in found_tones:
        primary = "Harsh"
    elif "Frustrated" in found_tones:
        primary = "Frustrated"
    elif "Disappointed" in found_tones:
        primary = "Disappointed"
    elif "Apologetic" in found_tones:
        primary = "Apologetic"
    elif "Polite" in found_tones:
        primary = "Polite"
    elif "Friendly" in found_tones:
        primary = "Friendly"
    elif "Persuasive" in found_tones:
        primary = "Persuasive"
    elif "Assertive" in found_tones:
        primary = "Assertive"
    else:
        primary = "Neutral"

    secondary = [tone for tone in found_tones if tone != primary]

    if len(found_tones) > 1:
        explanation = (
            "The local fallback found language patterns associated with "
            + ", ".join(found_tones)
            + ". Context may change how these expressions are interpreted."
        )
    elif found_tones:
        explanation = (
            f"Some expressions resemble a {primary.lower()} communication style. "
            "This is a rule-based estimate and may miss context."
        )
    else:
        explanation = (
            "No strong tone patterns were identified by the local fallback. "
            "The message may be neutral, or its tone may depend on context."
        )

    # These are heuristic estimates, not calibrated probabilities.
    if len(found_tones) > 1:
        confidence = 0.55
        confidence_level = "Low"
    elif found_tones:
        confidence = 0.60
        confidence_level = "Low"
    else:
        confidence = 0.40
        confidence_level = "Low"

    suggestion = {
        "Aggressive": "Consider replacing commands with respectful requests.",
        "Harsh": "Use specific, constructive language instead of absolute statements.",
        "Frustrated": "Describe the issue calmly and explain what action is needed.",
        "Disappointed": "Explain the unmet expectation while keeping the message constructive.",
        "Apologetic": "The message communicates an apology. Keep it sincere and clear.",
        "Polite": "The message uses polite expressions. Keep the request clear.",
        "Friendly": "The message sounds warm. Maintain this approachable style.",
        "Persuasive": "Support your recommendation with clear reasons.",
        "Assertive": "State your position clearly while acknowledging other viewpoints.",
        "Neutral": "The message appears neutral based on the limited local checks."
    }.get(primary, "Review the wording in its full communication context.")

    return {
        "original_text": text,
        "detected_tone": primary,
        "secondary_tones": secondary,
        "confidence": confidence,
        "confidence_level": confidence_level,
        "detected_words": list(dict.fromkeys(detected_phrases)),
        "explanation": explanation,
        "suggestion": suggestion,
        "is_mixed_tone": len(found_tones) > 1,
        "method": "Local heuristic fallback"
    }


# ============================================================
# AI TONE ANALYSIS
# ============================================================

@app.post("/analyze")
def analyze_text(request: TextRequest):
    text = clean_input(request.text)

    if client is None:
        return local_tone_analysis(text)

    prompt = f"""
You are a careful expert in human communication, pragmatics,
emotion and professional writing.

Analyse the tone of the message below. Interpret the complete
message in context. Do not classify tone from isolated keywords alone.

MESSAGE:
<<<
{text}
>>>

Possible tone labels include:
Professional, Formal, Friendly, Polite, Neutral, Assertive,
Aggressive, Harsh, Frustrated, Disappointed, Sarcastic,
Persuasive, Apologetic, Concerned, Excited, Sad, Confident,
Urgent, Uncertain, Supportive and Mixed.

Instructions:
1. Choose one primary tone that best describes the overall message.
2. Add secondary tones only when clearly present.
3. A short sentence can still have a tone. Do not automatically label
   short messages as neutral.
4. Consider punctuation, wording, sentence structure and context.
5. Do not assume words such as "please", "immediately", "never"
   or "always" determine tone by themselves.
6. Sarcasm should only be identified when there is meaningful evidence.
   If uncertain, explain the ambiguity.
7. Identify exact words or phrases that contribute to the tone.
   Return an empty list if no specific phrase is clearly responsible.
8. Explain the reasoning in plain English.
9. Give a practical suggestion if the message could be misunderstood.
10. Do not invent the sender's intention or relationship with the reader.
11. The confidence value is an estimated strength of the interpretation,
    not a statistically calibrated probability. Be conservative.
12. If context is insufficient, use a lower confidence and say so.
13. If the message contains contrasting emotional signals, mark it as mixed.

Return ONLY valid JSON with exactly these keys:

{{
  "detected_tone": "one primary tone",
  "secondary_tones": ["optional other tones"],
  "confidence": 0.0,
  "confidence_level": "High, Medium or Low",
  "detected_words": ["exact phrase from the message"],
  "explanation": "why this tone was identified",
  "suggestion": "practical communication suggestion",
  "is_mixed_tone": false
}}

Confidence guidance:
- High: the wording provides clear and consistent evidence.
- Medium: the interpretation is plausible but has some ambiguity.
- Low: context is limited or multiple interpretations are possible.

Do not always return the same confidence. Evaluate each message independently.
"""

    try:
        result = gemini_json(prompt)

        primary = safe_string(result.get("detected_tone"), "Neutral")
        secondary = safe_string_list(result.get("secondary_tones"))
        words = safe_string_list(result.get("detected_words"))
        explanation = safe_string(
            result.get("explanation"),
            "The tone was analysed using the available message context."
        )
        suggestion = safe_string(
            result.get("suggestion"),
            "Review the message for clarity and the intended audience."
        )

        try:
            confidence = float(result.get("confidence", 0.5))
        except (ValueError, TypeError):
            confidence = 0.5

        confidence = max(0.0, min(1.0, confidence))

        level = safe_string(result.get("confidence_level"), "Medium")
        if level not in ["High", "Medium", "Low"]:
            level = "Medium"

        mixed = result.get("is_mixed_tone", False)
        if not isinstance(mixed, bool):
            mixed = False

        return {
            "original_text": text,
            "detected_tone": primary,
            "secondary_tones": secondary,
            "confidence": confidence,
            "confidence_level": level,
            "detected_words": words,
            "explanation": explanation,
            "suggestion": suggestion,
            "is_mixed_tone": mixed,
            "method": "Gemini AI contextual analysis"
        }

    
    except Exception as e:
      print("GEMINI ANALYSIS ERROR:", repr(e))
      print("Switching to local tone analysis...")
      return local_tone_analysis(text)



# ============================================================
# LOCAL GRAMMAR FALLBACK
# ============================================================

def preserve_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()

    if original.istitle():
        return replacement.capitalize()

    return replacement


def local_grammar_correction(text: str) -> Dict[str, Any]:
    """
    Conservative offline correction rules.
    This is not a complete grammar engine.
    """

    corrected = text
    corrections = []

    def replace_pattern(pattern: str, replacement: Any, description: str):
        nonlocal corrected

        updated, count = re.subn(
            pattern,
            replacement,
            corrected,
            flags=re.IGNORECASE
        )

        if count:
            corrections.append({
                "type": description,
                "count": count
            })
            corrected = updated

    # Common contractions without apostrophes.
    contraction_map = {
        r"\bdont\b": "don't",
        r"\bdoesnt\b": "doesn't",
        r"\bdidnt\b": "didn't",
        r"\bcant\b": "can't",
        r"\bwont\b": "won't",
        r"\bisnt\b": "isn't",
        r"\barent\b": "aren't",
        r"\bwasnt\b": "wasn't",
        r"\bwerent\b": "weren't",
        r"\bhavent\b": "haven't",
        r"\bhasnt\b": "hasn't"
    }

    for pattern, replacement in contraction_map.items():
        replace_pattern(pattern, replacement, "Contraction")

    # Subject and auxiliary agreement.
    agreement_rules = [
        (r"\b(he|she|it)\s+don't\b", r"\1 doesn't"),
        (r"\b(i|you|we|they)\s+doesn't\b", r"\1 don't"),
        (r"\b(he|she|it)\s+have\b", r"\1 has"),
        (r"\b(i|you|we|they)\s+has\b", r"\1 have"),
        (r"\b(he|she|it)\s+are\b", r"\1 is"),
        (r"\b(i)\s+are\b", r"\1 am"),
        (r"\b(you|we|they)\s+is\b", r"\1 are"),
        (r"\b(he|she|it)\s+were\b", r"\1 was"),
        (r"\b(you|we|they)\s+was\b", r"\1 were"),
    ]

    for pattern, replacement in agreement_rules:
        replace_pattern(pattern, replacement, "Subject-verb agreement")

    # Common auxiliary verb mistakes.
    verb_rules = [
        (r"\bdoesn't\s+([a-z]+)s\b", r"doesn't \1"),
        (r"\bdidn't\s+(went|ate|came|saw|wrote|made|took|gave)\b",
         lambda m: "didn't " + {
             "went": "go", "ate": "eat", "came": "come",
             "saw": "see", "wrote": "write", "made": "make",
             "took": "take", "gave": "give"
         }[m.group(1).lower()]),
        (r"\bdon't\s+(likes|goes|plays|works|knows|wants)\b",
         lambda m: "don't " + m.group(1)[:-1]),
    ]

    for pattern, replacement in verb_rules:
        replace_pattern(pattern, replacement, "Verb form")

    # Common expressions and articles.
    phrase_rules = [
        (r"\bto office\b", "to the office"),
        (r"\bgo to home\b", "go home"),
        (r"\bdiscuss about\b", "discuss"),
        (r"\breturn back\b", "return"),
        (r"\bmore better\b", "better"),
        (r"\bmost best\b", "best"),
        (r"\bone of the best student\b", "one of the best students"),
        (r"\baccording to me\b", "in my opinion"),
        (r"\bi am agree\b", "I agree"),
        (r"\bhe do not\b", "he does not"),
        (r"\bshe do not\b", "she does not"),
        (r"\bit do not\b", "it does not"),
        (r"\bthe meeting are\b", "the meeting is"),
        (r"\bmeeting are\b", "meeting is"),
        (r"\bis postpone\b", "is postponed"),
        (r"\bare postpone\b", "are postponed")
    ]

    for pattern, replacement in phrase_rules:
        replace_pattern(pattern, replacement, "Common expression")

    # Capitalize standalone first-person pronoun.
    replace_pattern(r"\bi\b", "I", "Capitalization")

    # Remove repeated spaces.
    cleaned = re.sub(r"[ \t]{2,}", " ", corrected)
    if cleaned != corrected:
        corrections.append({"type": "Extra spaces", "count": 1})
    corrected = cleaned.strip()

    # Capitalize the first character.
    if corrected:
        corrected = corrected[0].upper() + corrected[1:]

    # Add punctuation if missing.
    if corrected and corrected[-1] not in ".!?":
        corrected += "."
        corrections.append({"type": "Missing punctuation", "count": 1})

    return {
        "original_text": text,
        "corrected_text": corrected,
        "corrections": corrections,
        "method": "Local rule-based fallback"
    }


# ============================================================
# AI GRAMMAR CORRECTION
# ============================================================

@app.post("/grammar")
def correct_grammar(request: TextRequest):
    text = clean_input(request.text)

    if client is None:
        return local_grammar_correction(text)

    prompt = f"""
You are an expert English grammar correction assistant.

Correct the grammar of the text below.

TEXT:
<<<
{text}
>>>

Correct genuine errors involving:
- Subject-verb agreement
- Verb tense and verb forms
- Articles and determiners
- Prepositions
- Pronouns
- Singular and plural forms
- Incorrect contractions
- Spelling
- Punctuation
- Capitalization
- Sentence structure and word order

Important rules:
1. Preserve the original meaning and intent.
2. Do not add facts or new information.
3. Do not change names, dates, numbers or technical terms.
4. Do not unnecessarily rewrite correct sentences.
5. Preserve the original tone and writing style as much as possible.
6. Do not make the language overly formal unless needed for grammar.
7. If the text is already correct, return it unchanged.
8. Correct all sentences, not only the first sentence.
9. Do not explain the corrections inside corrected_text.
10. List the important corrections separately.

Return ONLY valid JSON:

{{
  "corrected_text": "complete corrected text",
  "corrections": [
    {{
      "original": "incorrect phrase",
      "corrected": "correct phrase",
      "reason": "short grammar explanation"
    }}
  ]
}}
"""

    try:
        result = gemini_json(prompt)

        corrected = safe_string(result.get("corrected_text"))

        if not corrected:
            raise ValueError("Gemini returned no corrected text.")

        corrections = result.get("corrections", [])
        if not isinstance(corrections, list):
            corrections = []

        return {
            "original_text": text,
            "corrected_text": corrected,
            "corrections": corrections,
            "method": "Gemini AI grammar correction"
        }

    except Exception:
        logger.exception("Gemini grammar correction failed. Using local fallback.")
        return local_grammar_correction(text)


# ============================================================
# LOCAL PROFESSIONAL REWRITING FALLBACK
# ============================================================

def local_professional_rewrite(text: str) -> str:
    rewritten = text.strip()

    replacements = [
        (
            r"\bi am tired of asking you again\b",
            "I would appreciate your response, as I have followed up previously"
        ),
        (
            r"\byou are delaying everything\b",
            "There appears to be a delay"
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
            r"\bdo it now\b",
            "Could you please complete this as soon as possible"
        ),
        (
            r"\bgive me\b",
            "Could you please provide me with"
        ),
        (
            r"\bthis is wrong\b",
            "This may need some correction"
        ),
        (
            r"\byou are not doing the work properly\b",
            "There are some aspects of the work that may need improvement"
        )
    ]

    for old, new in replacements:
        rewritten = re.sub(old, new, rewritten, flags=re.IGNORECASE)

    if rewritten:
        rewritten = rewritten[0].upper() + rewritten[1:]

        if rewritten[-1] not in ".!?":
            rewritten += "."

    return rewritten


# ============================================================
# AI PROFESSIONAL REWRITING
# ============================================================

@app.post("/rewrite")
def rewrite_message(request: TextRequest):
    text = clean_input(request.text)

    if client is None:
        return {
            "original_text": text,
            "rewritten_text": local_professional_rewrite(text),
            "method": "Local professional rewriting fallback"
        }

    prompt = f"""
You are an expert professional communication editor.

Rewrite the message below so it sounds polite, clear,
respectful and professional.

ORIGINAL MESSAGE:
<<<
{text}
>>>

Rules:
1. Preserve the original meaning and intention.
2. Do not invent facts, dates, names, deadlines or promises.
3. Do not remove important instructions or information.
4. Avoid making the message unnecessarily long.
5. Keep the original language.
6. Make demanding or harsh wording more respectful.
7. Keep urgent requests appropriately urgent.
8. Do not make a direct statement sound uncertain unless necessary.
9. Return only the rewritten message, without quotation marks or explanation.
"""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3
            )
        )

        rewritten = (response.text or "").strip()

        if not rewritten:
            raise ValueError("Gemini returned an empty rewrite.")

        return {
            "original_text": text,
            "rewritten_text": rewritten,
            "method": "Gemini AI professional rewriting"
        }

    except Exception:
        logger.exception("Gemini rewriting failed. Using local fallback.")

        return {
            "original_text": text,
            "rewritten_text": local_professional_rewrite(text),
            "method": "Local professional rewriting fallback",
            "message": "AI rewriting was unavailable. A limited local fallback was used."
        }


# ============================================================
# RUN WITH:
# uvicorn backend.main:app --reload
# ============================================================
