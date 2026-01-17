import json
from typing import List, Tuple
from openai import OpenAI
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
    Analyzes content using OpenAI GPT-4o.
    """
    try:
        client = OpenAI(api_key=api_key)
        
        system_instructions = generate_system_prompt(book_title)
        
        # We limit the chunk to ~40k chars to stay safe, though GPT-4o has 128k context.
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": f"Analyze this text chunk:\n\n{text_chunk[:45000]}"}
            ],
            response_format={"type": "json_object"}
        )
        
        raw_json = response.choices[0].message.content
        
        try:
            data = json.loads(raw_json)
            # OpenAI sometimes wraps the list in a root key like "scenes", 
            # Pydantic handles validation, but we ensure the root matches ChapterOutput
            structured_data = ChapterOutput(**data)
        except Exception as json_err:
            return [], f"JSON Parsing Failed: {json_err}"

        # Add Negative Prompts
        for scene in structured_data.scenes:
            if not hasattr(scene.skybox_environment, 'negative_prompt'):
                scene.skybox_environment.negative_prompt = SKYBOX_NEGATIVE_PROMPT
            
        return structured_data.scenes, None

    except Exception as e:
        return [], str(e)
