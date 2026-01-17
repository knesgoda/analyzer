import json
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError

# --- 1. CONFIGURATION & CONSTANTS (Single Source of Truth) ---

SKYBOX_NEGATIVE_PROMPT = (
    "people, person, faces, crowds, animals, text, letters, signage, "
    "watermark, logo, UI, placeable props, furniture, vehicles, "
    "modern objects, anachronistic items, blurry"
)

# We define the strict schema the AI *must* adhere to.
# This prevents "instruction drift."

class Character(BaseModel):
    name: str = Field(..., description="Name of the character")
    role: str = Field(..., description="Role in scene: 'Main' or 'Secondary'")
    visual_description: str = Field(
        ..., 
        description="Visual description only. Full-body character cutout, centered, consistent scale, high detail, no background, no shadow, no text, 4k. NO TEXT CUES."
    )

class Skybox(BaseModel):
    # We let the AI generate the creative prompt, but we force the structure in the prompt instructions
    visual_prompt: str = Field(..., description="The description of the environment.")
    # We force the negative prompt in code so the AI can't mess it up
    negative_prompt: str = Field(default=SKYBOX_NEGATIVE_PROMPT)
    environment_type: str = Field(..., description="'Indoors' or 'Outdoors'")

class Scene(BaseModel):
    location: str
    chapter_beat: str
    trigger_sentence: str = Field(..., description="Verbatim sentence from text acting as the anchor.")
    # Note: We do NOT ask the AI for 'ch01'. The code assigns that later to guarantee sequence.
    characters: List[Character]
    skybox_environment: Skybox

class ChapterOutput(BaseModel):
    scenes: List[Scene]

# --- 2. THE AI PROMPT LOGIC ---

def generate_system_prompt(book_title: str) -> str:
    """
    Constructs the specific instructions for the AI based on the Project Brief.
    """
    return f"""
    You are the Cinematic Director for the AR project: "{book_title} | AR Scene Pack | Outputs v1".
    
    YOUR GOAL: Deep read the provided text and extract the most exciting cinematic moments for Augmented Reality.
    
    RULES FOR SCENE SELECTION:
    1. Minimum Coverage: Find at least TWO scenes in this text chunk.
    2. Epic Scaling: If the text contains high drama, big reveals, or spectacle, generate as many scenes as needed. There is no upper limit.
    3. No Duplicates: No two scenes can share the same trigger sentence.
    
    RULES FOR OUTPUTS:
    1. Trigger Sentences: Must be verbatim from the text. Choose the strongest hook line.
    2. Skybox Prompts: 
       - POV: Ground view, center eye level.
       - Environment ONLY. No people, no animals, no props.
       - Format: [Indoors/Outdoors] [Setting] [Era], [Time/Weather/Lighting], [Style: 3D watercolor].
    3. Character Descriptions: 
       - Visuals ONLY. Do NOT include "Text cue" or dialogue.
       - Style: Full-body character cutout, centered, consistent scale, high detail, no background, no shadow, no text, 4k.
       
    Return the result strictly as a valid JSON object matching the requested schema.
    """

# --- 3. THE ANALYZER FUNCTION ---

def analyze_chapter_content(client, text_chunk: str, book_title: str) -> List[Scene]:
    """
    Simulated function where we call the LLM (OpenAI/Gemini).
    """
    
    system_instructions = generate_system_prompt(book_title)
    
    # PSEUDOCODE for API Call
    # response = client.chat.completions.create(
    #     model="gpt-4o",
    #     messages=[
    #         {"role": "system", "content": system_instructions},
    #         {"role": "user", "content": text_chunk}
    #     ],
    #     response_format={"type": "json_object"}
    # )
    # raw_json = response.choices[0].message.content
    
    # --- MOCK DATA FOR DEMONSTRATION (Based on your Winnie-the-Pooh Example) ---
    # This simulates what the AI *should* return based on your brief.
    
    mock_response = {
        "scenes": [
            {
                "location": "Christopher Robin’s Staircase",
                "chapter_beat": "Part 1 of 3 - Staircase Descent",
                "trigger_sentence": "Here is Edward Bear, coming downstairs now, bump, bump, bump, on the back of his head, behind Christopher Robin.",
                "skybox_environment": {
                    "environment_type": "Indoors",
                    "visual_prompt": "ground view center eye level, indoors Christopher Robin’s nursery staircase, early 20th-century English cottage, morning light through window, warm cozy shadows, 3D watercolor, 2:1 360",
                    "negative_prompt": SKYBOX_NEGATIVE_PROMPT
                },
                "characters": [
                    {
                        "name": "Winnie-the-Pooh",
                        "role": "Main",
                        "visual_description": "Small teddy bear (childlike, 2'0\" tall). Golden fur, round belly, gentle eyes. Wears a short red shirt. Soft plush texture, friendly expression. Full-body character cutout, centered, consistent scale, high detail, no background, no shadow, no text, 4k."
                    }
                ]
            },
            {
                "location": "Hundred Acre Wood Clearing",
                "chapter_beat": "Part 2 of 3 - Umbrella Cloud Trick",
                "trigger_sentence": "I wish you would bring it out here, and walk up and down with it, and look up at me every now and then, and say 'Tut-tut, it looks like rain.'",
                "skybox_environment": {
                    "environment_type": "Outdoors",
                    "visual_prompt": "ground view center eye level, outdoors Hundred Acre Wood forest clearing, early 20th-century English countryside, bright midday sun, soft breeze, dappled canopy light, 3D watercolor, 2:1 360",
                    "negative_prompt": SKYBOX_NEGATIVE_PROMPT
                },
                "characters": [
                    {
                        "name": "Winnie-the-Pooh",
                        "role": "Main",
                        "visual_description": "Small teddy bear floating under a blue balloon. Golden fur, muddy paws. Full-body character cutout, centered, consistent scale, high detail, no background, no shadow, no text, 4k."
                    },
                    {
                         "name": "Christopher Robin",
                         "role": "Secondary",
                         "visual_description": "Young boy (8, 4'0\"). Neat hair, curious eyes. Wears a simple sweater. Walking with umbrella. Full-body character cutout, centered, consistent scale, high detail, no background, no shadow, no text, 4k."
                    }
                ]
            }
        ]
    }
    
    # VALIDATION STEP
    # We pass the raw JSON into Pydantic. If the AI missed a field or formatted it wrong,
    # this line will throw an error, protecting your downstream documents.
    try:
        structured_data = ChapterOutput(**mock_response)
        
        # [cite_start]LOGIC CHECK: Minimum Coverage Rule [cite: 5]
        if len(structured_data.scenes) < 2:
            print("WARNING: Coverage too low. Triggering re-prompt for Epic Scaling...")
            # In a real app, we would loop back here to re-prompt the AI.
            
        return structured_data.scenes
        
    except ValidationError as e:
        print(f"Data Validation Failed: {e}")
        return []

# --- 4. THE POST-PROCESSOR (The "Sequencer") ---

def sequence_and_format(all_scenes_from_book: List[Scene]):
    """
    This function takes the unordered lists from the AI and applies
    the strict file naming conventions (ch01, ch02...)
    """
    print(f"--- GENERATING OUTPUTS FOR: Winnie-the-Pooh | AR Scene Pack | Outputs v1 ---")
    
    global_scene_index = 1
    
    for scene in all_scenes_from_book:
        # Create the Scene ID string (e.g., "ch01", "ch12")
        scene_id = f"ch{global_scene_index:02}"
        
        # 1. Generate Filenames
        bg_filename = f"{scene_id}bg01"
        mc_filename = f"{scene_id}mc01"
        
        print(f"\n[SCENE {global_scene_index}] {scene.location} - {scene.chapter_beat}")
        print(f"   > Trigger (Page N/A): \"{scene.trigger_sentence[:50]}...\"")
        print(f"   > Background File: {bg_filename}")
        print(f"   > Skybox Prompt: {scene.skybox_environment.visual_prompt}")
        
        # Character Iteration for filenames
        sc_counter = 1
        for char in scene.characters:
            if char.role == "Main":
                file_ref = mc_filename
            else:
                file_ref = f"{scene_id}sc{sc_counter:02}"
                sc_counter += 1
            
            print(f"   > Character ({file_ref}): {char.name}")
            # Note: We stripped the text cues in the Pydantic model definition
        
        global_scene_index += 1

# --- 5. EXECUTION ---

if __name__ == "__main__":
    # Simulate reading a book chapter
    dummy_text = "Raw text from Winnie the Pooh chapter 1..."
    
    # Run the Agent
    extracted_scenes = analyze_chapter_content(None, dummy_text, "Winnie-the-Pooh")
    
    # Run the Sequencer
    if extracted_scenes:
        sequence_and_format(extracted_scenes)
