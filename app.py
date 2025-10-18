import streamlit as st
import pdfplumber
import re
import tempfile
import os

st.set_page_config(page_title="IGCSE Smart Question Bank", page_icon="🔍", layout="wide")

st.markdown("""
<style>
    .main-header { font-size: 2.8rem; color: #1f77b4; text-align: center; margin-bottom: 1rem; font-weight: bold; }
    .question-box { background-color: #f8f9fa; padding: 1.5rem; border-radius: 10px; margin-bottom: 1rem; border-left: 5px solid #1f77b4; }
    .multiple-choice { background-color: #e8f4fd; padding: 1rem; border-radius: 8px; margin: 0.5rem 0; border-left: 4px solid #4CAF50; }
    .file-header { color: #e63946; margin-top: 2rem; padding-bottom: 0.5rem; border-bottom: 3px solid #e63946; font-size: 1.5rem; }
    .admin-section { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem; }
    .user-section { background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%); color: white; padding: 1.5rem; border-radius: 10px; margin-bottom: 2rem; }
    .diagram-found { background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%); padding: 1rem; border-radius: 8px; margin: 0.5rem 0; border-left: 4px solid #ff6b6b; }
</style>
""", unsafe_allow_html=True)

if 'all_papers_data' not in st.session_state:
    st.session_state.all_papers_data = {}

def extract_all_questions(file_bytes, filename):
    all_questions = []
    diagram_pages = []
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        with pdfplumber.open(tmp_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                if page.images:
                    diagram_pages.append(page_num)
                width = page.width
                height = page.height
                cropped_page = page.crop((0, 100, width, height - 100))
                text = cropped_page.extract_text()
                if not text:
                    continue
                text = re.sub(r'\s+', ' ', text)
                patterns = [
                    r'(\b\d+[\.\)]\s+(?:.*?(?=\b\d+[\.\)]|\bQuestion\s+\d+|\n\s*[A-Z][a-z]|\n\s*[A-D]\.|\s*$)))',
                    r'([A-D][\.\)]\s+.*?)(?=[A-D][\.\)]|\d+[\.\)]|\n\s*[A-Z]|\s*$)',
                    r'(Question\s+\d+.*?)(?=Question\s+\d+|\d+[\.\)]|\s*$)'
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0]
                        clean_match = re.sub(r'\s+', ' ', match).strip()
                        if (len(clean_match) > 25 and not any(header in clean_match.lower() for header in ['page', 'copyright', 'instruction', 'total', 'mark', 'blank', 'end'])):
                            question_type = "Multiple Choice" if re.match(r'^[A-D][\.\)]', clean_match) else "Standard"
                            has_diagram = page_num in diagram_pages
                            all_questions.append({
                                'text': clean_match, 'page': page_num, 'source': filename, 'type': question_type,
                                'has_diagram': has_diagram, 'full_page_content': text[:2000]
                            })
        os.unlink(tmp_path)
        seen = set()
        unique_questions = []
        for q in all_questions:
            text_hash = hash(q['text'][:100])
            if text_hash not in seen:
                seen.add(text_hash)
                unique_questions.append(q)
        return unique_questions
    except Exception as e:
        st.error(f"Error processing {filename}: {str(e)}")
        return []

st.markdown('<h1 class="main-header">📚 IGCSE Smart Question Bank</h1>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🎓 User Search Portal", "🔧 Admin Management Panel"])

with tab1:
    st.markdown('<div class="user-section">', unsafe_allow_html=True)
    st.header("🎓 Student & Teacher Search Portal")
    st.markdown("Search across all available question papers instantly")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.session_state.all_papers_data:
        st.success(f"📚 {len(st.session_state.all_papers_data)} papers available in database")
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            keyword = st.text_input("🔍 Enter topic or keyword:", placeholder="e.g., algebra, photosynthesis, diagram, graph, circuit...")
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            search_clicked = st.button("🚀 Search Questions", type="primary", use_container_width=True)
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            include_diagrams = st.checkbox("Include Diagrams", value=True)
        
        if search_clicked and keyword:
            all_matching_questions = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            paper_names = list(st.session_state.all_papers_data.keys())
            for idx, paper_name in enumerate(paper_names):
                status_text.text(f"🔍 Searching in: {paper_name}...")
                paper_data = st.session_state.all_papers_data[paper_name]
                if not paper_data['questions']:
                    with st.spinner(f"Processing {paper_name}..."):
                        paper_data['questions'] = extract_all_questions(paper_data['bytes'], paper_name)
                for question in paper_data['questions']:
                    text_match = keyword.lower() in question['text'].lower()
                    content_match = keyword.lower() in question['full_page_content'].lower()
                    diagram_keywords = ['diagram', 'graph', 'chart', 'figure', 'drawing', 'image', 'picture', 'map', 'circuit']
                    diagram_match = any(diagram_word in keyword.lower() for diagram_word in diagram_keywords) and question['has_diagram']
                    if text_match or content_match or (include_diagrams and diagram_match):
                        if diagram_match and question['has_diagram']:
                            question['match_reason'] = 'diagram'
                        elif content_match and not text_match:
                            question['match_reason'] = 'related_content'
                        else:
                            question['match_reason'] = 'direct_text'
                        all_matching_questions.append(question)
                progress_bar.progress((idx + 1) / len(paper_names))
            progress_bar.empty()
            status_text.empty()
            
            if all_matching_questions:
                st.success(f"🎉 Found {len(all_matching_questions)} questions matching '{keyword}'!")
                questions_by_paper = {}
                for q in all_matching_questions:
                    if q['source'] not in questions_by_paper:
                        questions_by_paper[q['source']] = []
                    questions_by_paper[q['source']].append(q)
                for paper_name, paper_questions in questions_by_paper.items():
                    st.markdown(f'<h3 class="file-header">📄 {paper_name} ({len(paper_questions)} questions)</h3>', unsafe_allow_html=True)
                    paper_questions.sort(key=lambda x: x['page'])
                    for i, question in enumerate(paper_questions, 1):
                        if question.get('match_reason') == 'diagram':
                            st.markdown(f"""<div class="diagram-found"><strong>🔍 Q{i} (Page {question['page']}) - Diagram Related:</strong><br><em>Keyword found in diagram/illustration</em><br>{question['text']}</div>""", unsafe_allow_html=True)
                        elif question.get('match_reason') == 'related_content':
                            st.markdown(f"""<div class="question-box"><strong>📖 Q{i} (Page {question['page']}) - Related Content:</strong><br><em>Keyword found in related question parts</em><br>{question['text']}</div>""", unsafe_allow_html=True)
                        elif question['type'] == "Multiple Choice":
                            st.markdown(f"""<div class="multiple-choice"><strong>✅ Q{i} (Page {question['page']}) - Multiple Choice:</strong><br>{question['text']}</div>""", unsafe_allow_html=True)
                        else:
                            st.markdown(f"""<div class="question-box"><strong>📝 Q{i} (Page {question['page']}):</strong><br>{question['text']}</div>""", unsafe_allow_html=True)
            else:
                st.warning(f"🔍 No questions found containing '{keyword}'")
        elif search_clicked and not keyword:
            st.warning("⚠️ Please enter a search keyword first!")
    else:
        st.info("📚 No papers available yet. Ask admin to upload papers in the Admin Panel.")

with tab2:
    st.markdown('<div class="admin-section">', unsafe_allow_html=True)
    st.header("🔧 Admin Management Panel")
    st.markdown("Upload and manage question papers for the entire system")
    st.markdown('</div>', unsafe_allow_html=True)
    
    admin_files = st.file_uploader("Upload PDF question papers", type="pdf", accept_multiple_files=True, key="admin_upload")
    
    if admin_files:
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🚀 Process and Add Papers", type="primary", use_container_width=True):
                with st.spinner("Processing new papers..."):
                    for uploaded_file in admin_files:
                        file_bytes = uploaded_file.getvalue()
                        st.session_state.all_papers_data[uploaded_file.name] = {'bytes': file_bytes, 'questions': []}
                st.success(f"✅ Added {len(admin_files)} new papers to the database!")
                st.balloons()
        with col2:
            if st.button("🔄 Reprocess All Papers", type="secondary", use_container_width=True):
                with st.spinner("Reprocessing all papers..."):
                    for paper_name, paper_data in st.session_state.all_papers_data.items():
                        paper_data['questions'] = extract_all_questions(paper_data['bytes'], paper_name)
                st.success("✅ All papers reprocessed!")
    
    if st.session_state.all_papers_data:
        st.markdown("### 📋 Current Paper Database")
        for paper_name, paper_data in st.session_state.all_papers_data.items():
            col1, col2, col3 = st.columns([3, 1, 1])
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
                        paper_data['questions'] = extract_all_questions(paper_data['bytes'], paper_name)
                    st.success(f"✅ {paper_name} processed!")
            with col3:
                if st.button(f"🗑️ Remove", key=f"remove_{paper_name}"):
                    del st.session_state.all_papers_data[paper_name]
                    st.success(f"✅ {paper_name} removed!")
                    st.rerun()
    else:
        st.info("👆 Upload PDF papers to build your question database")

st.markdown("---")
st.markdown("<div style='text-align: center; color: #666;'><p>IGCSE Smart Question Bank • Separate Admin/User Panels • Enhanced Diagram Search</p></div>", unsafe_allow_html=True)
