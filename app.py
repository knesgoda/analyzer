import json
import google.generativeai as genai
from typing import List
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
    role: str = Field(..., description="Role in scene: 'Main' or 'Secondary'")
    visual_description: str = Field(..., description="Visual description only. Full-body character cutout, centered, consistent scale, high detail, no background, no shadow, no text, 4k. NO TEXT CUES.")

class Skybox(BaseModel):
    visual_prompt: str = Field(..., description="The description of the environment. POV: ground view, center eye level. Environment ONLY.")
    environment_type: str = Field(..., description="'Indoors' or 'Outdoors'")

class Scene(BaseModel):
    location: str
    chapter_beat: str
    trigger_sentence: str = Field(..., description="Verbatim sentence from text acting as the anchor.")
    characters: List[Character]
    skybox_environment: Skybox

class ChapterOutput(BaseModel):
    scenes: List[Scene]

# --- PROMPT ---
def generate_system_prompt(book_title: str) -> str:
    return f"""
    You are the Cinematic Director for the AR project: "{book_title} | AR Scene Pack | Outputs v1".
    
    YOUR GOAL: Deep read the provided text and extract the most exciting cinematic moments for Augmented Reality.
    
    RULES FOR SCENE SELECTION:
    1. Minimum Coverage: Find at least THREE (3) scenes in this text chunk. We need high density.
    2. Epic Scaling: If the text contains high drama, big reveals, or spectacle, generate as many scenes as needed.
    3. No Duplicates: No two scenes can share the same trigger sentence.
    
    RULES FOR OUTPUTS:
    1. Trigger Sentences: Must be verbatim from the text.
    2. Skybox Prompts: Environment ONLY. No people/animals. Format: [Indoors/Outdoors] [Setting] [Era], [Time/Weather/Lighting], [Style: 3D watercolor].
    3. Character Descriptions: Visuals ONLY. No text cues.
    
    OUTPUT FORMAT:
    Return a valid JSON object matching this structure:
    {{
        "scenes": [
            {{
                "location": "string",
                "chapter_beat": "string",
                "trigger_sentence": "string",
                "characters": [ {{"name": "string", "role": "Main/Secondary", "visual_description": "string"}} ],
                "skybox_environment": {{ "visual_prompt": "string", "environment_type": "Indoors/Outdoors" }}
            }}
        ]
    }}
    """

# --- ANALYZER ---
def analyze_chapter_content(api_key: str, text_chunk: str, book_title: str) -> List[Scene]:
    # Configure API
    genai.configure(api_key=api_key)
    
    # Using 1.5 Pro for stability.
    model = genai.GenerativeModel(
        'gemini-1.5-pro', 
        generation_config={"response_mime_type": "application/json"}
    )
    
    system_instructions = generate_system_prompt(book_title)
    user_prompt = f"{system_instructions}\n\nAnalyze this text chunk:\n\n{text_chunk[:45000]}"
    
    # We allow the error to bubble up so Streamlit shows it (No try/except)
    response = model.generate_content(user_prompt)
    
    # Parse
    raw_json = response.text
    data = json.loads(raw_json)
    structured_data = ChapterOutput(**data)
    
    # Add Negative Prompts
    for scene in structured_data.scenes:
        if not hasattr(scene.skybox_environment, 'negative_prompt'):
            scene.skybox_environment.negative_prompt = SKYBOX_NEGATIVE_PROMPT
        
    return structured_data.scenes
