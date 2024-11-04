import os
import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
from openai import OpenAI  # Import OpenAI client
from datetime import datetime
import base64
import httpx

# GitHub URLs for saving chat history
GITHUB_HISTORY_URL = "https://api.github.com/repos/scooter7/drivestreamlit/contents/chats"

# Set up OpenAI API client
client = OpenAI(
    api_key=st.secrets["openai"]["api_key"]  # Access OpenAI API key from Streamlit secrets
)

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

# Function to truncate content to stay within token limits
def truncate_content(filtered_sections, max_tokens=1600):
    # GPT-4o-mini supports a larger context window, but for safety, limit to 1600 tokens
    truncated_content = ""
    for section in filtered_sections:
        if len(truncated_content) + len(section) > max_tokens:
            break
        truncated_content += section + "\n"
    return truncated_content

# Function to query GPT-4o-mini
def query_gpt(filtered_sections, question, citations):
    # Truncate content to ensure it fits within the token limit
    context = truncate_content(filtered_sections, max_tokens=1600)
    
    # If no relevant sections were found, return early
    if not context:
        return "Sorry, no relevant information was found in the document regarding your query."
    
    # Query GPT-4o-mini with the context and question
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Specify the GPT-4o-mini model
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Context: {context}\n\nAnswer the following question: {question}"}
        ],
        max_tokens=500  # Adjust based on the desired length of the response
    )

    # Extract the response content
    bot_response = response.choices[0].message.content

    # Add citations to the response
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
    
    # Prepare chat content
    chat_content = f"Timestamp: {timestamp}\nUser question: {user_question}\nBot response: {bot_response}"
    
    # Encode the content for GitHub
    encoded_content = base64.b64encode(chat_content.encode('utf-8')).decode('utf-8')
    
    data = {
        "message": f"Save chat history on {timestamp}",
        "content": encoded_content,
        "branch": "main"
    }
    
    # Save to GitHub
    try:
        response = httpx.put(f"{GITHUB_HISTORY_URL}/{file_name}", headers=headers, json=data)
        response.raise_for_status()
        st.success("Chat history saved successfully to GitHub.")
    except httpx.HTTPStatusError as e:
        st.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        st.error(f"An error occurred: {e}")

# Streamlit App
folder_id = st.secrets["google"]["folder_id"]  # Retrieve the folder ID from Streamlit secrets
docs = get_google_docs_from_folder(folder_id)
doc_choices = [doc['name'] for doc in docs]
selected_docs_names = st.multiselect("Select documents to query", doc_choices)

if selected_docs_names:
    selected_docs = [doc for doc in docs if doc['name'] in selected_docs_names]
    doc_contents = [get_document_content(doc['id']) for doc in selected_docs]
    
    # Ask the user for the query
    user_question = st.text_input("Ask a question about the document(s)")
    
    if user_question:
        # Use keywords to filter the document
        keywords = user_question.split()  # Simple keyword extraction from the user question
        filtered_sections = []
        citations = set()  # Track which documents are relevant
        
        # Filter sections for each selected document and collect citations
        for doc, content in zip(selected_docs, doc_contents):
            sections = keyword_filter(content, keywords)
            if sections:
                filtered_sections.extend(sections)
                citations.add((doc['name'], doc['id']))  # Track document citations
        
        # Query GPT-4o-mini with the filtered sections
        answer = query_gpt(filtered_sections, user_question, citations)
        
        if answer:
            st.write(f"**Answer:** {answer}")
            # Save chat to GitHub
            save_chat_to_github(user_question, answer)
