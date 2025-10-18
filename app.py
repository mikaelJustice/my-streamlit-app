import streamlit as st
import pdfplumber
import re
import tempfile
import os
import pickle
import base64

st.set_page_config(page_title="IGCSE Question Bank v3", page_icon="🔍", layout="wide")

st.markdown("""
<style>
    .main-header { font-size: 2.8rem; color: #1f77b4; text-align: center; margin-bottom: 1rem; font-weight: bold; }
    .question-box { background-color: #f8f9fa; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem; border-left: 5px solid #1f77b4; }
    .multiple-choice { background-color: #e8f4fd; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; border-left: 4px solid #4CAF50; }
    .file-header { color: #e63946; margin-top: 2rem; padding-bottom: 0.5rem; border-bottom: 3px solid #e63946; font-size: 1.5rem; }
    .admin-section { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem; }
    .user-section { background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%); color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem; }
    .diagram-found { background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%); padding: 1rem; border-radius: 8px; margin: 0.5rem 0; border-left: 4px solid #ff6b6b; }
    .full-question { background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); padding: 1.5rem; border-radius: 10px; margin: 1rem 0; border: 2px solid #667eea; }
    .login-section { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem; border-radius: 10px; margin: 2rem auto; max-width: 500px; }
    .keyword-highlight { background-color: #ffeb3b; padding: 2px 4px; border-radius: 3px; font-weight: bold; }
    .paper-section { background: linear-gradient(135deg, #ffd89b 0%, #19547b 100%); color: white; padding: 1rem; border-radius: 8px; margin: 1rem 0; }
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
    if not keyword:
        return text
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return pattern.sub(lambda x: f'<span class="keyword-highlight">{x.group()}</span>', text)

# Initialize session state
if 'database_initialized' not in st.session_state:
    st.session_state.all_papers_data = load_database()
    st.session_state.database_initialized = True
    st.session_state.admin_logged_in = False

def extract_complete_questions_with_context(file_bytes, filename):
    """Enhanced extraction that captures complete questions with full context"""
    all_questions = []
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        with pdfplumber.open(tmp_path) as pdf:
            full_text = ""
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                full_text += f"\n--- Page {page_num} ---\n{page_text}"
                
                # Check for diagrams
                has_diagram = bool(page.images)
                
                # Enhanced question patterns
                patterns = [
                    # Complete numbered questions
                    r'(\b\d+[\.\)]\s+.*?)(?=\b\d+[\.\)]|\bQuestion\s+\d+|\s*[A-Z][a-z]{2,}\s|\s*$)',
                    # Multiple choice blocks
                    r'([A-D][\.\)]\s+.*?(?:\s+[A-D][\.\)]\s+.*?)*)(?=\s*\d+[\.\)]|\s*$)',
                    # Question format
                    r'(Question\s+\d+.*?)(?=Question\s+\d+|\d+[\.\)]|\s*$)'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, page_text, re.DOTALL | re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0]
                        
                        question_text = match.strip()
                        
                        if (len(question_text) > 25 and 
                            not any(header in question_text.lower() for header in 
                                   ['page', 'copyright', 'instruction', 'total', 'mark', 'blank'])):
                            
                            # Determine question type
                            if re.search(r'^[A-D][\.\)]', question_text, re.MULTILINE):
                                question_type = "Multiple Choice"
                            else:
                                question_type = "Standard"
                            
                            # Get broader context
                            context = get_question_context(question_text, page_text)
                            
                            all_questions.append({
                                'text': question_text,
                                'page': page_num,
                                'source': filename,
                                'type': question_type,
                                'has_diagram': has_diagram,
                                'full_page_content': page_text,
                                'question_context': context,
                                'original_structure': question_text
                            })
        
        os.unlink(tmp_path)
        
        # Remove duplicates
        seen = set()
        unique_questions = []
        for q in all_questions:
            identifier = f"{q['text'][:150]}_{q['page']}"
            if identifier not in seen:
                seen.add(identifier)
                unique_questions.append(q)
        
        return unique_questions
        
    except Exception as e:
        st.error(f"Error processing {filename}: {str(e)}")
        return []

def get_question_context(question_text, page_text):
    """Get broader context around the question"""
    start_idx = page_text.find(question_text)
    if start_idx == -1:
        return question_text
    
    context_start = max(0, start_idx - 150)
    context_end = min(len(page_text), start_idx + len(question_text) + 300)
    
    context = page_text[context_start:context_end]
    return re.sub(r'\s+', ' ', context).strip()

# Check admin access
show_admin_login = st.sidebar.checkbox("🔧 Access Admin Panel")

if show_admin_login:
    if not st.session_state.admin_logged_in:
        st.markdown('<div class="login-section">', unsafe_allow_html=True)
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
    st.markdown('<h1 class="main-header">🔧 IGCSE Admin Panel v3</h1>', unsafe_allow_html=True)
    st.markdown('<div class="admin-section">', unsafe_allow_html=True)
    st.header("Administrator Control Center - ENHANCED VERSION")
    st.markdown("Complete question extraction with diagrams and context")
    st.markdown('</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🚪 Logout Admin"):
            st.session_state.admin_logged_in = False
            st.rerun()
    
    st.info("**🔑 ADMIN PANEL v3 ACTIVE** - Enhanced question extraction")
    
    admin_files = st.file_uploader("Upload PDF question papers", type="pdf", accept_multiple_files=True, key="admin_upload")
    
    if admin_files:
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🚀 Process and Add Papers", type="primary", use_container_width=True):
                with st.spinner("Processing with ENHANCED extraction..."):
                    for uploaded_file in admin_files:
                        file_bytes = uploaded_file.getvalue()
                        st.session_state.all_papers_data[uploaded_file.name] = {
                            'bytes_base64': bytes_to_base64(file_bytes),
                            'questions': []
                        }
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ Added {len(admin_files)} papers with ENHANCED extraction!")
                        st.balloons()
        with col2:
            if st.button("🔄 Reprocess All", type="secondary", use_container_width=True):
                with st.spinner("Reprocessing ALL papers..."):
                    for paper_name, paper_data in st.session_state.all_papers_data.items():
                        file_bytes = base64_to_bytes(paper_data['bytes_base64'])
                        paper_data['questions'] = extract_complete_questions_with_context(file_bytes, paper_name)
                    if save_database(st.session_state.all_papers_data):
                        st.success("✅ ALL papers reprocessed with enhanced extraction!")
    
    if st.session_state.all_papers_data:
        st.markdown("### 📋 Paper Database - ENHANCED VERSION")
        
        for paper_name, paper_data in st.session_state.all_papers_data.items():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.write(f"**{paper_name}**")
                if paper_data['questions']:
                    diagrams_count = sum(1 for q in paper_data['questions'] if q['has_diagram'])
                    st.write(f"Questions: {len(paper_data['questions'])} | Diagrams: {diagrams_count}")
                else:
                    st.write("Not processed yet")
            with col2:
                if st.button(f"🔄 Process", key=f"process_{paper_name}"):
                    with st.spinner(f"Processing {paper_name}..."):
                        file_bytes = base64_to_bytes(paper_data['bytes_base64'])
                        paper_data['questions'] = extract_complete_questions_with_context(file_bytes, paper_name)
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ {paper_name} processed with enhanced extraction!")
            with col3:
                if st.button(f"🗑️ Remove", key=f"remove_{paper_name}"):
                    del st.session_state.all_papers_data[paper_name]
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ {paper_name} removed!")
                        st.rerun()
            with col4:
                if paper_data['questions']:
                    st.write(f"✅ Enhanced")
                else:
                    st.write("❌ Needs processing")
    
    else:
        st.info("👆 Upload PDF papers to build your enhanced database")

else:
    # USER PANEL - ENHANCED VERSION
    st.markdown('<h1 class="main-header">📚 IGCSE Question Bank v3</h1>', unsafe_allow_html=True)
    st.markdown('<div class="user-section">', unsafe_allow_html=True)
    st.header("ENHANCED Search Portal - Complete Questions & Diagrams")
    st.markdown("Now with full question context and diagram detection")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Load database
    latest_data = load_database()
    if latest_data != st.session_state.all_papers_data:
        st.session_state.all_papers_data = latest_data
    
    if st.session_state.all_papers_data:
        ready_papers = {name: data for name, data in st.session_state.all_papers_data.items() if data['questions']}
        
        if ready_papers:
            st.success(f"📚 {len(ready_papers)} papers available with ENHANCED extraction")
            
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                keyword = st.text_input(
                    "🔍 Enter topic or keyword:",
                    placeholder="e.g., algebra, photosynthesis, diagram, graph, circuit...",
                    help="ENHANCED: Searches complete questions and context"
                )
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                search_clicked = st.button("🚀 Search Questions", type="primary", use_container_width=True)
            
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                include_diagrams = st.checkbox("Include Diagrams", value=True)
            
            with col4:
                st.markdown("<br>", unsafe_allow_html=True)
                show_full_context = st.checkbox("Full Context", value=True)
            
            if search_clicked and keyword:
                all_matching_questions = []
                
                for paper_name, paper_data in ready_papers.items():
                    for question in paper_data['questions']:
                        # Enhanced search across all content
                        text_match = keyword.lower() in question['text'].lower()
                        context_match = keyword.lower() in question['question_context'].lower()
                        page_match = keyword.lower() in question['full_page_content'].lower()
                        diagram_match = any(diagram_word in keyword.lower() for diagram_word in 
                                          ['diagram', 'graph', 'chart', 'figure']) and question['has_diagram']
                        
                        if text_match or context_match or page_match or (include_diagrams and diagram_match):
                            question['search_keyword'] = keyword
                            if diagram_match:
                                question['match_type'] = 'diagram'
                            elif context_match:
                                question['match_type'] = 'context'
                            else:
                                question['match_type'] = 'direct'
                            all_matching_questions.append(question)
                
                if all_matching_questions:
                    st.success(f"🎉 ENHANCED: Found {len(all_matching_questions)} complete questions!")
                    
                    # Group by paper
                    questions_by_paper = {}
                    for q in all_matching_questions:
                        if q['source'] not in questions_by_paper:
                            questions_by_paper[q['source']] = []
                        questions_by_paper[q['source']].append(q)
                    
                    for paper_name, paper_questions in questions_by_paper.items():
                        st.markdown(f'<div class="paper-section">', unsafe_allow_html=True)
                        st.markdown(f'<h3 class="file-header">📄 {paper_name} ({len(paper_questions)} questions)</h3>')
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        for i, question in enumerate(paper_questions, 1):
                            highlighted_text = highlight_keyword(question['original_structure'], keyword)
                            highlighted_context = highlight_keyword(question['question_context'], keyword)
                            
                            if show_full_context:
                                st.markdown(f"""
                                <div class="full-question">
                                    <strong>🔍 Q{i} (Page {question['page']}) - COMPLETE QUESTION:</strong><br>
                                    <em>Match type: {question['match_type'].upper()}</em><br><br>
                                    <div style="white-space: pre-wrap; background: white; padding: 15px; border-radius: 8px; border: 1px solid #ddd;">
                                    {highlighted_context}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                if question['has_diagram']:
                                    st.markdown(f"""
                                    <div class="diagram-found">
                                        <strong>📊 Q{i} (Page {question['page']}) - DIAGRAM QUESTION:</strong><br>
                                        {highlighted_text}
                                    </div>
                                    """, unsafe_allow_html=True)
                                elif question['type'] == "Multiple Choice":
                                    st.markdown(f"""
                                    <div class="multiple-choice">
                                        <strong>✅ Q{i} (Page {question['page']}) - MULTIPLE CHOICE:</strong><br>
                                        {highlighted_text}
                                    </div>
                                    """, unsafe_allow_html=True)
                                else:
                                    st.markdown(f"""
                                    <div class="question-box">
                                        <strong>📝 Q{i} (Page {question['page']}):</strong><br>
                                        {highlighted_text}
                                    </div>
                                    """, unsafe_allow_html=True)
                            
                            if question['has_diagram']:
                                st.info(f"🖼️ **Contains diagrams on page {question['page']}**")
                
                else:
                    st.warning(f"🔍 No questions found containing '{keyword}'")
            
            elif search_clicked and not keyword:
                st.warning("⚠️ Please enter a search keyword first!")
        
        else:
            st.info("📚 Papers are being processed with enhanced extraction...")
    
    else:
        st.info("📚 No papers available yet. Admin will upload papers.")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>IGCSE Question Bank v3 • Enhanced Complete Question Extraction • Diagram Detection • Organized Papers</p>
</div>
""", unsafe_allow_html=True)
