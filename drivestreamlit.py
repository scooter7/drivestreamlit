import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
import openai

# Import necessary LangChain modules
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.schema import Document

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

# Function to chat with the document using LangChain
def chat_with_document_langchain(content, question):
    # Split the content into manageable chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    texts = text_splitter.split_text(content)
    
    # Create Document objects for each chunk
    documents = [Document(page_content=text) for text in texts]
    
    # Initialize OpenAI embeddings
    embeddings = OpenAIEmbeddings(openai_api_key=openai.api_key)
    
    # Create a vector store from the documents and embeddings
    vectorstore = FAISS.from_documents(documents, embeddings)
    
    # Create a retriever from the vector store
    retriever = vectorstore.as_retriever()
    
    # Initialize the ChatOpenAI model
    llm = ChatOpenAI(openai_api_key=openai.api_key, model_name="gpt-4")
    
    # Create a RetrievalQA chain
    qa_chain = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)
    
    # Track if we find any relevant answers
    final_answer = ""
    
    # Process chunks and get answers for each
    for text_chunk in texts:
        try:
            answer = qa_chain.run(question)
            if "I'm sorry" not in answer:
                final_answer += answer + "\n"
                # Break the loop if an answer is found
                break
        except Exception as e:
            st.write(f"Error while processing chunk: {e}")
    
    # If no answer found, return a single message
    if final_answer == "":
        final_answer = "Sorry, no relevant information was found in the document regarding your query."
    
    return final_answer

# Streamlit App
folder_id = st.text_input("Enter the Google Drive folder ID")
if folder_id:
    docs = get_google_docs_from_folder(folder_id)
    doc_choices = [doc['name'] for doc in docs]
    selected_doc = st.selectbox("Select a document to query", doc_choices)

    if selected_doc:
        doc_id = next(doc['id'] for doc in docs if doc['name'] == selected_doc)
        # Get document content from Google Docs
        doc_content = get_document_content(doc_id)  # Fetch the actual document content
        user_question = st.text_input("Ask a question about the document")
        
        if user_question:
            answer = chat_with_document_langchain(doc_content, user_question)
            if answer:
                st.write(f"**Answer:** {answer}")
