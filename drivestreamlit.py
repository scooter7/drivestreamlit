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

# Function to filter document content based on keywords
def keyword_filter(content, keywords):
    filtered_sections = []
    for paragraph in content.split("\n"):
        if any(keyword.lower() in paragraph.lower() for keyword in keywords):
            filtered_sections.append(paragraph)
    return filtered_sections

# Function to query GPT-3.5-turbo (new format for openai>=1.0.0)
def query_gpt(filtered_sections, question):
    # Concatenate the relevant sections to form the context
    context = "\n".join(filtered_sections)
    
    # If no relevant sections were found, return early
    if not context:
        return "Sorry, no relevant information was found in the document regarding your query."
    
    # Query GPT-3.5-turbo with the context and question
    response = openai.chat_completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Context: {context}\n\nAnswer the following question: {question}"}
        ],
        max_tokens=500  # Adjust based on the desired length of the response
    )
    
    # Extract the response content
    return response['choices'][0]['message']['content']

# Streamlit App
folder_id = st.text_input("Enter the Google Drive folder ID")
if folder_id:
    docs = get_google_docs_from_folder(folder_id)
    doc_choices = [doc['name'] for doc in docs]
    selected_doc = st.selectbox("Select a document to query", doc_choices)

    if selected_doc:
        doc_id = next(doc['id'] for doc in docs if doc['name'] == selected_doc)
        # Get document content from Google Docs
        doc_content = get_document_content(doc_id)
        
        # Ask the user for the query
        user_question = st.text_input("Ask a question about the document")
        
        if user_question:
            # Use keywords to filter the document
            keywords = user_question.split()  # Simple keyword extraction from the user question
            filtered_sections = keyword_filter(doc_content, keywords)
            
            # Query GPT-3.5-turbo with the filtered sections
            answer = query_gpt(filtered_sections, user_question)
            if answer:
                st.write(f"**Answer:** {answer}")
