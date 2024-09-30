import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
from openai import OpenAI

# Set up OpenAI API
client = OpenAI()
openai_api_key = st.secrets["openai"]["api_key"]
client.api_key = openai_api_key

# Google Drive API setup
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SERVICE_ACCOUNT_FILE = 'path_to_google_credentials.json'  # Use Streamlit secrets to store this

credentials = service_account.Credentials.from_service_account_info(
    st.secrets["google"], scopes=SCOPES)

drive_service = build('drive', 'v3', credentials=credentials)

# Function to get docs from Google Drive
def get_google_docs_from_folder(folder_id):
    query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document'"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    return items

# OpenAI Chat with the correct new API syntax
def chat_with_document(content, question):
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Assuming you are using GPT-4o-mini
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Here is the document content: {content}. Now, answer this question: {question}"}
        ],
        max_tokens=150
    )

    # Debug the response to check its structure
    st.write(response)  # Output the entire response to inspect

    # Correct access of response content based on the API response structure
    return response.choices[0].message['content']

# Streamlit App
folder_id = st.text_input("Enter the Google Drive folder ID")
if folder_id:
    docs = get_google_docs_from_folder(folder_id)
    doc_choices = [doc['name'] for doc in docs]
    selected_doc = st.selectbox("Select a document to query", doc_choices)

    if selected_doc:
        doc_id = next(doc['id'] for doc in docs if doc['name'] == selected_doc)
        # Get document content from Google Docs
        doc_content = "Extracted document content here"  # Implement Google Docs content extraction
        user_question = st.text_input("Ask a question about the document")
        
        if user_question:
            answer = chat_with_document(doc_content, user_question)
            st.write(f"Answer: {answer}")
