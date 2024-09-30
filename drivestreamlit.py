import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import openai
import textwrap

# Set up OpenAI API
openai.api_key = st.secrets["openai"]["api_key"]  # Access OpenAI API key from Streamlit secrets

# Google Drive and Docs API setup
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/documents.readonly']
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["google"], scopes=SCOPES)  # Access Google credentials from Streamlit secrets

drive_service = build('drive', 'v3', credentials=credentials)
docs_service = build('docs', 'v1', credentials=credentials)

# Function to get docs from Google Drive
def get_google_docs_from_folder(folder_id):
    query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document'"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    return items

# Function to get content from a Google Doc
def get_document_content(doc_id):
    document = docs_service.documents().get(documentId=doc_id).execute()
    content = ""
    for element in document.get('body').get('content'):
        if 'paragraph' in element:
            for text_run in element['paragraph']['elements']:
                if 'textRun' in text_run:
                    content += text_run['textRun']['content']
    return content

# Helper function to chunk the document content into smaller pieces
def chunk_content(content, max_length=1500):
    wrapped_content = textwrap.wrap(content, max_length)
    return wrapped_content

# OpenAI Chat with concise and focused responses
def chat_with_document(content, question):
    chunks = chunk_content(content)
    full_answer = ""

    for chunk in chunks:
        prompt = f"Here is a section of the document: {chunk}\n\nAnswer the following question briefly and without repeating similar phrases: {question}"
        
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a concise assistant that provides short, clear responses."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,  # Further reduce tokens to enforce concise responses
            temperature=0.3  # Lower temperature to reduce verbosity
        )
        
        # Extract the message content from the response
        answer = response.choices[0].message.content.strip()
        
        # Only append if it's not a redundant response
        if answer and "does not contain" not in full_answer:
            full_answer += answer + "\n"
    
    return full_answer.strip()

# Streamlit App
folder_id = st.secrets["google"]["folder_id"]  # Use the folder ID from Streamlit secrets
docs = get_google_docs_from_folder(folder_id)
doc_choices = [doc['name'] for doc in docs]

# Multi-select for selecting multiple Google Docs
selected_docs = st.multiselect("Select one or more documents to query", doc_choices)

if selected_docs:
    # Single text input area for entering the question
    user_question = st.text_input("Ask a question to query across the selected documents")

    if user_question:
        for doc_name in selected_docs:
            doc_id = next(doc['id'] for doc in docs if doc['name'] == doc_name)
            # Get document content from Google Docs
            doc_content = get_document_content(doc_id)
            
            # Query each document with the same question
            answer = chat_with_document(doc_content, user_question)
            if answer:
                st.write(f"Answer for {doc_name}: {answer}")
