import streamlit as st
import pdfplumber
import re
import tempfile
import os
import pickle
import base64

st.set_page_config(page_title="IGCSE Smart Question Bank", page_icon="🔍", layout="wide")

st.markdown("""
<style>
    .main-header { font-size: 2.8rem; color: #1f77b4; text-align: center; margin-bottom: 1rem; font-weight: bold; }
    .clean-question { background: white; padding: 1.5rem; border-radius: 10px; margin: 1rem 0; border-left: 5px solid #28a745; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    .multiple-choice { background: #e8f5e8; padding: 1.5rem; border-radius: 10px; margin: 1rem 0; border-left: 5px solid #4CAF50; }
    .file-header { color: #e63946; margin-top: 2rem; padding-bottom: 0.5rem; border-bottom: 3px solid #e63946; font-size: 1.5rem; }
    .admin-section { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem; }
    .user-section { background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%); color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem; }
    .diagram-indicator { background: #fff3cd; padding: 0.5rem 1rem; border-radius: 5px; margin: 0.5rem 0; border-left: 4px solid #ffc107; }
    .keyword-highlight { background-color: #ffeb3b; padding: 2px 4px; border-radius: 3px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# SHARED DATABASE SYSTEM
DB_FILE = "question_database.pkl"
ADMIN_PASSWORD = "admin123"

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

def clean_text(text):
    """Remove garbage characters and clean up text"""
    if not text:
        return ""
    
    # Remove common PDF garbage patterns
    garbage_patterns = [
        r'\(cid:\d+\)',  # (cid:xxx) patterns
        r'© UCLES \d+',  # Copyright notices
        r'\[Turn over\]',  # Page turn indicators
        r'NIGRAM SIHT NI ETIRW TON OD',  # Reverse text garbage
        r'DO NOT WRITE IN THIS MARGIN',  # Margin text
        r'DO NOT WRITE ABOVE THIS LINE',
        r'0610/\d+/[A-Z]/[M|O|N]/\d+',  # Paper codes
    ]
    
    for pattern in garbage_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Remove excessive whitespace but preserve paragraph structure
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    
    return text.strip()

def extract_intelligent_questions(file_bytes, filename):
    """Intelligent question extraction that identifies complete questions"""
    all_questions = []
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        with pdfplumber.open(tmp_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text with better layout preservation
                text = page.extract_text() or ""
                if not text:
                    continue
                
                # Clean the text
                clean_page_text = clean_text(text)
                
                # Check for diagrams
                has_diagram = bool(page.images)
                
                # INTELLIGENT QUESTION DETECTION
                
                # Method 1: Split by clear question numbers (1., 2., 3., etc.)
                question_splits = re.split(r'(\b\d+[\.\)]\s+)', clean_page_text)
                
                for i in range(1, len(question_splits), 2):
                    if i + 1 < len(question_splits):
                        question_number = question_splits[i].strip()
                        question_content = question_splits[i + 1]
                        
                        # Find the end of this question (next question number or reasonable boundary)
                        full_question = question_number + " " + question_content
                        
                        # Look for natural question endings
                        question_endings = [
                            r'\b\d+[\.\)]\s+',  # Next question
                            r'© UCLES',         # Copyright
                            r'\[Turn over\]',   # Page turn
                        ]
                        
                        # Try to find a clean ending point
                        for ending_pattern in question_endings:
                            match = re.search(ending_pattern, full_question)
                            if match:
                                full_question = full_question[:match.start()].strip()
                                break
                        
                        # Clean and validate the question
                        clean_question = clean_text(full_question)
                        
                        if is_valid_question(clean_question):
                            question_data = create_question_data(
                                clean_question, page_num, filename, has_diagram, clean_page_text
                            )
                            if question_data:
                                all_questions.append(question_data)
                
                # Method 2: Capture multiple choice blocks specifically
                mcq_blocks = re.findall(
                    r'(\b\d+[\.\)]\s+.*?(?:\s*[A-D][\.\)].*?)+)(?=\b\d+[\.\)]|$)',
                    clean_page_text, re.DOTALL | re.IGNORECASE
                )
                
                for mcq_block in mcq_blocks:
                    clean_mcq = clean_text(mcq_block)
                    if is_valid_question(clean_mcq):
                        question_data = create_question_data(
                            clean_mcq, page_num, filename, has_diagram, clean_page_text, "Multiple Choice"
                        )
                        if question_data and not any(q['text'] == question_data['text'] for q in all_questions):
                            all_questions.append(question_data)
        
        os.unlink(tmp_path)
        
        # Remove duplicates and ensure quality
        return deduplicate_questions(all_questions)
        
    except Exception as e:
        st.error(f"Error processing {filename}: {str(e)}")
        return []

def is_valid_question(text):
    """Check if text represents a valid question"""
    if not text or len(text) < 25:
        return False
    
    # Must contain question indicators
    question_indicators = [
        r'\b\d+[\.\)]\s+',  # Numbered
        r'[A-D][\.\)]\s+',  # Multiple choice options
        r'\?',              # Question mark
        r'explain', r'state', r'describe', r'calculate',  # Question verbs
    ]
    
    has_indicator = any(re.search(indicator, text, re.IGNORECASE) for indicator in question_indicators)
    
    # Must NOT contain garbage
    garbage_indicators = [
        r'\(cid:\d+\)',
        r'DO NOT WRITE',
        r'NIGRAM SIHT',
        r'© UCLES \d+',
    ]
    
    has_garbage = any(re.search(garbage, text, re.IGNORECASE) for garbage in garbage_indicators)
    
    return has_indicator and not has_garbage and len(text) > 25

def create_question_data(question_text, page_num, filename, has_diagram, full_page_text, question_type=None):
    """Create structured question data"""
    if not question_type:
        if re.search(r'[A-D][\.\)]\s+', question_text, re.MULTILINE):
            question_type = "Multiple Choice"
        else:
            question_type = "Standard"
    
    # Extract question number
    qnum_match = re.match(r'(\b\d+)[\.\)]\s+', question_text)
    question_number = qnum_match.group(1) if qnum_match else "1"
    
    return {
        'text': question_text,
        'clean_text': clean_text(question_text),  # Always include clean_text
        'page': page_num,
        'source': filename,
        'type': question_type,
        'has_diagram': has_diagram,
        'full_page_content': full_page_text,
        'question_context': question_text,
        'original_structure': question_text,
        'question_number': question_number
    }

def deduplicate_questions(questions):
    """Remove duplicate questions while preserving quality"""
    seen = set()
    unique_questions = []
    
    for q in questions:
        # Create a signature based on clean content
        signature = f"{clean_text(q['text'])[:200]}_{q['page']}_{q['source']}"
        
        if signature not in seen and is_valid_question(q['text']):
            seen.add(signature)
            unique_questions.append(q)
    
    return unique_questions

def safe_get(question, field, default=""):
    """Safely get a field from question dictionary"""
    return question.get(field, default)

def format_question_display(question, keyword, question_index):
    """Format question for clean display"""
    question_text = safe_get(question, 'clean_text', safe_get(question, 'text', ''))
    highlighted_text = highlight_keyword(question_text, keyword)
    
    # Determine styling
    if safe_get(question, 'type') == "Multiple Choice":
        css_class = "multiple-choice"
        type_icon = "✅"
    else:
        css_class = "clean-question"
        type_icon = "📝"
    
    # Build display
    display_html = f"""
    <div class="{css_class}">
        <strong>{type_icon} Question {question_index} (Page {safe_get(question, 'page', 'N/A')})</strong>
        {'' if not safe_get(question, 'has_diagram') else ' • 🖼️ <em>Contains diagrams</em>'}<br><br>
        <div style="white-space: pre-wrap; font-family: Arial, sans-serif; line-height: 1.6; font-size: 14px;">
        {highlighted_text}
        </div>
    </div>
    """
    
    return display_html

# Initialize session state
if 'database_initialized' not in st.session_state:
    st.session_state.all_papers_data = load_database()
    st.session_state.database_initialized = True
    st.session_state.admin_logged_in = False

# Check admin access
show_admin_login = st.sidebar.checkbox("🔧 Access Admin Panel")

if show_admin_login:
    if not st.session_state.admin_logged_in:
        st.markdown("""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem; border-radius: 10px; margin: 2rem auto; max-width: 500px;'>
            <h2 style="text-align: center; color: white;">🔧 Admin Login</h2>
        """, unsafe_allow_html=True)
        
        password = st.text_input("Enter Admin Password:", type="password", key="admin_password")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🚀 Login", use_container_width=True):
                if password == ADMIN_PASSWORD:
                    st.session_state.admin_logged_in = True
                    st.success("✅ Admin access granted!")
                    st.rerun()
                else:
                    st.error("❌ Invalid password!")
        
        with col2:
            if st.button("👤 Back to User", use_container_width=True):
                st.session_state.admin_logged_in = False
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.stop()
    
    # ADMIN PANEL
    st.markdown('<h1 class="main-header">🔧 IGCSE Admin - Intelligent</h1>', unsafe_allow_html=True)
    st.markdown('<div class="admin-section">', unsafe_allow_html=True)
    st.header("Smart Question Extraction")
    st.markdown("Intelligent detection of complete questions only")
    st.markdown('</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🚪 Logout Admin"):
            st.session_state.admin_logged_in = False
            st.rerun()
    
    st.success("**🤖 INTELLIGENT EXTRACTION** - Filters garbage, preserves complete questions")
    
    admin_files = st.file_uploader("Upload PDF question papers", type="pdf", accept_multiple_files=True, key="admin_upload")
    
    if admin_files:
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🚀 Process Intelligently", type="primary", use_container_width=True):
                with st.spinner("Processing with intelligent question detection..."):
                    for uploaded_file in admin_files:
                        file_bytes = uploaded_file.getvalue()
                        st.session_state.all_papers_data[uploaded_file.name] = {
                            'bytes_base64': bytes_to_base64(file_bytes),
                            'questions': []
                        }
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ Added {len(admin_files)} papers with SMART extraction!")
                        st.balloons()
        with col2:
            if st.button("🔄 Reprocess All", type="secondary", use_container_width=True):
                with st.spinner("Reprocessing ALL with intelligent filtering..."):
                    for paper_name, paper_data in st.session_state.all_papers_data.items():
                        file_bytes = base64_to_bytes(paper_data['bytes_base64'])
                        paper_data['questions'] = extract_intelligent_questions(file_bytes, paper_name)
                    if save_database(st.session_state.all_papers_data):
                        st.success("✅ ALL papers reprocessed with intelligent filtering!")
    
    if st.session_state.all_papers_data:
        st.markdown("### 📋 Paper Database - CLEAN QUESTIONS")
        
        for paper_name, paper_data in st.session_state.all_papers_data.items():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.write(f"**{paper_name}**")
                if paper_data['questions']:
                    diagrams_count = sum(1 for q in paper_data['questions'] if safe_get(q, 'has_diagram', False))
                    # SAFELY get sample question
                    sample_text = safe_get(paper_data['questions'][0], 'clean_text', safe_get(paper_data['questions'][0], 'text', 'No sample available'))
                    sample_preview = sample_text[:150] + "..." if len(sample_text) > 150 else sample_text
                    st.write(f"Clean Questions: {len(paper_data['questions'])} | Diagrams: {diagrams_count}")
                    st.caption(f"Sample: {sample_preview}")
                else:
                    st.write("Not processed yet")
            with col2:
                if st.button(f"🔄 Process", key=f"process_{paper_name}"):
                    with st.spinner(f"Intelligent processing {paper_name}..."):
                        file_bytes = base64_to_bytes(paper_data['bytes_base64'])
                        paper_data['questions'] = extract_intelligent_questions(file_bytes, paper_name)
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ {paper_name} processed intelligently!")
            with col3:
                if st.button(f"🗑️ Remove", key=f"remove_{paper_name}"):
                    del st.session_state.all_papers_data[paper_name]
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ {paper_name} removed!")
                        st.rerun()
            with col4:
                if paper_data['questions']:
                    st.write(f"✅ Clean")
                else:
                    st.write("❌ Needs processing")
    
    else:
        st.info("👆 Upload PDF papers for intelligent question extraction")

else:
    # USER PANEL - INTELLIGENT SEARCH
    st.markdown('<h1 class="main-header">📚 IGCSE Smart Question Bank</h1>', unsafe_allow_html=True)
    st.markdown('<div class="user-section">', unsafe_allow_html=True)
    st.header("Intelligent Search - Clean Questions Only")
    st.markdown("No garbage text • Complete questions • Smart filtering")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Load database
    latest_data = load_database()
    if latest_data != st.session_state.all_papers_data:
        st.session_state.all_papers_data = latest_data
    
    if st.session_state.all_papers_data:
        ready_papers = {name: data for name, data in st.session_state.all_papers_data.items() if data['questions']}
        
        if ready_papers:
            st.success(f"📚 {len(ready_papers)} papers available with CLEAN questions")
            
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                keyword = st.text_input(
                    "🔍 Enter topic or keyword:",
                    placeholder="e.g., photosynthesis, titration, diagram...",
                    help="Intelligent search across clean question content"
                )
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                search_clicked = st.button("🚀 Smart Search", type="primary", use_container_width=True)
            
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                show_diagrams = st.checkbox("Diagram Questions", value=True)
            
            if search_clicked and keyword:
                all_matching_questions = []
                
                for paper_name, paper_data in ready_papers.items():
                    for question in paper_data['questions']:
                        # Clean search in clean text
                        search_text = safe_get(question, 'clean_text', safe_get(question, 'text', '')).lower()
                        keyword_lower = keyword.lower()
                        
                        text_match = keyword_lower in search_text
                        diagram_match = any(diagram_word in keyword_lower for diagram_word in 
                                          ['diagram', 'graph', 'chart', 'figure', 'image', 'fig']) 
                        if diagram_match:
                            diagram_match = diagram_match and safe_get(question, 'has_diagram', False)
                        
                        if text_match or (show_diagrams and diagram_match):
                            question['search_keyword'] = keyword
                            if diagram_match:
                                question['match_type'] = 'diagram'
                            else:
                                question['match_type'] = 'direct'
                            all_matching_questions.append(question)
                
                if all_matching_questions:
                    st.success(f"🎉 Found {len(all_matching_questions)} CLEAN questions!")
                    
                    # Group by paper
                    questions_by_paper = {}
                    for q in all_matching_questions:
                        source = safe_get(q, 'source', 'Unknown')
                        if source not in questions_by_paper:
                            questions_by_paper[source] = []
                        questions_by_paper[source].append(q)
                    
                    for paper_name, paper_questions in questions_by_paper.items():
                        st.markdown(f'<h3 class="file-header">📄 {paper_name} ({len(paper_questions)} clean questions)</h3>', unsafe_allow_html=True)
                        
                        for i, question in enumerate(paper_questions, 1):
                            display_html = format_question_display(question, keyword, i)
                            st.markdown(display_html, unsafe_allow_html=True)
                
                else:
                    st.warning(f"🔍 No clean questions found containing '{keyword}'")
                    st.info("💡 Try: photosynthesis, respiration, mitosis, DNA, ecosystem")
            
            elif search_clicked and not keyword:
                st.warning("⚠️ Please enter a search keyword first!")
        
        else:
            st.info("📚 Papers are being processed with intelligent extraction...")
    
    else:
        st.info("📚 No papers available yet. Admin will upload papers.")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>IGCSE Smart Question Bank • Intelligent Extraction • Clean Questions • No Garbage Text</p>
</div>
""", unsafe_allow_html=True)
