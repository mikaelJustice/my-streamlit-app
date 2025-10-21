import streamlit as st

# MUST BE FIRST!
st.set_page_config(
    page_title="IGCSE Question Bank Pro", 
    page_icon="🎓", 
    layout="wide",
    initial_sidebar_state="auto"
)

import pdfplumber
import re
import tempfile
import os
import pickle
import base64
from io import BytesIO
from collections import defaultdict
from learning_engine import extract_text_from_pdf, auto_learn_from_document, parse_csv_topics, learn_from_questions

st.markdown("""
<style>
    .main-header { font-size: 2.8rem; color: #1f77b4; text-align: center; margin-bottom: 1rem; font-weight: bold; }
    .question-container { background: white; padding: 1.5rem; border-radius: 10px; margin: 1rem 0; border-left: 5px solid #1f77b4; box-shadow: 0 2px 8px rgba(0,0,0,0.1); overflow-wrap: break-word; word-wrap: break-word; color: #000; }
    .multiple-choice { background: #f0f8ff; padding: 1.5rem; border-radius: 10px; margin: 1rem 0; border-left: 5px solid #4CAF50; overflow-wrap: break-word; color: #000; }
    .file-header { color: #e63946; margin-top: 2rem; padding-bottom: 0.5rem; border-bottom: 3px solid #e63946; font-size: 1.5rem; word-wrap: break-word; }
    .admin-section { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem; }
    .keyword-highlight { background-color: #ffeb3b; padding: 2px 4px; border-radius: 3px; font-weight: bold; }
    .diagram-box { background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #ffc107; overflow-x: auto; }
    .diagram-box img { max-width: 100%; height: auto; display: block; margin: 10px auto; }
    .subject-badge { display: inline-block; padding: 5px 12px; border-radius: 15px; font-size: 12px; font-weight: bold; margin: 5px; }
    .physics { background: #e3f2fd; color: #1565c0; }
    .chemistry { background: #f3e5f5; color: #6a1b9a; }
    .biology { background: #e8f5e9; color: #2e7d32; }
    .math { background: #fff3e0; color: #e65100; }
    .geography { background: #fce4ec; color: #c2185b; }
    .smart-search { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 1rem; border-radius: 10px; margin: 1rem 0; }
    
    @media screen and (max-width: 768px) {
        .main-header { font-size: 2rem; padding: 0.5rem; }
        .question-container, .multiple-choice { padding: 1rem; margin: 0.5rem 0; font-size: 14px; }
        .stButton > button { min-height: 44px; font-size: 16px; padding: 12px 20px; width: 100%; }
        .stTextInput > div > div > input { font-size: 16px !important; padding: 12px; }
    }
    
    @media screen and (max-width: 480px) {
        .main-header { font-size: 1.5rem; }
        .question-container, .multiple-choice { padding: 0.8rem; font-size: 13px; }
        .subject-badge { font-size: 9px; padding: 3px 6px; }
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "question_database.pkl"
TOPICS_FILE = "learned_topics.pkl"
ADMIN_PASSWORD = "admin123"

TOPIC_KEYWORDS = {
    "algebra": ["equation", "solve", "variable", "expression", "simplify", "expand", "factorise", "quadratic", "linear"],
    "geometry": ["angle", "triangle", "circle", "polygon", "area", "perimeter", "volume", "pythagoras"],
    "photosynthesis": ["photosynthesis", "chlorophyll", "glucose", "carbon dioxide", "oxygen"],
    "electricity": ["current", "voltage", "resistance", "circuit", "ohm", "power"],
    "cells": ["cell", "nucleus", "cytoplasm", "membrane", "mitochondria"],
    "bonding": ["ionic", "covalent", "metallic", "bond", "molecule"],
}

def load_database():
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'rb') as f:
                return pickle.load(f)
    except:
        pass
    return {}

def save_database(data):
    try:
        with open(DB_FILE, 'wb') as f:
            pickle.dump(data, f)
        return True
    except:
        return False

def load_learned_topics():
    try:
        if os.path.exists(TOPICS_FILE):
            with open(TOPICS_FILE, 'rb') as f:
                return pickle.load(f)
    except:
        pass
    return {}

def save_learned_topics(topics):
    try:
        with open(TOPICS_FILE, 'wb') as f:
            pickle.dump(topics, f)
        return True
    except:
        return False

def detect_subject(filename):
    subject_codes = {
        '0580': ('Mathematics', 'math'),
        '0460': ('Geography', 'geography'),
        '0625': ('Physics', 'physics'),
        '0610': ('Biology', 'biology'),
        '0620': ('Chemistry', 'chemistry'),
    }
    for code, (name, css) in subject_codes.items():
        if code in filename:
            return name, css
    return 'General', 'general'

def smart_topic_match(query, question_text, learned_topics):
    query_lower = query.lower()
    text_lower = question_text.lower()
    if query_lower in text_lower:
        return True
    all_topics = {**TOPIC_KEYWORDS, **learned_topics}
    for topic, keywords in all_topics.items():
        if query_lower in topic.lower():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return True
    return False

def bytes_to_base64(file_bytes):
    return base64.b64encode(file_bytes).decode('utf-8')

def base64_to_bytes(base64_str):
    return base64.b64decode(base64_str.encode('utf-8'))

def highlight_keyword(text, keyword):
    if not keyword or not text:
        return text
    try:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        return pattern.sub(lambda x: f'<span class="keyword-highlight">{x.group()}</span>', text)
    except:
        return text

def should_exclude_line(line):
    if not line or len(line.strip()) < 3:
        return True
    exclude_patterns = [r'DO NOT WRITE', r'TURN OVER', r'© UCLES', r'NIGRAM SIHT', r'ETIRW TON']
    for pattern in exclude_patterns:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False

def extract_questions_robust(file_bytes, filename, debug_mode=False):
    questions = []
    debug_info = []
    subject, subject_css = detect_subject(filename)
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        with pdfplumber.open(tmp_path) as pdf:
            debug_info.append(f"📄 {len(pdf.pages)} pages | {subject}")
            
            for page_num, page in enumerate(pdf.pages, 1):
                raw_text = page.extract_text()
                if not raw_text:
                    continue
                
                lines = raw_text.split('\n')
                clean_lines = [re.sub(r'\(cid:\d+\)', '', line.strip()) 
                             for line in lines 
                             if line.strip() and not should_exclude_line(line.strip())]
                page_text = '\n'.join(clean_lines)
                
                page_images = []
                try:
                    if page.images:
                        for img_obj in page.images:
                            try:
                                bbox = (img_obj['x0'], img_obj['top'], img_obj['x1'], img_obj['bottom'])
                                cropped = page.crop(bbox)
                                img = cropped.to_image(resolution=150)
                                img_buffer = BytesIO()
                                img.original.save(img_buffer, format='PNG')
                                img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
                                page_images.append(img_base64)
                            except:
                                continue
                except:
                    pass
                
                all_matches = []
                patterns = [
                    r'(?:^|\n)(\d+)\s+([A-Z])',
                    r'(?:^|\n)(\d+)[.\)]\s+',
                    r'(?:^|\n)\(([a-z]|i{1,3})\)\s+'
                ]
                
                for pattern in patterns:
                    matches = list(re.finditer(pattern, page_text, re.MULTILINE))
                    all_matches.extend(matches)
                
                all_matches.sort(key=lambda x: x.start())
                
                for i, match in enumerate(all_matches):
                    q_id = match.group(1) if match.lastindex >= 1 else str(i+1)
                    start = match.start()
                    end = all_matches[i+1].start() if i+1 < len(all_matches) else len(page_text)
                    
                    question_text = page_text[start:end].strip()
                    
                    if len(question_text) < 15:
                        continue
                    
                    is_mcq = bool(re.search(r'\b[A-D][.\)]\s+[A-Za-z]', question_text))
                    has_diagram = bool(re.search(r'\bFig\.?\s*\d+|\bdiagram\b', question_text, re.IGNORECASE))
                    
                    questions.append({
                        'text': question_text,
                        'page': page_num,
                        'source': filename,
                        'order': len(questions) + 1,
                        'question_number': q_id,
                        'type': "Multiple Choice" if is_mcq else "Standard",
                        'images': page_images.copy(),
                        'subject': subject,
                        'subject_css': subject_css,
                        'has_diagram_ref': has_diagram,
                        'suggested_topics': []
                    })
        
        os.unlink(tmp_path)
        debug_info.append(f"✅ {len(questions)} questions")
        return questions, debug_info
        
    except Exception as e:
        debug_info.append(f"❌ ERROR: {str(e)}")
        return [], debug_info

def format_question_display(question, keyword, display_index):
    text = question.get('text', '')
    highlighted = highlight_keyword(text, keyword)
    subject = question.get('subject', 'General')
    subject_css = question.get('subject_css', 'general')
    
    css_class = "multiple-choice" if question.get('type') == "Multiple Choice" else "question-container"
    icon = "✅" if question.get('type') == "Multiple Choice" else "📝"
    
    html = f"""
    <div class="{css_class}">
        <div>
            <strong>{icon} Q{question.get('question_number', display_index)} (Page {question.get('page', '?')})</strong>
            <span class="subject-badge {subject_css}">{subject}</span>
        </div>
        <br>
        <div style="white-space: pre-wrap; font-family: Arial, sans-serif; line-height: 1.6; font-size: 14px;">
        {highlighted}
        </div>
    """
    
    if question.get('images'):
        html += '<div class="diagram-box">📊 <strong>Diagram:</strong><br>'
        for img_data in question['images'][:2]:
            if img_data and len(img_data) > 100:
                html += f'<img src="data:image/png;base64,{img_data}" style="max-width: 100%;"><br>'
        html += '</div>'
    elif question.get('has_diagram_ref'):
        html += f'''<div style="background: #ffebee; padding: 10px; border-radius: 5px; margin: 10px 0;">
        ⚠️ <strong>Diagram Reference:</strong> {question.get('source', 'Unknown')}, Page {question.get('page', '?')}
        </div>'''
    
    html += "</div>"
    return html

# Session state
if 'database_initialized' not in st.session_state:
    st.session_state.all_papers_data = load_database()
    st.session_state.learned_topics = load_learned_topics()
    st.session_state.database_initialized = True
    st.session_state.admin_logged_in = False

# END OF PART 1
# Continue with PART 2...
# PART 2 - ADD THIS RIGHT AFTER PART 1

show_admin = st.sidebar.checkbox("🔧 Admin Panel")

if show_admin:
    if not st.session_state.admin_logged_in:
        st.markdown('<div class="admin-section">', unsafe_allow_html=True)
        st.markdown('<h2 style="color: white; text-align: center;">🔐 Admin Login</h2>', unsafe_allow_html=True)
        password = st.text_input("Password:", type="password")
        
        if st.button("Login", use_container_width=True):
            if password == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("Wrong password!")
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()
    
    # ADMIN MODE
    st.markdown('<h1 class="main-header">🔧 Admin Panel</h1>', unsafe_allow_html=True)
    
    if st.button("🚪 Logout"):
        st.session_state.admin_logged_in = False
        st.rerun()
    
    # CSV Import
    with st.expander("📊 Import Topics (CSV)"):
        st.code("differentiation, derivative, gradient\nphotosynthesis, chlorophyll, glucose")
        csv_input = st.text_area("Paste CSV:", height=150)
        if st.button("📥 Import"):
            if csv_input:
                topics = parse_csv_topics(csv_input)
                for topic, keywords in topics.items():
                    st.session_state.learned_topics[topic] = keywords
                save_learned_topics(st.session_state.learned_topics)
                st.success(f"✅ Imported {len(topics)} topics!")
    
    # Upload Papers
    st.markdown("### 📚 Upload Question Papers")
    files = st.file_uploader("Upload PDFs", type="pdf", accept_multiple_files=True)
    
    if files and st.button("🚀 Process Papers", type="primary"):
        for file in files:
            st.write(f"Processing: {file.name}")
            file_bytes = file.getvalue()
            questions, debug_info = extract_questions_robust(file_bytes, file.name, False)
            
            st.session_state.all_papers_data[file.name] = {
                'bytes_base64': bytes_to_base64(file_bytes),
                'questions': questions
            }
            st.success(f"✅ {len(questions)} questions")
        
        save_database(st.session_state.all_papers_data)
        st.balloons()
    
    # Database Overview
    if st.session_state.all_papers_data:
        st.markdown("### 📚 Database")
        for name, data in st.session_state.all_papers_data.items():
            col1, col2, col3 = st.columns([5, 2, 1])
            with col1:
                q_count = len(data.get('questions', []))
                st.write(f"**{name}** - {q_count} questions")
            with col2:
                if st.button("🔄", key=f"proc_{name}"):
                    fb = base64_to_bytes(data['bytes_base64'])
                    questions, _ = extract_questions_robust(fb, name, False)
                    data['questions'] = questions
                    save_database(st.session_state.all_papers_data)
                    st.rerun()
            with col3:
                if st.button("🗑️", key=f"del_{name}"):
                    del st.session_state.all_papers_data[name]
                    save_database(st.session_state.all_papers_data)
                    st.rerun()

else:
    # USER MODE - MOBILE OPTIMIZED
    st.markdown('<h1 class="main-header">🎓 IGCSE Question Bank</h1>', unsafe_allow_html=True)
    st.markdown('<div class="smart-search">', unsafe_allow_html=True)
    st.markdown("### 🧠 Smart Search")
    st.markdown("Find questions by topic")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.session_state.all_papers_data = load_database()
    st.session_state.learned_topics = load_learned_topics()
    
    if not st.session_state.all_papers_data:
        st.info("📚 No papers uploaded yet.")
        st.stop()
    
    ready_papers = {n: d for n, d in st.session_state.all_papers_data.items() if d.get('questions')}
    
    if not ready_papers:
        st.warning("⏳ Processing...")
        st.stop()
    
    # Stats
    total_q = sum(len(d.get('questions', [])) for d in ready_papers.values())
    subjects = set()
    for d in ready_papers.values():
        for q in d.get('questions', []):
            subjects.add(q.get('subject', 'General'))
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📚 Papers", len(ready_papers))
    with col2:
        st.metric("❓ Questions", total_q)
    with col3:
        st.metric("📖 Subjects", len(subjects))
    
    # Quick Topics
    st.markdown("### 💡 Quick Search")
    sample_topics = ["algebra", "photosynthesis", "electricity", "bonding"]
    cols = st.columns(4)
    for i, topic in enumerate(sample_topics):
        with cols[i]:
            if st.button(topic, key=f"topic_{topic}", use_container_width=True):
                st.session_state.quick_search = topic
    
    # Search
    keyword = st.text_input(
        "🔍 Search:",
        placeholder="e.g., quadratic, photosynthesis...",
        value=st.session_state.get('quick_search', '')
    )
    
    search = st.button("🔍 Search", type="primary", use_container_width=True)
    
    if 'quick_search' in st.session_state:
        del st.session_state.quick_search
    
    if search and keyword:
        matches = []
        
        with st.spinner("Searching..."):
            for paper_name, paper_data in ready_papers.items():
                for q in paper_data.get('questions', []):
                    if smart_topic_match(keyword, q.get('text', ''), st.session_state.learned_topics):
                        matches.append(q)
        
        if matches:
            matches.sort(key=lambda x: (x.get('source', ''), x.get('order', 0)))
            st.success(f"🎉 {len(matches)} questions found!")
            
            # Group by subject
            by_subject = defaultdict(lambda: defaultdict(list))
            for q in matches:
                subj = q.get('subject', 'General')
                src = q.get('source', 'Unknown')
                by_subject[subj][src].append(q)
            
            # Display
            for subject in sorted(by_subject.keys()):
                st.markdown(f'<h2 style="color: #1f77b4; border-bottom: 2px solid #1f77b4; padding: 8px 0;">📚 {subject}</h2>', unsafe_allow_html=True)
                
                for paper_name in sorted(by_subject[subject].keys()):
                    questions = by_subject[subject][paper_name]
                    
                    # Truncate long filenames
                    display_name = paper_name if len(paper_name) <= 40 else paper_name[:37] + "..."
                    
                    with st.expander(f"📄 {display_name} ({len(questions)} Q)", expanded=False):
                        for i, q in enumerate(questions, 1):
                            html = format_question_display(q, keyword, i)
                            st.markdown(html, unsafe_allow_html=True)
                            if i < len(questions):
                                st.markdown("---")
        else:
            st.warning(f"No questions found for '{keyword}'")
    
    elif search:
        st.warning("Please enter a search term!")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 10px;'>
    <p><strong>🎓 IGCSE Question Bank Pro v4.2</strong></p>
    <p>Mobile-Optimized • AI-Powered • Multi-Subject</p>
</div>
""", unsafe_allow_html=True)
