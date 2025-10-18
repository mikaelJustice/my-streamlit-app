import streamlit as st
import pdfplumber
import re
import tempfile
import os
import base64

# Configure the app
st.set_page_config(
    page_title="IGCSE Question Bank",
    page_icon="🔍",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.8rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
        font-weight: bold;
    }
    .question-box {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 5px solid #1f77b4;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        font-family: 'Arial', sans-serif;
    }
    .multiple-choice {
        background-color: #e8f4fd;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid #4CAF50;
    }
    .file-header {
        color: #e63946;
        margin-top: 2rem;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #e63946;
        font-size: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Main title
st.markdown('<h1 class="main-header">📚 IGCSE Question Bank</h1>', unsafe_allow_html=True)
st.markdown("### Teacher's Portal - Upload Papers Once, Students Search Anytime")

# Initialize session state for stored papers
if 'uploaded_papers' not in st.session_state:
    st.session_state.uploaded_papers = {}

# Teacher section for uploading papers
with st.sidebar:
    st.header("👨‍🏫 Teacher Portal")
    st.markdown("---")
    
    st.subheader("Upload Question Papers")
    teacher_files = st.file_uploader(
        "Upload PDF question papers",
        type="pdf",
        accept_multiple_files=True,
        key="teacher_upload"
    )
    
    if teacher_files:
        if st.button("📥 Process and Store Papers", type="primary"):
            with st.spinner("Processing papers..."):
                for uploaded_file in teacher_files:
                    # Store file in session state
                    file_bytes = uploaded_file.getvalue()
                    st.session_state.uploaded_papers[uploaded_file.name] = {
                        'bytes': file_bytes,
                        'questions': []
                    }
            
            st.success(f"✅ Processed {len(teacher_files)} papers! Students can now search.")

# Enhanced question extraction function
def extract_all_questions(file_bytes, filename):
    all_questions = []
    
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        with pdfplumber.open(tmp_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text with better bounding box to avoid headers/footers
                width = page.width
                height = page.height
                
                # Define crop areas to exclude headers and footers
                header_crop = 100  # pixels from top
                footer_crop = 100  # pixels from bottom
                
                cropped_page = page.crop((0, header_crop, width, height - footer_crop))
                text = cropped_page.extract_text()
                
                if not text:
                    continue
                
                # Clean the text
                text = re.sub(r'\n+', '\n', text)
                text = re.sub(r'\s+', ' ', text)
                
                # Enhanced patterns for different question types
                
                # Pattern 1: Numbered questions (1., 2), etc.)
                numbered_pattern = r'(\b\d+[\.\)]\s+(?:.*?(?=\b\d+[\.\)]|\bQuestion\s+\d+|\n\s*[A-Z][a-z]|\n\s*[A-D]\.|\s*$)))'
                
                # Pattern 2: Multiple choice questions (A., B), etc.)
                mcq_pattern = r'([A-D][\.\)]\s+.*?)(?=[A-D][\.\)]|\d+[\.\)]|\n\s*[A-Z]|\s*$)'
                
                # Pattern 3: "Question X" format
                question_pattern = r'(Question\s+\d+.*?)(?=Question\s+\d+|\d+[\.\)]|\s*$)'
                
                # Combine all patterns
                all_patterns = [numbered_pattern, mcq_pattern, question_pattern]
                
                for pattern in all_patterns:
                    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0]
                        
                        # Clean the match
                        clean_match = re.sub(r'\s+', ' ', match).strip()
                        
                        # Filter out very short matches and common header/footer text
                        if (len(clean_match) > 25 and 
                            not any(header in clean_match.lower() for header in 
                                   ['page', 'copyright', 'instruction', 'total', 'mark', 'blank', 'end'])):
                            
                            # Determine question type
                            question_type = "Multiple Choice" if re.match(r'^[A-D][\.\)]', clean_match) else "Standard"
                            
                            all_questions.append({
                                'text': clean_match,
                                'page': page_num,
                                'source': filename,
                                'type': question_type
                            })
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_questions = []
        for q in all_questions:
            text_hash = hash(q['text'][:100])  # Hash first 100 chars to identify duplicates
            if text_hash not in seen:
                seen.add(text_hash)
                unique_questions.append(q)
        
        return unique_questions
        
    except Exception as e:
        st.error(f"Error processing {filename}: {str(e)}")
        return []

# Student search interface
st.markdown("---")
st.header("🎓 Student Search Portal")

# Show available papers
if st.session_state.uploaded_papers:
    st.success(f"📚 {len(st.session_state.uploaded_papers)} papers available for search")
    
    # Search interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        keyword = st.text_input(
            "🔍 Search for topics:",
            placeholder="e.g., algebra, photosynthesis, world war, chemistry...",
            help="Search through all uploaded question papers"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        search_clicked = st.button("🚀 Search Questions", type="primary", use_container_width=True)
    
    # Process search
    if search_clicked and keyword:
        if not st.session_state.uploaded_papers:
            st.warning("No papers available. Please upload papers first.")
        else:
            all_matching_questions = []
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Search through all papers
            paper_names = list(st.session_state.uploaded_papers.keys())
            for idx, paper_name in enumerate(paper_names):
                status_text.text(f"🔍 Searching in: {paper_name}...")
                
                paper_data = st.session_state.uploaded_papers[paper_name]
                
                # Extract questions if not already done
                if not paper_data['questions']:
                    paper_data['questions'] = extract_all_questions(paper_data['bytes'], paper_name)
                
                # Search for matching questions
                for question in paper_data['questions']:
                    if keyword.lower() in question['text'].lower():
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
                        # Different styling for multiple choice questions
                        if question['type'] == "Multiple Choice":
                            st.markdown(f"""
                            <div class="multiple-choice">
                                <strong>Q{i} (Page {question['page']}) - Multiple Choice:</strong><br>
                                {question['text']}
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class="question-box">
                                <strong>Q{i} (Page {question['page']}):</strong><br>
                                {question['text']}
                            </div>
                            """, unsafe_allow_html=True)
            
            else:
                st.warning(f"🔍 No questions found containing '{keyword}'")
                st.info("💡 Try different keywords or check if papers have been uploaded")
    
    elif search_clicked and not keyword:
        st.warning("⚠️ Please enter a search keyword first!")
    
    # Show paper statistics
    with st.expander("📊 Paper Statistics"):
        col1, col2, col3 = st.columns(3)
        total_questions = 0
        for paper_name, paper_data in st.session_state.uploaded_papers.items():
            if not paper_data['questions']:
                paper_data['questions'] = extract_all_questions(paper_data['bytes'], paper_name)
            total_questions += len(paper_data['questions'])
        
        col1.metric("Papers Available", len(st.session_state.uploaded_papers))
        col2.metric("Total Questions", total_questions)
        col3.metric("Searchable Topics", "All Subjects")

else:
    st.info("👆 **Teacher: Please upload question papers using the sidebar to get started**")
    st.markdown("""
    ### How it works:
    1. **Teacher uploads** PDF question papers in the sidebar
    2. **System processes** and stores all questions
    3. **Students search** for topics anytime
    4. **Results show** organized questions with page numbers
    """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>IGCSE Question Bank • Upload once, search forever • Perfect for exam preparation</p>
</div>
""", unsafe_allow_html=True)
