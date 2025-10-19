import streamlit as st
import pdfplumber
import re
import tempfile
import os
import pickle
import base64

st.set_page_config(page_title="IGCSE Question Bank", page_icon="🔍", layout="wide")

st.markdown("""
<style>
    .main-header { font-size: 2.8rem; color: #1f77b4; text-align: center; margin-bottom: 1rem; font-weight: bold; }
    .question-container { background: white; padding: 1.5rem; border-radius: 10px; margin: 1rem 0; border-left: 5px solid #1f77b4; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    .multiple-choice { background: #f0f8ff; padding: 1.5rem; border-radius: 10px; margin: 1rem 0; border-left: 5px solid #4CAF50; }
    .file-header { color: #e63946; margin-top: 2rem; padding-bottom: 0.5rem; border-bottom: 3px solid #e63946; font-size: 1.5rem; }
    .admin-section { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem; }
    .user-section { background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%); color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem; }
    .diagram-indicator { background: #fff3cd; padding: 0.5rem 1rem; border-radius: 5px; margin: 0.5rem 0; border-left: 4px solid #ffc107; }
    .keyword-highlight { background-color: #ffeb3b; padding: 2px 4px; border-radius: 3px; font-weight: bold; }
    .question-number { color: #1f77b4; font-weight: bold; font-size: 1.1em; }
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
        r'\(cid:\d+\)',
        r'© UCLES \d+',
        r'\[Turn over\]',
        r'NIGRAM SIHT NI ETIRW TON OD',
        r'DO NOT WRITE IN THIS MARGIN',
        r'DO NOT WRITE ABOVE THIS LINE',
        r'0610/\d+/[A-Z]/[M|O|N]/\d+',
    ]
    
    for pattern in garbage_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Clean up whitespace but preserve structure
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    
    return text.strip()

def extract_proper_questions(file_bytes, filename):
    """Proper question extraction that handles both structured and multiple choice questions"""
    all_questions = []
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        with pdfplumber.open(tmp_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text with proper layout
                text = page.extract_text() or ""
                if not text:
                    continue
                
                # Clean the text
                clean_text_content = clean_text(text)
                
                # Check for diagrams
                has_diagram = bool(page.images)
                
                # METHOD 1: Extract numbered questions (1., 2., 3., etc.)
                numbered_questions = extract_numbered_questions(clean_text_content, page_num, filename, has_diagram)
                all_questions.extend(numbered_questions)
                
                # METHOD 2: Extract multiple choice questions specifically
                mcq_questions = extract_multiple_choice_questions(clean_text_content, page_num, filename, has_diagram)
                all_questions.extend(mcq_questions)
                
                # METHOD 3: Extract "Question X" format
                question_format = extract_question_format(clean_text_content, page_num, filename, has_diagram)
                all_questions.extend(question_format)
        
        os.unlink(tmp_path)
        
        # Remove duplicates
        return remove_duplicate_questions(all_questions)
        
    except Exception as e:
        st.error(f"Error processing {filename}: {str(e)}")
        return []

def extract_numbered_questions(text, page_num, filename, has_diagram):
    """Extract questions that start with numbers like 1., 2., 3."""
    questions = []
    
    # Find all question numbers
    question_starts = list(re.finditer(r'\b(\d+)[\.\)]\s+', text))
    
    for i, match in enumerate(question_starts):
        question_num = match.group(1)
        start_pos = match.start()
        
        # Find the end of this question (next question or end of text)
        if i + 1 < len(question_starts):
            end_pos = question_starts[i + 1].start()
        else:
            end_pos = len(text)
        
        question_text = text[start_pos:end_pos].strip()
        
        if is_valid_question(question_text):
            questions.append(create_question_data(
                question_text, page_num, filename, has_diagram, text, "Multiple Choice" if has_multiple_choice(question_text) else "Standard"
            ))
    
    return questions

def extract_multiple_choice_questions(text, page_num, filename, has_diagram):
    """Specifically extract multiple choice questions"""
    questions = []
    
    # Pattern for MCQs: question followed by A., B., C., D. options
    mcq_pattern = r'(\b\d+[\.\)]\s+.*?)(?=\b\d+[\.\)]|$)'
    matches = re.finditer(mcq_pattern, text, re.DOTALL)
    
    for match in matches:
        question_text = match.group(1).strip()
        
        # Check if this looks like a multiple choice question
        if has_multiple_choice(question_text) and is_valid_question(question_text):
            questions.append(create_question_data(
                question_text, page_num, filename, has_diagram, text, "Multiple Choice"
            ))
    
    return questions

def extract_question_format(text, page_num, filename, has_diagram):
    """Extract questions in 'Question X' format"""
    questions = []
    
    question_pattern = r'(Question\s+\d+.*?)(?=Question\s+\d+|\d+[\.\)]|$)'
    matches = re.finditer(question_pattern, text, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        question_text = match.group(1).strip()
        
        if is_valid_question(question_text):
            questions.append(create_question_data(
                question_text, page_num, filename, has_diagram, text, "Multiple Choice" if has_multiple_choice(question_text) else "Standard"
            ))
    
    return questions

def has_multiple_choice(text):
    """Check if text contains multiple choice options"""
    return bool(re.search(r'[A-D][\.\)]\s+', text))

def is_valid_question(text):
    """Check if this is a valid question (not garbage)"""
    if not text or len(text) < 25:
        return False
    
    # Must have question indicators
    has_indicators = any([
        re.search(r'\b\d+[\.\)]\s+', text),
        re.search(r'Question\s+\d+', text, re.IGNORECASE),
        re.search(r'\?', text),
        re.search(r'[A-D][\.\)]\s+', text),
    ])
    
    # Must NOT have garbage
    no_garbage = not any([
        re.search(r'\(cid:\d+\)', text),
        re.search(r'DO NOT WRITE', text, re.IGNORECASE),
        re.search(r'NIGRAM SIHT', text),
    ])
    
    return has_indicators and no_garbage

def create_question_data(question_text, page_num, filename, has_diagram, full_text, question_type):
    """Create structured question data"""
    # Extract question number
    qnum_match = re.match(r'(\b\d+)[\.\)]\s+', question_text) or re.match(r'Question\s+(\d+)', question_text, re.IGNORECASE)
    question_number = qnum_match.group(1) if qnum_match else "1"
    
    return {
        'text': question_text,
        'clean_text': clean_text(question_text),
        'page': page_num,
        'source': filename,
        'type': question_type,
        'has_diagram': has_diagram,
        'question_number': question_number
    }

def remove_duplicate_questions(questions):
    """Remove duplicate questions"""
    seen = set()
    unique = []
    
    for q in questions:
        signature = f"{q['clean_text'][:100]}_{q['page']}"
        if signature not in seen:
            seen.add(signature)
            unique.append(q)
    
    return unique

def format_question_for_display(question, keyword, index):
    """Format question with proper styling"""
    question_text = question.get('clean_text', question.get('text', ''))
    highlighted = highlight_keyword(question_text, keyword)
    
    if question.get('type') == "Multiple Choice":
        css_class = "multiple-choice"
        icon = "✅"
        label = "Multiple Choice"
    else:
        css_class = "question-container"
        icon = "📝"
        label = "Question"
    
    display_html = f"""
    <div class="{css_class}">
        <strong>{icon} {label} {index} (Page {question.get('page', 'N/A')})</strong>
        {'' if not question.get('has_diagram') else '• 🖼️ <em>Contains diagrams</em>'}<br><br>
        <div style="white-space: pre-wrap; font-family: Arial, sans-serif; line-height: 1.6; font-size: 14px;">
        {highlighted}
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
        st.markdown('<div class="admin-section">', unsafe_allow_html=True)
        st.markdown('<h2 style="text-align: center; color: white;">🔧 Admin Login</h2>', unsafe_allow_html=True)
        
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
    st.markdown('<h1 class="main-header">🔧 IGCSE Question Bank</h1>', unsafe_allow_html=True)
    st.markdown('<div class="admin-section">', unsafe_allow_html=True)
    st.header("Admin Panel - Proper Question Extraction")
    st.markdown("Extracts both structured and multiple choice questions")
    st.markdown('</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🚪 Logout Admin"):
            st.session_state.admin_logged_in = False
            st.rerun()
    
    st.info("**🔧 PROCESSING:** Proper question extraction with multiple choice support")
    
    admin_files = st.file_uploader("Upload PDF question papers", type="pdf", accept_multiple_files=True, key="admin_upload")
    
    if admin_files:
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🚀 Process Papers", type="primary", use_container_width=True):
                with st.spinner("Processing with proper question extraction..."):
                    for uploaded_file in admin_files:
                        file_bytes = uploaded_file.getvalue()
                        st.session_state.all_papers_data[uploaded_file.name] = {
                            'bytes_base64': bytes_to_base64(file_bytes),
                            'questions': []
                        }
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ Added {len(admin_files)} papers!")
                        st.balloons()
        with col2:
            if st.button("🔄 Reprocess All", type="secondary", use_container_width=True):
                with st.spinner("Reprocessing all papers..."):
                    for paper_name, paper_data in st.session_state.all_papers_data.items():
                        file_bytes = base64_to_bytes(paper_data['bytes_base64'])
                        paper_data['questions'] = extract_proper_questions(file_bytes, paper_name)
                    if save_database(st.session_state.all_papers_data):
                        st.success("✅ All papers reprocessed!")
    
    if st.session_state.all_papers_data:
        st.markdown("### 📋 Paper Database")
        
        for paper_name, paper_data in st.session_state.all_papers_data.items():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.write(f"**{paper_name}**")
                if paper_data['questions']:
                    mcq_count = sum(1 for q in paper_data['questions'] if q.get('type') == "Multiple Choice")
                    diagrams_count = sum(1 for q in paper_data['questions'] if q.get('has_diagram', False))
                    st.write(f"Questions: {len(paper_data['questions'])} | MCQ: {mcq_count} | Diagrams: {diagrams_count}")
                else:
                    st.write("Not processed yet")
            with col2:
                if st.button(f"🔄 Process", key=f"process_{paper_name}"):
                    with st.spinner(f"Processing {paper_name}..."):
                        file_bytes = base64_to_bytes(paper_data['bytes_base64'])
                        paper_data['questions'] = extract_proper_questions(file_bytes, paper_name)
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ {paper_name} processed!")
            with col3:
                if st.button(f"🗑️ Remove", key=f"remove_{paper_name}"):
                    del st.session_state.all_papers_data[paper_name]
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ {paper_name} removed!")
                        st.rerun()
            with col4:
                if paper_data['questions']:
                    st.write(f"✅ Ready")
                else:
                    st.write("❌ Needs processing")
    
    else:
        st.info("👆 Upload PDF papers to build your database")

else:
    # USER PANEL
    st.markdown('<h1 class="main-header">📚 IGCSE Question Bank</h1>', unsafe_allow_html=True)
    st.markdown('<div class="user-section">', unsafe_allow_html=True)
    st.header("Search Portal - Complete Questions")
    st.markdown("Find questions across all uploaded papers")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Load database
    latest_data = load_database()
    if latest_data != st.session_state.all_papers_data:
        st.session_state.all_papers_data = latest_data
    
    if st.session_state.all_papers_data:
        ready_papers = {name: data for name, data in st.session_state.all_papers_data.items() if data['questions']}
        
        if ready_papers:
            st.success(f"📚 {len(ready_papers)} papers available")
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                keyword = st.text_input(
                    "🔍 Enter topic or keyword:",
                    placeholder="e.g., plants, photosynthesis, diagram...",
                    help="Search across all question papers"
                )
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                search_clicked = st.button("🚀 Search", type="primary", use_container_width=True)
            
            if search_clicked and keyword:
                all_matching_questions = []
                
                for paper_name, paper_data in ready_papers.items():
                    for question in paper_data['questions']:
                        search_text = question.get('clean_text', question.get('text', '')).lower()
                        if keyword.lower() in search_text:
                            question['search_keyword'] = keyword
                            all_matching_questions.append(question)
                
                if all_matching_questions:
                    st.success(f"🎉 Found {len(all_matching_questions)} questions!")
                    
                    # Group by paper
                    questions_by_paper = {}
                    for q in all_matching_questions:
                        source = q.get('source', 'Unknown')
                        if source not in questions_by_paper:
                            questions_by_paper[source] = []
                        questions_by_paper[source].append(q)
                    
                    for paper_name, paper_questions in questions_by_paper.items():
                        st.markdown(f'<h3 class="file-header">📄 {paper_name} ({len(paper_questions)} questions)</h3>', unsafe_allow_html=True)
                        
                        for i, question in enumerate(paper_questions, 1):
                            display_html = format_question_for_display(question, keyword, i)
                            st.markdown(display_html, unsafe_allow_html=True)
                
                else:
                    st.warning(f"🔍 No questions found containing '{keyword}'")
            
            elif search_clicked and not keyword:
                st.warning("⚠️ Please enter a search keyword first!")
        
        else:
            st.info("📚 Papers are being processed...")
    
    else:
        st.info("📚 No papers available yet. Admin will upload papers.")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>IGCSE Question Bank • Complete Questions • Multiple Choice Support • Clean Formatting</p>
</div>
""", unsafe_allow_html=True)
