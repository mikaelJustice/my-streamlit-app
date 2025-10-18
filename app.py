import streamlit as st
import pdfplumber
import re
import tempfile
import os
import json
import pickle
import base64
from PIL import Image
import io

st.set_page_config(page_title="IGCSE Question Bank", page_icon="🔍", layout="wide")

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
    .diagram-image { border: 2px solid #4CAF50; border-radius: 8px; margin: 10px 0; max-width: 100%; }
</style>
""", unsafe_allow_html=True)

# SHARED DATABASE SYSTEM
DB_FILE = "question_database.pkl"
ADMIN_PASSWORD = "admin123"

def load_database():
    """Load the shared database from file"""
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'rb') as f:
                return pickle.load(f)
    except:
        pass
    return {}

def save_database(data):
    """Save the shared database to file"""
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
    """Highlight the keyword in text"""
    if not keyword:
        return text
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return pattern.sub(lambda x: f'<span class="keyword-highlight">{x.group()}</span>', text)

# Initialize or load the shared database
if 'database_initialized' not in st.session_state:
    st.session_state.all_papers_data = load_database()
    st.session_state.database_initialized = True
    st.session_state.admin_logged_in = False

def extract_complete_questions(file_bytes, filename):
    """Extract complete questions with context and diagrams"""
    all_questions = []
    diagram_data = []  # Store diagram information
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        with pdfplumber.open(tmp_path) as pdf:
            full_text_by_page = {}
            
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract full page text for context
                full_text = page.extract_text() or ""
                full_text_by_page[page_num] = full_text
                
                # Extract images/diagrams
                if page.images:
                    for img in page.images:
                        diagram_data.append({
                            'page': page_num,
                            'bbox': (img['x0'], img['top'], img['x1'], img['bottom']),
                            'source': filename
                        })
                
                # Clean the text
                text = re.sub(r'\s+', ' ', full_text)
                
                # Enhanced patterns to capture complete questions
                patterns = [
                    # Numbered questions with broader context
                    r'(\b\d+[\.\)]\s+.*?)(?=\b\d+[\.\)]|\bQuestion\s+\d+|\n\s*[A-Z][a-z]|\s*$)',
                    # Multiple choice with options
                    r'([A-D][\.\)]\s+.*?)(?=[A-D][\.\)]|\d+[\.\)]|\s*$)',
                    # Question format
                    r'(Question\s+\d+.*?)(?=Question\s+\d+|\d+[\.\)]|\s*$)',
                    # Questions ending with question marks (broader capture)
                    r'([A-Z][^\.!?]*\?.*?)(?=[A-Z][^\.!?]*\?|\d+[\.\)]|\s*$)'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0]
                        
                        clean_match = re.sub(r'\s+', ' ', match).strip()
                        
                        # More lenient filtering to capture complete questions
                        if (len(clean_match) > 20 and 
                            not any(header in clean_match.lower() for header in 
                                   ['page', 'copyright', 'instruction', 'total', 'mark', 'blank', 'end of'])):
                            
                            question_type = "Multiple Choice" if re.match(r'^[A-D][\.\)]', clean_match) else "Standard"
                            
                            # Check if this page has diagrams
                            has_diagram = any(d['page'] == page_num for d in diagram_data)
                            
                            # Store the complete question with full context
                            all_questions.append({
                                'text': clean_match,
                                'page': page_num,
                                'source': filename,
                                'type': question_type,
                                'has_diagram': has_diagram,
                                'full_page_content': full_text,  # Store complete page content
                                'question_context': get_question_context(clean_match, full_text)
                            })
        
        os.unlink(tmp_path)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_questions = []
        for q in all_questions:
            # Use a combination of text and page to identify duplicates
            text_hash = hash(q['text'][:150] + str(q['page']))
            if text_hash not in seen:
                seen.add(text_hash)
                unique_questions.append(q)
        
        return unique_questions
        
    except Exception as e:
        st.error(f"Error processing {filename}: {str(e)}")
        return []

def get_question_context(question_text, full_page_text):
    """Get broader context around the question"""
    # Find the question in the full page text
    start_idx = full_page_text.find(question_text)
    if start_idx == -1:
        return question_text
    
    # Extract more context around the question
    context_start = max(0, start_idx - 200)  # 200 chars before
    context_end = min(len(full_page_text), start_idx + len(question_text) + 500)  # 500 chars after
    
    context = full_page_text[context_start:context_end]
    
    # Clean up the context
    context = re.sub(r'\s+', ' ', context).strip()
    
    return context

def extract_diagram_images(file_bytes, filename, page_number):
    """Extract diagram images from specific page"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        with pdfplumber.open(tmp_path) as pdf:
            if page_number <= len(pdf.pages):
                page = pdf.pages[page_number - 1]
                images = []
                
                # Extract images from the page
                for img in page.images:
                    # Crop the image area from the page
                    bbox = (img['x0'], img['top'], img['x1'], img['bottom'])
                    cropped_page = page.crop(bbox)
                    
                    # Convert to image
                    img_obj = cropped_page.to_image()
                    if img_obj:
                        images.append(img_obj)
                
                return images
        os.unlink(tmp_path)
    except Exception as e:
        st.error(f"Error extracting diagrams from {filename} page {page_number}: {str(e)}")
    return []

# Check if user wants to access admin panel
show_admin_login = st.sidebar.checkbox("🔧 Access Admin Panel")

if show_admin_login:
    if not st.session_state.admin_logged_in:
        # Admin Login Section
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
    st.markdown('<h1 class="main-header">🔧 IGCSE Admin Panel</h1>', unsafe_allow_html=True)
    st.markdown('<div class="admin-section">', unsafe_allow_html=True)
    st.header("Administrator Control Center")
    st.markdown("Manage all question papers and system settings")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Admin logout button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🚪 Logout Admin"):
            st.session_state.admin_logged_in = False
            st.rerun()
    
    st.info("**🔑 Admin Access Active** - You are viewing the administrator panel")
    
    # Admin file upload
    admin_files = st.file_uploader("Upload PDF question papers", type="pdf", accept_multiple_files=True, key="admin_upload")
    
    if admin_files:
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🚀 Process and Add Papers", type="primary", use_container_width=True):
                with st.spinner("Processing new papers..."):
                    for uploaded_file in admin_files:
                        file_bytes = uploaded_file.getvalue()
                        st.session_state.all_papers_data[uploaded_file.name] = {
                            'bytes_base64': bytes_to_base64(file_bytes),
                            'questions': []
                        }
                    if save_database(st.session_state.all_papers_data):
                        st.success(f"✅ Added {len(admin_files)} new papers to the SHARED database!")
                        st.balloons()
                    else:
                        st.error("❌ Failed to save to database")
        with col2:
            if st.button("🔄 Reprocess All Papers", type="secondary", use_container_width=True):
                with st.spinner("Reprocessing all papers with enhanced context..."):
                    for paper_name, paper_data in st.session_state.all_papers_data.items():
                        file_bytes = base64_to_bytes(paper_data['bytes_base64'])
                        paper_data['questions'] = extract_complete_questions(file_bytes, paper_name)
                    if save_database(st.session_state.all_papers_data):
                        st.success("✅ All papers reprocessed with enhanced context!")
    
    # Paper management
    if st.session_state.all_papers_data:
        st.markdown("### 📋 Paper Database Management")
        
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
                        paper_data['questions'] = extract_complete_questions(file_bytes, paper_name)
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
        
        # Database summary
        st.markdown("---")
        total_questions = sum(len(data['questions']) for data in st.session_state.all_papers_data.values())
        total_diagrams = sum(sum(1 for q in data['questions'] if q['has_diagram']) for data in st.session_state.all_papers_data.values())
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Papers", len(st.session_state.all_papers_data))
        col2.metric("Total Questions", total_questions)
        col3.metric("Questions with Diagrams", total_diagrams)
        col4.metric("Database Status", "✅ Shared")
    
    else:
        st.info("👆 Upload PDF papers to build your question database")

else:
    # USER PANEL
    st.markdown('<h1 class="main-header">📚 IGCSE Question Bank</h1>', unsafe_allow_html=True)
    st.markdown('<div class="user-section">', unsafe_allow_html=True)
    st.header("Student & Teacher Search Portal")
    st.markdown("Search across all available question papers instantly")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Load the latest database
    latest_data = load_database()
    if latest_data != st.session_state.all_papers_data:
        st.session_state.all_papers_data = latest_data
    
    if st.session_state.all_papers_data:
        ready_papers = {name: data for name, data in st.session_state.all_papers_data.items() if data['questions']}
        unready_papers = {name: data for name, data in st.session_state.all_papers_data.items() if not data['questions']}
        
        if ready_papers:
            st.success(f"📚 {len(ready_papers)} papers available for search")
            
            if unready_papers:
                st.warning(f"⚠️ {len(unready_papers)} papers still processing...")
            
            # Enhanced search interface
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                keyword = st.text_input(
                    "🔍 Enter topic or keyword:",
                    placeholder="e.g., algebra, photosynthesis, diagram, graph, circuit...",
                    help="Search across complete questions and diagrams"
                )
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                search_clicked = st.button("🚀 Search Questions", type="primary", use_container_width=True)
            
            with col3:
                st.markdown("<br>", unsafe_allow_html=True)
                include_diagrams = st.checkbox("Include Diagrams", value=True)
            
            with col4:
                st.markdown("<br>", unsafe_allow_html=True)
                show_full_context = st.checkbox("Full Context", value=True, help="Show complete question context")
            
            # Process search
            if search_clicked and keyword:
                all_matching_questions = []
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                paper_names = list(ready_papers.keys())
                for idx, paper_name in enumerate(paper_names):
                    status_text.text(f"🔍 Searching in: {paper_name}...")
                    
                    paper_data = ready_papers[paper_name]
                    
                    # Enhanced search across multiple fields
                    for question in paper_data['questions']:
                        # Search in question text
                        text_match = keyword.lower() in question['text'].lower()
                        
                        # Search in full context (broader search)
                        context_match = keyword.lower() in question['question_context'].lower()
                        
                        # Search for diagram-related keywords
                        diagram_keywords = ['diagram', 'graph', 'chart', 'figure', 'drawing', 'image', 'picture', 'map', 'circuit']
                        diagram_match = any(diagram_word in keyword.lower() for diagram_word in diagram_keywords) and question['has_diagram']
                        
                        # If keyword found anywhere, include the complete question
                        if text_match or context_match or (include_diagrams and diagram_match):
                            if diagram_match and question['has_diagram']:
                                question['match_reason'] = 'diagram'
                                question['match_type'] = 'diagram_keyword'
                            elif context_match and not text_match:
                                question['match_reason'] = 'related_content'
                                question['match_type'] = 'context'
                            else:
                                question['match_reason'] = 'direct_text'
                                question['match_type'] = 'direct'
                            
                            # Store the keyword for highlighting
                            question['search_keyword'] = keyword
                            all_matching_questions.append(question)
                    
                    progress_bar.progress((idx + 1) / len(paper_names))
                
                progress_bar.empty()
                status_text.empty()
                
                # Display results
                if all_matching_questions:
                    st.success(f"🎉 Found {len(all_matching_questions)} questions matching '{keyword}'!")
                    
                    # Group by paper
                    questions_by_paper = {}
                    for q in all_matching_questions:
                        if q['source'] not in questions_by_paper:
                            questions_by_paper[q['source']] = []
                        questions_by_paper[q['source']].append(q)
                    
                    # Display organized results
                    for paper_name, paper_questions in questions_by_paper.items():
                        st.markdown(f'<h3 class="file-header">📄 {paper_name} ({len(paper_questions)} questions)</h3>', unsafe_allow_html=True)
                        
                        # Sort questions by page number
                        paper_questions.sort(key=lambda x: x['page'])
                        
                        for i, question in enumerate(paper_questions, 1):
                            highlighted_text = highlight_keyword(question['text'], question['search_keyword'])
                            highlighted_context = highlight_keyword(question['question_context'], question['search_keyword'])
                            
                            if show_full_context:
                                # Show COMPLETE QUESTION CONTEXT
                                st.markdown(f"""
                                <div class="full-question">
                                    <strong>🔍 Q{i} (Page {question['page']}) - Complete Question:</strong><br>
                                    <em>Keyword found in: {question['match_type'].upper()}</em><br><br>
                                    {highlighted_context}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Show diagram indicator if available
                                if question['has_diagram']:
                                    st.info(f"📊 **This question contains diagrams/illustrations on page {question['page']}**")
                                
                            else:
                                # Show compact version
                                if question.get('match_reason') == 'diagram':
                                    st.markdown(f"""
                                    <div class="diagram-found">
                                        <strong>🔍 Q{i} (Page {question['page']}) - Diagram Related:</strong><br>
                                        <em>Keyword found in diagram/illustration</em><br>
                                        {highlighted_text}
                                    </div>
                                    """, unsafe_allow_html=True)
                                elif question.get('match_reason') == 'related_content':
                                    st.markdown(f"""
                                    <div class="question-box">
                                        <strong>📖 Q{i} (Page {question['page']}) - Related Content:</strong><br>
                                        <em>Keyword found in related question parts</em><br>
                                        {highlighted_text}
                                    </div>
                                    """, unsafe_allow_html=True)
                                elif question['type'] == "Multiple Choice":
                                    st.markdown(f"""
                                    <div class="multiple-choice">
                                        <strong>✅ Q{i} (Page {question['page']}) - Multiple Choice:</strong><br>
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
                
                else:
                    st.warning(f"🔍 No questions found containing '{keyword}'")
                    st.info("💡 Try different keywords or check the spelling")
            
            elif search_clicked and not keyword:
                st.warning("⚠️ Please enter a search keyword first!")
        
        else:
            st.info("📚 Papers are being processed. Please check back soon.")
    
    else:
        st.info("📚 No papers available yet. The administrator will upload papers soon.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>IGCSE Question Bank • Complete Context Display • Keyword Highlighting • Enhanced Search</p>
</div>
""", unsafe_allow_html=True)
