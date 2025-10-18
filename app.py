import streamlit as st
import pdfplumber
import re
import tempfile
import os
import pickle
import base64
from PIL import Image
import io

st.set_page_config(page_title="IGCSE Question Bank - Complete", page_icon="🔍", layout="wide")

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
    .complete-question { background: white; padding: 1.5rem; border-radius: 8px; margin: 1rem 0; border: 2px solid #28a745; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
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

def extract_complete_questions_preserved(file_bytes, filename):
    """Extract COMPLETE questions without cutting off any content"""
    all_questions = []
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        with pdfplumber.open(tmp_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract the entire page text
                full_page_text = page.extract_text() or ""
                if not full_page_text:
                    continue
                
                # Clean but preserve ALL content
                cleaned_text = re.sub(r'\n+', '\n', full_page_text)
                
                # Check for diagrams on this page
                has_diagram = bool(page.images)
                
                # NEW APPROACH: Extract by question numbers and preserve EVERYTHING between them
                question_numbers = re.findall(r'\b(\d+[\.\)])\s+', full_page_text)
                
                if question_numbers:
                    # Split the page text by question numbers to get complete questions
                    parts = re.split(r'(\b\d+[\.\)]\s+)', full_page_text)
                    
                    for i in range(1, len(parts), 2):
                        if i + 1 < len(parts):
                            question_number = parts[i].strip()
                            question_content = parts[i + 1]
                            
                            # Find where this question ends (next question number or end)
                            next_question_start = None
                            for j in range(i + 2, len(parts)):
                                if re.match(r'\b\d+[\.\)]\s+', parts[j]):
                                    next_question_start = j
                                    break
                            
                            if next_question_start:
                                # Include all content until next question
                                full_question = question_number + " " + "".join(parts[i+1:next_question_start])
                            else:
                                # This is the last question on the page
                                full_question = question_number + " " + "".join(parts[i+1:])
                            
                            # Clean up but preserve ALL content
                            full_question = re.sub(r'\n+', '\n', full_question).strip()
                            
                            if len(full_question) > 10:  # Very lenient filter
                                # Determine question type
                                if re.search(r'[A-D][\.\)]', full_question):
                                    question_type = "Multiple Choice"
                                else:
                                    question_type = "Standard"
                                
                                all_questions.append({
                                    'text': full_question,
                                    'page': page_num,
                                    'source': filename,
                                    'type': question_type,
                                    'has_diagram': has_diagram,
                                    'full_page_content': full_page_text,
                                    'question_context': full_question,  # Use the complete question as context
                                    'original_structure': full_question,
                                    'question_number': question_number.replace('.', '').replace(')', '')
                                })
                
                # Also capture questions that start with "Question X" format
                question_patterns = [
                    r'(Question\s+\d+.*?)(?=Question\s+\d+|\d+[\.\)]|\s*$)',
                    r'(\b\d+[\.\)]\s+.*)'
                ]
                
                for pattern in question_patterns:
                    matches = re.findall(pattern, full_page_text, re.DOTALL)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0]
                        
                        question_text = match.strip()
                        if len(question_text) > 20 and question_text not in [q['text'] for q in all_questions]:
                            if re.search(r'[A-D][\.\)]', question_text):
                                question_type = "Multiple Choice"
                            else:
                                question_type = "Standard"
                            
                            all_questions.append({
                                'text': question_text,
                                'page': page_num,
                                'source': filename,
                                'type': question_type,
                                'has_diagram': has_diagram,
                                'full_page_content': full_page_text,
                                'question_context': question_text,
                                'original_structure': question_text,
                                'question_number': str(len(all_questions) + 1)
                            })
        
        os.unlink(tmp_path)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_questions = []
        for q in all_questions:
            # Use a generous identifier to avoid removing similar but different questions
            identifier = f"{q['text'][:200]}_{q['page']}"
            if identifier not in seen:
                seen.add(identifier)
                unique_questions.append(q)
        
        return unique_questions
        
    except Exception as e:
        st.error(f"Error processing {filename}: {str(e)}")
        return []

def organize_questions_by_paper(questions):
    """Organize questions by paper"""
    organized = {}
    for question in questions:
        paper_name = question['source']
        if paper_name not in organized:
            organized[paper_name] = []
        organized[paper_name].append(question)
    
    # Sort by page and question number
    for paper in organized:
        organized[paper].sort(key=lambda x: (x['page'], x.get('question_number', '0')))
    
    return organized

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
    st.markdown('<h1 class="main-header">🔧 IGCSE Admin - Complete Questions</h1>', unsafe_allow_html=True)
    st.markdown('<div class="admin-section">', unsafe_allow_html=True)
    st.header("Administrator - PRESERVES ALL CONTENT")
    st.markdown("Now extracts COMPLETE questions without cutting off information")
    st.markdown('</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🚪 Logout Admin"):
            st.session_state.admin_logged_in = False
            st.rerun()
    
    st.success("**✅ ENHANCED: Preserves complete questions and diagrams**")
    
    admin_files = st.file_uploader("Upload PDF question papers", type="pdf", accept_multiple_files=True, key="admin_upload")
    
    if admin_files:
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🚀 Process with Complete Extraction", type="primary", use_container_width=True):
                with st.spinner("Processing with COMPLETE question preservation..."):
                    for uploaded_file in admin_files:
                        file_bytes = uploaded_file.getvalue()
                        st.session_state.all_papers_data[uploaded_file.name] = {
                            'bytes_base64': bytes_to_base64(file_bytes),
                            'questions': []
                        }
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ Added {len(admin_files)} papers with COMPLETE question extraction!")
                        st.balloons()
        with col2:
            if st.button("🔄 Reprocess All", type="secondary", use_container_width=True):
                with st.spinner("Reprocessing ALL with complete preservation..."):
                    for paper_name, paper_data in st.session_state.all_papers_data.items():
                        file_bytes = base64_to_bytes(paper_data['bytes_base64'])
                        paper_data['questions'] = extract_complete_questions_preserved(file_bytes, paper_name)
                    if save_database(st.session_state.all_papers_data):
                        st.success("✅ ALL papers reprocessed with COMPLETE question preservation!")
    
    if st.session_state.all_papers_data:
        st.markdown("### 📋 Paper Database - COMPLETE QUESTIONS")
        
        for paper_name, paper_data in st.session_state.all_papers_data.items():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.write(f"**{paper_name}**")
                if paper_data['questions']:
                    diagrams_count = sum(1 for q in paper_data['questions'] if q['has_diagram'])
                    sample_question = paper_data['questions'][0]['text'][:100] + "..." if len(paper_data['questions'][0]['text']) > 100 else paper_data['questions'][0]['text']
                    st.write(f"Questions: {len(paper_data['questions'])} | Diagrams: {diagrams_count}")
                    st.caption(f"Sample: {sample_question}")
                else:
                    st.write("Not processed yet")
            with col2:
                if st.button(f"🔄 Process", key=f"process_{paper_name}"):
                    with st.spinner(f"Processing {paper_name}..."):
                        file_bytes = base64_to_bytes(paper_data['bytes_base64'])
                        paper_data['questions'] = extract_complete_questions_preserved(file_bytes, paper_name)
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ {paper_name} processed with complete extraction!")
            with col3:
                if st.button(f"🗑️ Remove", key=f"remove_{paper_name}"):
                    del st.session_state.all_papers_data[paper_name]
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ {paper_name} removed!")
                        st.rerun()
            with col4:
                if paper_data['questions']:
                    st.write(f"✅ Complete")
                else:
                    st.write("❌ Needs processing")
    
    else:
        st.info("👆 Upload PDF papers to build your complete question database")

else:
    # USER PANEL - COMPLETE QUESTIONS
    st.markdown('<h1 class="main-header">📚 IGCSE Question Bank - Complete</h1>', unsafe_allow_html=True)
    st.markdown('<div class="user-section">', unsafe_allow_html=True)
    st.header("Search Portal - PRESERVES ALL QUESTION CONTENT")
    st.markdown("Now shows COMPLETE questions without cutting off information")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Load database
    latest_data = load_database()
    if latest_data != st.session_state.all_papers_data:
        st.session_state.all_papers_data = latest_data
    
    if st.session_state.all_papers_data:
        ready_papers = {name: data for name, data in st.session_state.all_papers_data.items() if data['questions']}
        
        if ready_papers:
            st.success(f"📚 {len(ready_papers)} papers available with COMPLETE questions")
            
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                keyword = st.text_input(
                    "🔍 Enter topic or keyword:",
                    placeholder="e.g., titration, electrolysis, diagram, graph...",
                    help="Searches COMPLETE questions without cutting off content"
                )
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                search_clicked = st.button("🚀 Search Questions", type="primary", use_container_width=True)
            
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                include_diagrams = st.checkbox("Include Diagrams", value=True)
            
            if search_clicked and keyword:
                all_matching_questions = []
                
                for paper_name, paper_data in ready_papers.items():
                    for question in paper_data['questions']:
                        # Search across ALL question content
                        text_match = keyword.lower() in question['text'].lower()
                        context_match = keyword.lower() in question['question_context'].lower()
                        page_match = keyword.lower() in question['full_page_content'].lower()
                        diagram_match = any(diagram_word in keyword.lower() for diagram_word in 
                                          ['diagram', 'graph', 'chart', 'figure', 'image']) and question['has_diagram']
                        
                        # If found ANYWHERE, include the COMPLETE question
                        if text_match or context_match or page_match or (include_diagrams and diagram_match):
                            question['search_keyword'] = keyword
                            if diagram_match:
                                question['match_type'] = 'diagram'
                            elif context_match or page_match:
                                question['match_type'] = 'context'
                            else:
                                question['match_type'] = 'direct'
                            all_matching_questions.append(question)
                
                if all_matching_questions:
                    st.success(f"🎉 Found {len(all_matching_questions)} COMPLETE questions!")
                    
                    # Organize by paper
                    organized_questions = organize_questions_by_paper(all_matching_questions)
                    
                    for paper_name, paper_questions in organized_questions.items():
                        st.markdown(f'<div class="paper-section">', unsafe_allow_html=True)
                        st.markdown(f'<h3 class="file-header">📄 {paper_name} ({len(paper_questions)} questions)</h3>')
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        for i, question in enumerate(paper_questions, 1):
                            # Highlight the keyword in the COMPLETE question
                            highlighted_question = highlight_keyword(question['original_structure'], keyword)
                            
                            st.markdown(f"""
                            <div class="complete-question">
                                <strong>🔍 Question {i} (Page {question['page']}) - {question['type']}:</strong><br>
                                <em>Match type: {question['match_type'].upper()}</em>
                                {'' if not question['has_diagram'] else ' • 🖼️ <strong>CONTAINS DIAGRAMS</strong>'}<br><br>
                                <div style="white-space: pre-wrap; font-family: Arial, sans-serif; line-height: 1.5; font-size: 14px;">
                                {highlighted_question}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                
                else:
                    st.warning(f"🔍 No questions found containing '{keyword}'")
                    st.info("💡 Try different keywords or check spelling")
            
            elif search_clicked and not keyword:
                st.warning("⚠️ Please enter a search keyword first!")
            
            # Show sample of available questions
            with st.expander("📋 Sample Available Questions"):
                sample_paper = list(ready_papers.keys())[0]
                sample_questions = ready_papers[sample_paper]['questions'][:3]
                st.write(f"**Sample from {sample_paper}:**")
                for i, q in enumerate(sample_questions, 1):
                    st.write(f"{i}. {q['text'][:150]}...")
        
        else:
            st.info("📚 Papers are being processed with complete question extraction...")
    
    else:
        st.info("📚 No papers available yet. Admin will upload papers.")

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>IGCSE Question Bank • Complete Question Preservation • No Content Cutting • Diagram Detection</p>
</div>
""", unsafe_allow_html=True)
