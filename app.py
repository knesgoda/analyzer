import streamlit as st

# --- 1. CONFIGURATION (MUST BE FIRST) ---
st.set_page_config(page_title="OutPaged Scene Generator", layout="wide")

import io
import warnings
warnings.filterwarnings("ignore")

from docx import Document
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import analyzer 

# --- 2. EPUB LOGIC ---
def parse_epub(uploaded_file):
    try:
        book = epub.read_epub(uploaded_file)
        title_meta = book.get_metadata('DC', 'title')
        book_title = title_meta[0][0] if title_meta else "Untitled Book"
        
        chapters = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                text = soup.get_text(separator='\n').strip()
                if len(text) > 500:
                    chapters.append(text)
        return book_title, chapters
    except Exception as e:
        return "Error", []

# --- 3. DOC GENERATOR ---
def generate_documents(book_title, all_scenes):
    doc1 = Document(); doc1.add_heading(f"{book_title} | Triggers", 0)
    doc2 = Document(); doc2.add_heading(f"{book_title} | Skybox", 0)
    doc3 = Document(); doc3.add_heading(f"{book_title} | Characters", 0)
    
    idx = 1
    for scene in all_scenes:
        s_id = f"ch{idx:02}"
        
        # Doc 1
        doc1.add_heading(f"Scene {idx:02}: {scene.location}", level=2)
        doc1.add_paragraph(f"Trigger: {scene.trigger_sentence}")
        doc1.add_paragraph(f"Page: N/A")
        
        # Doc 2
        neg = getattr(scene.skybox_environment, 'negative_prompt', analyzer.SKYBOX_NEGATIVE_PROMPT)
        doc2.add_heading(f"Scene {idx:02}: {scene.location}", level=2)
        doc2.add_paragraph(f"File: {s_id}bg01")
        doc2.add_paragraph(f"Prompt: {scene.skybox_environment.visual_prompt}")
        doc2.add_paragraph(f"Negative: {neg}")
        
        # Doc 3
        doc3.add_heading(f"Scene {idx:02}: {scene.location}", level=2)
        for i, char in enumerate(scene.characters):
            role_tag = "mc" if char.role == "Main" else "sc"
            num = "01" if role_tag == "mc" else f"{i:02}"
            doc3.add_paragraph(f"{char.name} ({s_id}{role_tag}{num}): {char.visual_description}")
            
        idx += 1
        
    def to_stream(d):
        s = io.BytesIO(); d.save(s); s.seek(0); return s
    
    return to_stream(doc1), to_stream(doc2), to_stream(doc3)

# --- 4. UI LOGIC ---
st.title("OutPaged Scene Generator (Flash Edition)")

# Secrets Logic
try:
    secret_key = st.secrets["GEMINI_API_KEY"]
except:
    secret_key = None

# Sidebar
with st.sidebar:
    st.header("Setup")
    if secret_key:
        st.success("✅ Key loaded from Secrets")
        api_key = secret_key
    else:
        api_key = st.text_input("Gemini API Key", type="password")

# File Upload
uploaded_file = st.file_uploader("Upload EPUB", type=["epub"])

if uploaded_file:
    title, chapters = parse_epub(uploaded_file)
    st.info(f"Book: {title} | Chapters: {len(chapters)}")
    
    if st.button("Generate Scenes"):
        if not api_key:
            st.error("Missing API Key.")
            st.stop()
            
        all_scenes = []
        bar = st.progress(0)
        
        for i, chapter in enumerate(chapters):
            bar.progress((i+1)/len(chapters))
            
            # CALL ANALYZER
            scenes, error = analyzer.analyze_chapter_content(api_key, chapter, title)
            
            if error:
                st.error(f"Chapter {i+1} Failed: {error}")
            else:
                all_scenes.extend(scenes)
                
        if not all_scenes:
            st.error("No scenes were generated. Check for model errors above.")
        else:
            st.success(f"Success! {len(all_scenes)} scenes found.")
            d1, d2, d3 = generate_documents(title, all_scenes)
            
            c1, c2, c3 = st.columns(3)
            c1.download_button("Triggers", d1, "Triggers.docx")
            c2.download_button("Skybox", d2, "Skybox.docx")
            c3.download_button("Characters", d3, "Characters.docx")
