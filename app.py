import streamlit as st
import io
import os
from docx import Document
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import analyzer 

# --- CONFIGURATION ---
st.set_page_config(page_title="OutPaged Scene Generator", layout="wide")

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

# 1. Initialize Session State for Title
if 'detected_title' not in st.session_state:
    st.session_state['detected_title'] = "Waiting for file..."

# 2. Upload File (We do this BEFORE the sidebar input so we can update the state if needed)
uploaded_file = st.file_uploader("Upload EPUB", type=["epub"])

if uploaded_file:
    # Only parse if we haven't already processed this specific file upload
    # (Streamlit re-runs the whole script on interaction, so we check if the title needs updating)
    if st.session_state['detected_title'] == "Waiting for file...":
        detected_title, chapters = parse_epub(uploaded_file)
        if detected_title != "Unknown Title":
            st.session_state['detected_title'] = detected_title
            st.rerun() # Restart the script immediately to populate the sidebar correctly

# 3. Sidebar Configuration
with st.sidebar:
    st.header("Configuration")
    
    api_key = st.text_input("Google Gemini API Key", type="password")
    
    # FIX: We removed key='detected_title' to prevent the crash.
    # We set the default value from state, but capture the user's edit in a new variable.
    book_title = st.text_input("Book Title", value=st.session_state['detected_title'])
    
    st.info("Upload an EPUB to begin.")

# 4. Main Execution Logic
if uploaded_file and book_title != "Waiting for file...":
    # Re-parse quickly to get chapters (cached in memory usually, but fast enough to redo)
    _, chapters = parse_epub(uploaded_file)
    
    st.success(f"Ready to process '{book_title}' ({len(chapters)} Chapters)")

    if st.button("Generate Scene Pack"):
        if not api_key:
            st.error("⚠️ Stop! You must provide a Google Gemini API Key to proceed.")
        else:
            all_scenes = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, chapter_text in enumerate(chapters):
                progress = (i + 1) / len(chapters)
                progress_bar.progress(progress)
                status_text.text(f"Analyzing Chapter {i+1}/{len(chapters)}...")
                
                # Production Call
                chapter_scenes = analyzer.analyze_chapter_content(api_key, chapter_text, book_title)
                all_scenes.extend(chapter_scenes)
            
            status_text.text("Compiling Documents...")
            d1, d2, d3 = generate_documents(book_title, all_scenes)
            
            st.success(f"Production Run Complete! Generated {len(all_scenes)} scenes.")
            
            c1, c2, c3 = st.columns(3)
            file_prefix = book_title.replace(" ", "_")
            
            with c1:
                st.download_button("📄 Download Triggers", d1, f"{file_prefix}_Document_1_Triggers.docx")
            with c2:
                st.download_button("🖼️ Download Skybox", d2, f"{file_prefix}_Document_2_Backgrounds.docx")
            with c3:
                st.download_button("👤 Download Characters", d3, f"{file_prefix}_Document_3_Characters.docx")
