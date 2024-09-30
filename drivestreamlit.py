import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import openai

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

# OpenAI Chat with correct API syntax
def chat_with_document(content, question):
    response = openai.chat.completions.create(
        model="gpt-4o-mini",  # Use GPT-4o-mini model
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Here is the document content: {content}. Now, answer this question: {question}"}
        ],
        max_tokens=150
    )
    
    # Extract the message content from the response
    message_content = response.choices[0].message.content  # Access the 'content' as an object attribute
    
    return message_content

# Streamlit App
folder_id = st.secrets["google"]["folder_id"]  # Use the folder ID from Streamlit secrets
docs = get_google_docs_from_folder(folder_id)
doc_choices = [doc['name'] for doc in docs]

# Multi-select for selecting multiple Google Docs
selected_docs = st.multiselect("Select one or more documents to query", doc_choices)

if selected_docs:
    doc_ids = [doc['id'] for doc in docs if doc['name'] in selected_docs]  # Get the corresponding doc IDs
    for idx, doc_id in enumerate(doc_ids):
        # Get document content from Google Docs
        doc_content = get_document_content(doc_id)  # Fetch the actual document content
        user_question = st.text_input(f"Ask a question about the document: {selected_docs[idx]}", key=f"question_{idx}")
        
        if user_question:
            answer = chat_with_document(doc_content, user_question)
            if answer:
                st.write(f"Answer for {selected_docs[idx]}: {answer}")
