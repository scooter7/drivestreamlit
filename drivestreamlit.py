import streamlit as st
from io import BytesIO
from googleapiclient.discovery import build
from google.oauth2 import service_account
from PyPDF2 import PdfReader
import openai
from langchain_community.text_splitter import CharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.chat_models import ChatOpenAI
from langchain_community.memory import ConversationBufferMemory
from langchain_community.chains import ConversationalRetrievalChain
from langchain_community.schema import Document

# Set up OpenAI API
openai.api_key = st.secrets["openai"]["api_key"]

# Google Drive and Docs API setup
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/documents.readonly']
credentials = service_account.Credentials.from_service_account_info(st.secrets["google"], scopes=SCOPES)

drive_service = build('drive', 'v3', credentials=credentials)
docs_service = build('docs', 'v1', credentials=credentials)

# Function to get docs from Google Drive
def get_google_docs_from_folder(folder_id):
    query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document'"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    return items

# Function to export content from a Google Doc in plain text format
def export_google_doc_content(doc_id):
    # Use the `export_media` method to export Google Docs in text format
    request = drive_service.files().export_media(fileId=doc_id, mimeType='text/plain')
    file_content = request.execute()
    return file_content.decode('utf-8')

# Function to process PDFs from Google Drive and get their content
def get_pdf_text(pdf_docs, pdf_names):
    text = []
    metadata = []
    for pdf, pdf_name in zip(pdf_docs, pdf_names):
        pdf_reader = PdfReader(pdf)
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
                metadata.append({'source': f"{pdf_name} - Page {page_num + 1}"})
    return text, metadata

# Function to chunk text content
def get_text_chunks(text, metadata):
    text_splitter = CharacterTextSplitter(separator="\n", chunk_size=1000, chunk_overlap=200, length_function=len)
    chunks = []
    chunk_metadata = []
    for i, page_text in enumerate(text):
        page_chunks = text_splitter.split_text(page_text)
        chunks.extend(page_chunks)
        chunk_metadata.extend([metadata[i]] * len(page_chunks))  # Assign correct metadata to each chunk
    return chunks, chunk_metadata

# Function to create a vectorstore
def get_vectorstore(text_chunks, chunk_metadata):
    if not text_chunks:
        raise ValueError("No text chunks available for embedding.")
    # Ensure OpenAI API Key is passed correctly
    embeddings = OpenAIEmbeddings(openai_api_key=openai.api_key)
    documents = [Document(page_content=chunk, metadata=chunk_metadata[i]) for i, chunk in enumerate(text_chunks)]
    vectorstore = FAISS.from_documents(documents, embedding=embeddings)
    return vectorstore

# Function to create a conversation chain using the vectorstore
def get_conversation_chain(vectorstore):
    llm = ChatOpenAI()
    memory = ConversationBufferMemory(memory_key='chat_history', return_messages=True, output_key='answer')
    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm, 
        retriever=vectorstore.as_retriever(), 
        memory=memory, 
        return_source_documents=True
    )
    return conversation_chain

# Main function to handle user input and display answers
def handle_userinput(user_question):
    if 'conversation' in st.session_state and st.session_state.conversation:
        response = st.session_state.conversation({'question': user_question})
        st.session_state.chat_history = response['chat_history']
        answer = response['answer']
        source_documents = response.get('source_documents', [])
        citations = [doc.metadata['source'] for doc in source_documents if doc.metadata]
        modified_answer = modify_response_language(answer, citations)
        st.write(modified_answer)

# Function to modify response language and add citations
def modify_response_language(original_response, citations=None):
    response = original_response.replace(" they ", " we ").replace(" their ", " our ")
    if citations:
        response += "\n\nSources:\n" + "\n".join(f"- {citation}" for citation in citations)
    return response

# Streamlit app
def main():
    st.title("Ask Carnegie Everything")

    if 'conversation' not in st.session_state:
        st.session_state.conversation = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    folder_id = st.secrets["google"]["folder_id"]
    docs = get_google_docs_from_folder(folder_id)
    doc_choices = [doc['name'] for doc in docs]
    selected_docs = st.multiselect("Select one or more documents to query", doc_choices)

    if selected_docs:
        # Process the Google Docs by exporting them as plain text
        doc_contents = [export_google_doc_content(doc['id']) for doc in docs if doc['name'] in selected_docs]
        raw_text, source_metadata = get_text_chunks(doc_contents, [{'source': name} for name in selected_docs])

        if raw_text:
            vectorstore = get_vectorstore(raw_text, source_metadata)
            st.session_state.conversation = get_conversation_chain(vectorstore)

    user_question = st.text_input("Ask a question about the document(s):")
    if user_question:
        handle_userinput(user_question)

if __name__ == '__main__':
    main()
