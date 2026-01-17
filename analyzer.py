import json
import google.generativeai as genai
from typing import List, Tuple
from pydantic import BaseModel, Field

# --- CONFIGURATION ---
SKYBOX_NEGATIVE_PROMPT = (
    "people, person, faces, crowds, animals, text, letters, signage, "
    "watermark, logo, UI, placeable props, furniture, vehicles, "
    "modern objects, anachronistic items, blurry"
)

# --- DATA MODELS ---
class Character(BaseModel):
    name: str = Field(..., description="Name of the character")
    role: str = Field(..., description="Role: 'Main' or 'Secondary'")
    visual_description: str = Field(..., description="Visual description only. Full-body character cutout, no text cues.")

class Skybox(BaseModel):
    visual_prompt: str = Field(..., description="Environment description. POV: ground view, center eye level.")
    environment_type: str = Field(..., description="'Indoors' or 'Outdoors'")

class Scene(BaseModel):
    location: str
    chapter_beat: str
    trigger_sentence: str = Field(..., description="Verbatim sentence from text.")
    characters: List[Character]
    skybox_environment: Skybox

class ChapterOutput(BaseModel):
    scenes: List[Scene]

# --- PROMPT ---
def generate_system_prompt(book_title: str) -> str:
    return f"""
    You are the Cinematic Director for the AR project: "{book_title}".
    
    GOAL: Extract cinematic moments for Augmented Reality.
    
    RULES:
    1. FIND AT LEAST 3 SCENES in this text chunk.
    2. Triggers must be VERBATIM text.
    3. Skybox prompts must be ENVIRONMENT ONLY (no people).
    4. Character descriptions must be VISUALS ONLY (no text cues).
    
    OUTPUT: Return valid JSON matching the schema.
    """

# --- HELPER: AUTO-DISCOVER MODEL ---
def get_best_model_name(api_key: str) -> str:
    """
    Connects to Google and asks for the list of available models.
    Picks the best one based on priority.
    """
    genai.configure(api_key=api_key)
    try:
        # List all models
        models = list(genai.list_models())
        # Filter for models that can 'generateContent'
        supported_names = [m.name for m in models if 'generateContent' in m.supported_generation_methods]
        
        # Priority List: 1.5 Pro -> 1.5 Flash -> 1.0 Pro -> Any Gemini
        # We use 'in' matching because names return as 'models/gemini-1.5-pro-001' etc.
        if any('gemini-1.5-pro' in m for m in supported_names):
            return 'gemini-1.5-pro'
        if any('gemini-1.5-flash' in m for m in supported_names):
            return 'gemini-1.5-flash'
        if any('gemini-1.0-pro' in m for m in supported_names):
            return 'gemini-1.0-pro'
        if any('gemini-pro' in m for m in supported_names):
            return 'gemini-pro'
            
        # Last resort: just take the first one that looks like a text model
        if supported_names:
            return supported_names[0]
            
        return 'gemini-pro' # Hope for the best if list is empty
    except:
        return 'gemini-pro' # Fallback if list_models fails

# --- ANALYZER ---
def analyze_chapter_content(api_key: str, text_chunk: str, book_title: str) -> Tuple[List[Scene], str]:
    try:
        # 1. Auto-Discover the correct model name for this API Key
        model_name = get_best_model_name(api_key)
        
        # 2. Configure Client
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name, 
            generation_config={"response_mime_type": "application/json"}
        )
        
        # 3. Prepare Prompt
        system_instructions = generate_system_prompt(book_title)
        # 32k context is safe for Gemini 1.0 Pro (the fallback), 
        # so we cap text at 30k chars to be safe across ALL models.
        user_prompt = f"{system_instructions}\n\nAnalyze this text:\n\n{text_chunk[:30000]}"
        
        # 4. Call API
        response = model.generate_content(user_prompt)
        
        # 5. Parse
        try:
            data = json.loads(response.text)
            structured_data = ChapterOutput(**data)
        except Exception as json_err:
            return [], f"AI Output Error ({model_name}): {json_err}"

        # 6. Post-Process
        for scene in structured_data.scenes:
            if not hasattr(scene.skybox_environment, 'negative_prompt'):
                scene.skybox_environment.negative_prompt = SKYBOX_NEGATIVE_PROMPT
            
        return structured_data.scenes, None

    except Exception as e:
        return [], f"Critical Error with model '{model_name}': {str(e)}"
