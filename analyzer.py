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

# --- ANALYZER ---
def analyze_chapter_content(api_key: str, text_chunk: str, book_title: str) -> Tuple[List[Scene], str]:
    """
    Returns a tuple: (List of Scenes, Error Message)
    If successful, Error Message is None.
    """
    try:
        genai.configure(api_key=api_key)
        
        # Using 1.5 Pro for best results
        model = genai.GenerativeModel(
            'gemini-1.5-pro', 
            generation_config={"response_mime_type": "application/json"}
        )
        
        system_instructions = generate_system_prompt(book_title)
        user_prompt = f"{system_instructions}\n\nAnalyze this text:\n\n{text_chunk[:40000]}"
        
        # Call API
        response = model.generate_content(user_prompt)
        
        # Parse Logic
        try:
            data = json.loads(response.text)
            structured_data = ChapterOutput(**data)
        except Exception as json_err:
            return [], f"AI returned bad JSON: {json_err}"

        # Add Negative Prompts
        for scene in structured_data.scenes:
            if not hasattr(scene.skybox_environment, 'negative_prompt'):
                scene.skybox_environment.negative_prompt = SKYBOX_NEGATIVE_PROMPT
            
        return structured_data.scenes, None

    except Exception as e:
        return [], str(e)
