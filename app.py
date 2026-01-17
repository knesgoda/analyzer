import streamlit as st
import io
import os
from docx import Document
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

# IMPORT THE GEMINI ANALYZER MODULE
import analyzer 

# --- CONFIGURATION ---
st.set_page_config(page_title="OutPaged Scene Generator", layout="wide")

# --- CORE DATA STRUCTURES RE-MAPPED ---
class SimpleCharacter:
    def __init__(self, name, role, visual_description):
        self.name = name
        self.role = role
        self.visual_description = visual_description

class SimpleSkybox:
    def __init__(self, visual_prompt, environment_type, negative_prompt):
        self.visual_prompt = visual_prompt
        self.environment_type = environment_type
        self.negative_prompt = negative_prompt

class SimpleScene:
    def __init__(self, location, chapter_beat, trigger_sentence, characters, skybox_environment):
        self.location = location
        self.chapter_beat = chapter_beat
        self.trigger_sentence = trigger_sentence
        self.characters = characters 
        self.skybox_environment = skybox_environment

# --- EPUB LOGIC ---

def parse_epub(uploaded_file):
    """
    Parses the EPUB and extracts the Title and Chapter Content.
    """
    try:
        book = epub.read_epub(uploaded_file)
    except Exception as e:
        st.error(f"Error reading EPUB: {e}")
        return "Unknown Title", []

    # 1. Auto-Detect Title
    try:
        title_meta = book.get_metadata('DC', 'title')
        if title_meta:
            book_title = title_meta[0][0]
        else:
            book_title = "Untitled Book"
    except:
        book_title = "Untitled Book"

    # 2. Extract Chapters
    chapters = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text(separator='\n').strip()
            # Filter out tiny pages (TOC, copyright, spacers)
            if len(text) > 500:
                chapters.append(text)
                
    return book_title, chapters

# --- DOCUMENT GENERATOR ---

def generate_documents(book_title, all_scenes):
    doc1 = Document()
    doc2 = Document()
    doc3 = Document()
    
    # Headers
    doc1.add_heading(f"{book_title} | AR Scene Pack | Outputs v1", 0)
    doc1.add_paragraph("Document 1: Trigger Sentences Per Scene")
    doc2.add_heading(f"{book_title} | AR Scene Pack | Outputs v1", 0)
    doc2.add_paragraph("Document 2: Skybox Background Prompts (Blockade Labs Standard)")
    doc3.add_heading(f"{book_title} | AR Scene Pack | Outputs v1", 0)
    doc3.add_paragraph("Document 3: Character Descriptions (No Cues)")

    global_idx = 1
    
    for scene in all_scenes:
        scene_id = f"ch{global_idx:02}"
        
        # DOC 1: Triggers
        doc1.add_heading(f"Scene {global_idx:02} - {scene.location} - {scene.chapter_beat}", level=2)
        p = doc1.add_paragraph(); p.add_run("Trigger sentence: ").bold = True; p.add_run(scene.trigger_sentence)
        p = doc1.add_paragraph(); p.add_run("Page number: ").bold = True; p.add_run("N/A")
        
        # DOC 2: Backgrounds
        # Ensure negative prompt exists (fallback to constant if missing)
        neg_prompt = getattr(scene.skybox_environment, 'negative_prompt', analyzer.SKYBOX_NEGATIVE_PROMPT)
        
        doc2.add_heading(f"Scene {global_idx:02} - {scene.location} - {scene.chapter_beat}", level=2)
        doc2.add_paragraph(f"Background file name:  {scene_id}bg01")
        p = doc2.add_paragraph(); p.add_run("Skybox prompt:  ").bold = True; p.add_run(scene.skybox_environment.visual_prompt)
        p = doc2.add_paragraph(); p.add_run("Negative prompt:  ").bold = True; p.add_run(neg_prompt)
        doc2.add_paragraph()
        
        # DOC 3: Characters
        doc3.add_heading(f"Scene {global_idx:02} - {scene.location} - {scene.chapter_beat}", level=2)
        
        main_chars = [c for c in scene.characters if c.role == "Main"]
        other_chars = [c for c in scene.characters if c.role != "Main"]
        
        # Fallback: if AI didn't tag "Main", assume first character is Main
        if not main_chars and scene.characters:
            main_chars = [scene.characters[0]]
            other_chars = scene.characters[1:]
            
        if main_chars:
            mc = main_chars[0]
            doc3.add_paragraph(f"{mc.name}:")
            doc3.add_paragraph(f"- ref: {scene_id}mc01")
            doc3.add_paragraph(f"prompt: \"{mc.visual_description}\"")
            
        sc_idx = 1
        for sc in other_chars:
            doc3.add_paragraph(f"{sc.name}:")
            doc3.add_paragraph(f"- ref: {scene_id}sc{sc_idx:02}")
            doc3.add_paragraph(f"prompt: \"{sc.visual_description}\"")
            sc_idx += 1
            
        global_idx += 1
        
    def save_doc(d):
        s = io.BytesIO()
        d.save(s)
        s.seek(0)
        return s

    return save_doc(doc1), save_doc(doc2), save_doc(doc3)

# --- UI LOGIC ---

st.title("OutPaged Scene Pack Generator")
st.markdown("Automated EPUB ingestion and Scene Pack generation (Production Mode).")

# Session State for Title persistence
if 'detected_title' not in st.session_state:
    st.session_state['detected_title'] = "Waiting for file..."

with st.sidebar:
    st.header("Configuration")
    
    # API Key is now mandatory and prominent
    api_key = st.text_input("Google Gemini API Key", type="password")
    
    # Title field listens to session state
    book_title = st.text_input("Book Title", key='detected_title')
    
    st.info("Upload an EPUB to begin.")

uploaded_file = st.file_uploader("Upload EPUB", type=["epub"])

if uploaded_file:
    # Auto-Parse on upload
    detected_title, chapters = parse_epub(uploaded_file)
    
    # Update title in session state if it hasn't been set yet
    if st.session_state['detected_title'] == "Waiting for file..." and detected_title != "Unknown Title":
        st.session_state['detected_title'] = detected_title
        st.rerun() # Refresh to show new title in sidebar

    st.success(f"Loaded '{detected_title}' ({len(chapters)} Processable Chapters)")

    # The Big Red Button
    if st.button("Generate Scene Pack"):
        if not api_key:
            st.error("⚠️ Stop! You must provide a Google Gemini API Key to proceed.")
        else:
            all_scenes = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # --- THE LOOP ---
            for i, chapter_text in enumerate(chapters):
                # Update UI
                progress = (i + 1) / len(chapters)
                progress_bar.progress(progress)
                status_text.text(f"Analyzing Chapter {i+1}/{len(chapters)}...")
                
                # Production Call
                chapter_scenes = analyzer.analyze_chapter_content(api_key, chapter_text, book_title)
                all_scenes.extend(chapter_scenes)
            
            # --- FINISH ---
            status_text.text("Compiling Documents...")
            d1, d2, d3 = generate_documents(book_title, all_scenes)
            
            st.success(f"Production Run Complete! Generated {len(all_scenes)} scenes.")
            
            # Download Columns
            c1, c2, c3 = st.columns(3)
            file_prefix = book_title.replace(" ", "_")
            
            with c1:
                st.download_button("📄 Download Triggers", d1, f"{file_prefix}_Document_1_Triggers.docx")
            with c2:
                st.download_button("🖼️ Download Skybox", d2, f"{file_prefix}_Document_2_Backgrounds.docx")
            with c3:
                st.download_button("👤 Download Characters", d3, f"{file_prefix}_Document_3_Characters.docx")
