import streamlit as st
import pdfplumber
import re
import tempfile
import os

st.set_page_config(
    page_title="IGCSE Question Bank Search",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 IGCSE Question Bank Search")
st.markdown("Upload your IGCSE PDF question papers and search for specific topics!")

# File upload
uploaded_files = st.file_uploader(
    "Upload PDF files",
    type="pdf",
    accept_multiple_files=True,
    help="Upload IGCSE question paper PDFs"
)

# Search input
keyword = st.text_input("Enter keyword to search for:", placeholder="e.g., algebra, photosynthesis, chemistry...")

def extract_questions_from_pdf(file_bytes, filename, search_term):
    questions = []
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        # Extract text from PDF
        with pdfplumber.open(tmp_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        
        # Find questions (numbered items)
        pattern = r'(\d+[\.\)]\s+.*?)(?=\n\d+[\.\)]|\n\s*$|$)'
        matches = re.findall(pattern, full_text, re.DOTALL)
        
        for match in matches:
            if search_term.lower() in match.lower():
                # Clean up the text
                clean_match = re.sub(r'\s+', ' ', match).strip()
                if len(clean_match) > 20:  # Only include substantial matches
                    questions.append({
                        'text': clean_match,
                        'source': filename
                    })
        
        # Clean up temp file
        os.unlink(tmp_path)
        
    except Exception as e:
        st.error(f"Error processing {filename}: {str(e)}")
    
    return questions

# Search button
if st.button("Search Questions", type="primary"):
    if not keyword:
        st.warning("Please enter a search keyword first!")
    elif not uploaded_files:
        st.warning("Please upload at least one PDF file first!")
    else:
        all_questions = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Searching in {uploaded_file.name}...")
            questions = extract_questions_from_pdf(
                uploaded_file.getvalue(), 
                uploaded_file.name, 
                keyword
            )
            if questions:
                all_questions.extend(questions)
            progress_bar.progress((i + 1) / len(uploaded_files))
        
        progress_bar.empty()
        status_text.empty()
        
        # Display results
        if all_questions:
            st.success(f"🎉 Found {len(all_questions)} questions matching '{keyword}'!")
            
            # Group by file
            questions_by_file = {}
            for q in all_questions:
                if q['source'] not in questions_by_file:
                    questions_by_file[q['source']] = []
                questions_by_file[q['source']].append(q)
            
            # Display organized results
            for filename, file_questions in questions_by_file.items():
                st.subheader(f"📄 {filename} ({len(file_questions)} questions)")
                
                for i, question in enumerate(file_questions, 1):
                    st.markdown(f"""
                    <div style="
                        background-color: #f0f2f6; 
                        padding: 1rem; 
                        border-radius: 0.5rem; 
                        margin-bottom: 1rem;
                        border-left: 4px solid #1f77b4;
                    ">
                        <strong>Q{i}:</strong> {question['text']}
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.warning(f"No questions found containing '{keyword}'. Try a different search term.")

# Instructions
with st.sidebar:
    st.header("Instructions")
    st.markdown("""
    1. **Upload PDF files** of IGCSE question papers
    2. **Enter a keyword** to search for
    3. **Click 'Search Questions'**
    4. **Browse results** organized by file
    
    **Example searches:**
    - algebra
    - photosynthesis  
    - world war
    - Shakespeare
    - chemistry
    """)
    
    st.markdown("---")
    st.header("About")
    st.markdown("This app helps you quickly find relevant questions across multiple IGCSE exam papers.")