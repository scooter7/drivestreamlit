import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import openai
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.schema import Document

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

# Function to split document into chunks
def split_document_into_chunks(content, chunk_size=2000):
    return [content[i:i + chunk_size] for i in range(0, len(content), chunk_size)]

# Function to convert text chunks into embeddings and create a vectorstore
def create_vectorstore_from_chunks(text_chunks):
    embeddings = OpenAIEmbeddings()
    docs = [Document(page_content=chunk) for chunk in text_chunks]
    vectorstore = FAISS.from_documents(docs, embeddings)
    return vectorstore

# Function to find the relevant chunk of the document using embeddings search
def find_relevant_chunk(vectorstore, query):
    docs = vectorstore.similarity_search(query)
    if docs:
        return docs[0].page_content
    return None

# Function to chat with the document using the correct syntax `openai.chat.completions.create`
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
    
    message_content = response.choices[0]['message']['content']
    
    return message_content

# Streamlit app
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
        
        # Split the document into chunks
        chunks = split_document_into_chunks(doc_content)
        
        # Create the vectorstore
        vectorstore = create_vectorstore_from_chunks(chunks)
        
        user_question = st.text_input("Ask a question about the document")
        
        if user_question:
            # Search for the most relevant chunk
            relevant_chunk = find_relevant_chunk(vectorstore, user_question)
            
            if relevant_chunk:
                st.write(f"Relevant Section: {relevant_chunk[:500]}...")
                answer = chat_with_document(relevant_chunk, user_question)
            else:
                answer = "The document does not contain any relevant information about the question."
            
            if answer:
                st.write(f"Answer: {answer}")
