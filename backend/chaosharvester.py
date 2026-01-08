import pandas as pd
import PyPDF2
import docx
import json
import os
from typing import Dict, List, Any
import streamlit as st
from openai import OpenAI


import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import time
class ChaosInsighter:
    def __init__(self):
        # Initialize OpenAI client with the new format
        self.client = OpenAI(
            api_key="8124c85892537a0bfcdae4b999e4eba2909c367431cab6a72589c2278e4c2cc4",
            base_url="https://api.together.xyz/v1"
        )
        self.model_name = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
        self.analyzed_content = ""
        self.file_summary = ""

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF files"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            return f"Error reading PDF: {str(e)}"

    def extract_text_from_excel(self, file_path: str) -> str:
        """Extract text from Excel files"""
        try:
            df = pd.read_excel(file_path)
            text = df.to_string(index=False)
            return text
        except Exception as e:
            return f"Error reading Excel file: {str(e)}"

    def extract_text_from_csv(self, file_path: str) -> str:
        """Extract text from CSV files"""
        try:
            df = pd.read_csv(file_path)
            text = df.to_string(index=False)
            return text
        except Exception as e:
            return f"Error reading CSV file: {str(e)}"

    def extract_text_from_docx(self, file_path: str) -> str:
        """Extract text from Word documents"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            return f"Error reading Word document: {str(e)}"

    def extract_text_from_txt(self, file_path: str) -> str:
        """Extract text from text files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except Exception as e:
            return f"Error reading text file: {str(e)}"

    def extract_text_from_json(self, file_path: str) -> str:
        """Extract text from JSON files"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                return json.dumps(data, indent=2)
        except Exception as e:
            return f"Error reading JSON file: {str(e)}"

    def process_file(self, file_path: str) -> str:
        """Process different file formats and extract text"""
        file_extension = os.path.splitext(file_path)[1].lower()

        extractors = {
            '.pdf': self.extract_text_from_pdf,
            '.xlsx': self.extract_text_from_excel,
            '.xls': self.extract_text_from_excel,
            '.csv': self.extract_text_from_csv,
            '.docx': self.extract_text_from_docx,
            '.doc': self.extract_text_from_docx,
            '.txt': self.extract_text_from_txt,
            '.json': self.extract_text_from_json
        }

        if file_extension in extractors:
            return extractors[file_extension](file_path)
        else:
            return f"Unsupported file format: {file_extension}"

    def analyze_content(self, content: str) -> str:
        """Analyze the extracted content and generate initial insights"""
        prompt = f"""You are an advanced data analyst. Analyze the following content and provide comprehensive insights including:

1. Summary of the content
2. Key themes and patterns
3. Important statistics or data points (if applicable)
4. Notable trends or anomalies
5. Overall assessment

Content to analyze:
{content[:4000]}  # Limiting content to avoid token limits

Provide detailed insights:"""

        try:
            # Updated API call format for OpenAI 1.0+
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500
            )

            analysis = response.choices[0].message.content.strip()
            self.analyzed_content = content
            self.file_summary = analysis
            return analysis

        except Exception as e:
            return f"Error during analysis: {str(e)}"

    def answer_question(self, question: str) -> str:
        """Answer specific questions about the analyzed content"""
        if not self.analyzed_content:
            return "No content has been analyzed yet. Please upload and analyze a file first."

        prompt = f"""Based on the following content, answer the user's question accurately and comprehensively:

Content:
{self.analyzed_content[:3000]}

Previous Analysis Summary:
{self.file_summary}

User Question: {question}

Answer:"""

        try:
            # Updated API call format for OpenAI 1.0+
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1000
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            return f"Error answering question: {str(e)}"

def main():
    """Main function to run the Chaos Insighter"""
    insighter = ChaosInsighter()

    print("🔍 Welcome to Chaos Insighter!")
    print("="*50)

    while True:
        print("\nOptions:")
        print("1. Analyze a new file")
        print("2. Ask questions about analyzed content")
        print("3. Exit")

        choice = input("\nEnter your choice (1-3): ").strip()

        if choice == "1":
            file_path = input("Enter the file path: ").strip()

            if not os.path.exists(file_path):
                print("❌ File not found. Please check the path.")
                continue

            print("📄 Processing file...")
            extracted_content = insighter.process_file(file_path)

            if extracted_content.startswith("Error"):
                print(f"❌ {extracted_content}")
                continue

            print("🔍 Analyzing content...")
            analysis = insighter.analyze_content(extracted_content)

            print("\n" + "="*50)
            print("📊 ANALYSIS RESULTS:")
            print("="*50)
            print(analysis)
            print("="*50)

        elif choice == "2":
            if not insighter.analyzed_content:
                print("❌ No content analyzed yet. Please analyze a file first.")
                continue

            question = input("\n❓ Enter your question about the analyzed content: ").strip()

            if not question:
                print("❌ Please enter a valid question.")
                continue

            print("🤔 Thinking...")
            answer = insighter.answer_question(question)

            print("\n" + "="*30)
            print("💡 ANSWER:")
            print("="*30)
            print(answer)
            print("="*30)

        elif choice == "3":
            print("👋 Thanks for using Chaos Insighter!")
            break

        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")

# Streamlit Web Interface (Optional)
def streamlit_app():
    """Streamlit web interface for Chaos Insighter"""
    st.set_page_config(page_title="Chaos Insighter", page_icon="🔍")

    st.title("🔍 Chaos Insighter")
    st.markdown("Upload files and get intelligent insights!")

    # Initialize session state
    if 'insighter' not in st.session_state:
        st.session_state.insighter = ChaosInsighter()

    # File upload
    uploaded_file = st.file_uploader(
        "Choose a file",
        type=['pdf', 'xlsx', 'xls', 'csv', 'docx', 'txt', 'json']
    )

    if uploaded_file is not None:
        # Save uploaded file temporarily
        with open(f"temp_{uploaded_file.name}", "wb") as f:
            f.write(uploaded_file.getbuffer())

        if st.button("Analyze File"):
            with st.spinner("Processing file..."):
                content = st.session_state.insighter.process_file(f"temp_{uploaded_file.name}")

            with st.spinner("Analyzing content..."):
                analysis = st.session_state.insighter.analyze_content(content)

            st.success("Analysis complete!")
            st.markdown("### 📊 Analysis Results:")
            st.write(analysis)

            # Clean up temp file
            os.remove(f"temp_{uploaded_file.name}")

    # Question answering section
    if st.session_state.insighter.analyzed_content:
        st.markdown("### ❓ Ask Questions")
        question = st.text_input("Enter your question about the analyzed content:")

        if st.button("Get Answer") and question:
            with st.spinner("Finding answer..."):
                answer = st.session_state.insighter.answer_question(question)
            st.markdown("### 💡 Answer:")
            st.write(answer)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "console":
        main()  # run console mode
    else:
        streamlit_app()  # run Streamlit mode

