import streamlit as st
import fitz  # this is PyMuPDF
import openai
import pandas as pd
import streamlit as st
import fitz  # PyMuPDF
import json
import openai
import os
import pandas as pd
import io
import zipfile

# === UI Config ===
st.set_page_config(page_title="AI JD Processor", layout="wide", initial_sidebar_state="auto")
st.markdown("""
    <style>
    body {
        color: white;
        background-color: #0e1117;
    }
    .stApp {
        background-color: #0e1117;
    }
    .block-container {
        padding: 2rem 3rem;
    }
    .stButton > button {
        background-color: #2563eb;
        color: white;
        border-radius: 8px;
        height: 3em;
        padding: 0.5em 1.5em;
        margin-top: 1em;
    }
    .stDownloadButton > button {
        background-color: #16a34a;
        color: white;
        border-radius: 8px;
        padding: 0.4em 1em;
    }
    .stTextArea textarea {
        background-color: #1e1e1e;
        color: #d4d4d4;
    }
    </style>
""", unsafe_allow_html=True)

st.title("AI Job Description Processor")

openai.api_key = os.getenv("OPENAI_API_KEY")

uploaded_files = st.file_uploader("Upload Job Descriptions (PDF)", type=["pdf"], accept_multiple_files=True)

def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

def call_openai(prompt, temperature=0.3):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=1800
    )
    return response.choices[0].message.content.strip()

def get_skill_prompt(jd_text):
    return f"""
    Extract a list of skills from the following job description. Categorize each as Technical, Functional, or Soft Skill.
    For each skill, provide:
    - Skill Name
    - Type
    - Importance (0-10)
    - Priority (Core, Secondary, Bonus)
    - Recommended proficiency level (1-10)

    Job Description:
    {jd_text}
    """

def get_path_prompt(jd_text):
    return f"""
    Based on the following job description, generate 12 possible career paths:
    - 4 Vertical (senior versions)
    - 4 Horizontal (same level, different domain)
    - 4 Diagonal (cross-functional or leadership)

    For each path, include:
    - Role Title
    - Brief Description
    - Skill Gaps
    - Recommended Experience

    Job Description:
    {jd_text}
    """

def get_enhanced_jd_prompt(jd_text):
    return f"""
    Rewrite the job description below to make it clear, concise, and optimized for applicant tracking systems.
    Include sections like Responsibilities, Requirements, Preferred Skills, Company Info, etc.

    Original JD:
    {jd_text}
    """

def parse_skills(text):
    lines = [line for line in text.split("\n") if line.strip() and not line.startswith("-")]
    data = []
    for line in lines:
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 5:
            data.append({
                "Skill": parts[0],
                "Type": parts[1],
                "Importance": parts[2],
                "Priority": parts[3],
                "Proficiency": parts[4]
            })
    return pd.DataFrame(data)

def parse_paths(text):
    paths = {"Vertical": [], "Horizontal": [], "Diagonal": []}
    current = None
    for line in text.split("\n"):
        line = line.strip()
        if any(key in line for key in paths):
            current = next((k for k in paths if k in line), None)
        elif current and line:
            paths[current].append(line)
    return paths

temp_zip_bytes = io.BytesIO()
with zipfile.ZipFile(temp_zip_bytes, mode="w") as zipf:
    if uploaded_files:
        for pdf_file in uploaded_files:
            st.subheader(f"Results for: {pdf_file.name}")
            jd_text = extract_text_from_pdf(pdf_file)

            with st.spinner("Generating insights with GPT..."):
                enhanced_jd = call_openai(get_enhanced_jd_prompt(jd_text))
                skills_output = call_openai(get_skill_prompt(jd_text))
                paths_output = call_openai(get_path_prompt(jd_text))

            with st.expander("Enhanced Job Description"):
                st.text_area("Enhanced JD", value=enhanced_jd, height=300)
                txt_bytes = io.BytesIO(enhanced_jd.encode("utf-8"))
                st.download_button("Download JD (.txt)", data=txt_bytes, file_name="enhanced_jd.txt")

            with st.expander("Skill Profiler"):
                st.markdown("#### AI Extracted Skills Table")
                skill_df = parse_skills(skills_output)
                st.dataframe(skill_df)
                csv = skill_df.to_csv(index=False).encode("utf-8")
                st.download_button("Download Skills as CSV", data=csv, file_name="skills.csv", mime="text/csv")

            with st.expander("Career Paths"):
                st.markdown("#### AI Suggested Career Growth Paths")
                paths = parse_paths(paths_output)
                col1, col2, col3 = st.columns(3)
                col1.write("### Vertical")
                col1.write(paths["Vertical"])
                col2.write("### Horizontal")
                col2.write(paths["Horizontal"])
                col3.write("### Diagonal")
                col3.write(paths["Diagonal"])

                flat_data = [(k, v) for k, lst in paths.items() for v in lst]
                path_df = pd.DataFrame(flat_data, columns=["Path Type", "Role"])
                path_csv = path_df.to_csv(index=False).encode("utf-8")
                st.download_button("Download Career Paths as CSV", data=path_csv, file_name="career_paths.csv")

            base = pdf_file.name.replace(".pdf", "")
            zipf.writestr(f"{base}/enhanced_jd.txt", enhanced_jd)
            zipf.writestr(f"{base}/skills.csv", skill_df.to_csv(index=False))
            zipf.writestr(f"{base}/career_paths.csv", path_df.to_csv(index=False))

            results = {
                "file": pdf_file.name,
                "enhanced_jd": enhanced_jd,
                "skills": skills_output,
                "career_paths": paths_output
            }
            st.download_button(
                label="Download Results as JSON",
                data=json.dumps(results, indent=2),
                file_name=f"{pdf_file.name}_output.json",
                mime="application/json"
            )
            zipf.writestr(f"{base}/result.json", json.dumps(results, indent=2))

if uploaded_files:
    st.markdown("---")
    st.markdown("### Download All Results")
    temp_zip_bytes.seek(0)
    st.download_button(
        label="Download All as ZIP",
        data=temp_zip_bytes,
        file_name="all_jd_results.zip",
        mime="application/zip"
    )
