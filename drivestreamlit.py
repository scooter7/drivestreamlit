import os
import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
from openai import OpenAI
from datetime import datetime
import base64
import httpx

# GitHub URLs for saving chat history
GITHUB_HISTORY_URL = "https://api.github.com/repos/scooter7/drivestreamlit/contents/chats"

# Set up OpenAI API client
client = OpenAI(
    api_key=st.secrets["openai"]["api_key"]
)

# Google Drive and Docs API setup
SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/documents.readonly']
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["google"], scopes=SCOPES
)

drive_service = build('drive', 'v3', credentials=credentials)
docs_service = build('docs', 'v1', credentials=credentials)

# Function to retrieve Google Docs files from a specified folder in Google Drive
def get_google_docs_from_folder(folder_id):
    query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document'"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    return items

# Function to retrieve the content of a Google Doc
def get_document_content(doc_id):
    document = docs_service.documents().get(documentId=doc_id).execute()
    content = ""
    for element in document.get('body').get('content'):
        if 'paragraph' in element:
            for text_run in element['paragraph']['elements']:
                if 'textRun' in text_run:
                    content += text_run['textRun']['content']
    return content

# Function to find sections containing any term from the user's question
def find_relevant_sections(content, question):
    # Split the question into individual words for matching
    question_terms = set(word.lower() for word in question.split())
    
    matched_sections = []
    for paragraph in content.split("\n"):
        if any(term in paragraph.lower() for term in question_terms):
            matched_sections.append(paragraph.strip())
    return matched_sections

# Function to dynamically assemble context with found matches
def assemble_context(matched_sections, max_tokens=3000):
    if not matched_sections:
        return "No relevant information was found based on your query."
    
    context = ""
    tokens_used = 0
    
    for section in matched_sections:
        section_tokens = len(section.split())
        if tokens_used + section_tokens > max_tokens:
            break
        context += section + "\n\n"
        tokens_used += section_tokens
    
    return context

# GPT query function focusing on document-based response
def query_gpt_improved(matched_sections, question, citations):
    context = assemble_context(matched_sections, max_tokens=3000)
    
    if "No relevant information was found" in context:
        return context  # Return this early if no matches were found
    
    # Display a portion of the context for debugging
    st.write("### Context Window for Debugging (Partial):")
    st.write(context[:1500])  # Display first 1500 characters for inspection
    
    # Query GPT-4o-mini
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an assistant providing answers based only on provided document content."},
            {"role": "user", "content": f"Based on this context:\n{context}\n\nAnswer this question as specifically as possible: {question}"}
        ],
        max_tokens=800
    )

    # Extract response and add citations
    bot_response = response.choices[0].message.content
    doc_links = "\n".join([f"- {doc_name} (https://docs.google.com/document/d/{doc_id})" for doc_name, doc_id in citations])
    bot_response += f"\n\n**Citations**:\n{doc_links}"

    return bot_response

# Function to save chat logs to GitHub
def save_chat_to_github(user_question, bot_response):
    github_token = st.secrets["github"]["access_token"]
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': f'token {github_token}'
    }
    
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"chat_history_{timestamp}.txt"
    
    # Prepare chat content and encode for GitHub
    chat_content = f"Timestamp: {timestamp}\nUser question: {user_question}\nBot response: {bot_response}"
    encoded_content = base64.b64encode(chat_content.encode('utf-8')).decode('utf-8')
    
    data = {
        "message": f"Save chat history on {timestamp}",
        "content": encoded_content,
        "branch": "main"
    }
    
    try:
        response = httpx.put(f"{GITHUB_HISTORY_URL}/{file_name}", headers=headers, json=data)
        response.raise_for_status()
        st.success("Chat history saved successfully to GitHub.")
    except httpx.HTTPStatusError as e:
        st.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        st.error(f"An error occurred: {e}")

# Streamlit app to query and respond based on document content
folder_id = st.secrets["google"]["folder_id"]
docs = get_google_docs_from_folder(folder_id)
doc_choices = [doc['name'] for doc in docs]
selected_docs_names = st.multiselect("Select documents to query", doc_choices)

if selected_docs_names:
    selected_docs = [doc for doc in docs if doc['name'] in selected_docs_names]
    doc_contents = [get_document_content(doc['id']) for doc in selected_docs]
    
    user_question = st.text_input("Ask a question about the document(s)")
    
    if user_question:
        matched_sections = []
        citations = set()
        
        for doc, content in zip(selected_docs, doc_contents):
            sections = find_relevant_sections(content, user_question)
            if sections:
                matched_sections.extend(sections)
                citations.add((doc['name'], doc['id']))
        
        answer = query_gpt_improved(matched_sections, user_question, citations)
        
        if answer:
            st.write(f"**Answer:** {answer}")
            save_chat_to_github(user_question, answer)
