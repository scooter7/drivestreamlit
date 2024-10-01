import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import openai

# Set up OpenAI API
openai.api_key = st.secrets["openai"]["api_key"]

# Google Drive and Docs API setup
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/documents.readonly']
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["google"], scopes=SCOPES)

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
    for element in document.get('body').get('content', []):
        if 'paragraph' in element:
            for text_run in element['paragraph']['elements']:
                if 'textRun' in text_run:
                    content += text_run['textRun']['content']
    return content

# Keyword-based search within the document
def find_relevant_section(content, keyword):
    keyword = keyword.lower()
    content_lower = content.lower()
    if keyword in content_lower:
        start_index = content_lower.find(keyword)
        # Grab a portion of text around the keyword for better context
        return content[max(0, start_index-500):min(len(content), start_index+500)]
    return None

# OpenAI Chat function with content optimization
def chat_with_document(content, question):
    if len(content) > 5000:
        content = content[:5000] + "..."
    
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Here is the document content: {content}. Now, answer this question: {question}"}
        ],
        max_tokens=300
    )
    
    message_content = response.choices[0].message['content']
    
    return message_content

# Streamlit App
st.title("Query Google Docs and Get Answers")

folder_id = st.text_input("Enter the Google Drive folder ID")
if folder_id:
    docs = get_google_docs_from_folder(folder_id)
    doc_choices = [doc['name'] for doc in docs]
    selected_doc = st.selectbox("Select a document to query", doc_choices)

    if selected_doc:
        doc_id = next(doc['id'] for doc in docs if doc['name'] == selected_doc)
        doc_content = get_document_content(doc_id)
        
        st.write(f"Document Content (first 2000 characters): {doc_content[:2000]}...")
        
        user_question = st.text_input("Ask a question about the document")
        
        if user_question:
            keyword = user_question.split()[-1]  # Assuming the keyword is the last word of the question
            relevant_section = find_relevant_section(doc_content, keyword)
            
            if relevant_section:
                st.write(f"Relevant Section: {relevant_section[:500]}...")
                answer = chat_with_document(relevant_section, user_question)
            else:
                answer = "The document does not contain any relevant information about the question."
            
            if answer:
                st.write(f"Answer: {answer}")
