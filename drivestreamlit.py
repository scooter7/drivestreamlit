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

# Google Drive, Docs, Sheets, and Slides API setup
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly', 
    'https://www.googleapis.com/auth/documents.readonly', 
    'https://www.googleapis.com/auth/spreadsheets.readonly', 
    'https://www.googleapis.com/auth/presentations.readonly'
]
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["google"], scopes=SCOPES
)

drive_service = build('drive', 'v3', credentials=credentials)
docs_service = build('docs', 'v1', credentials=credentials)
sheets_service = build('sheets', 'v4', credentials=credentials)
slides_service = build('slides', 'v1', credentials=credentials)

# Debugging function: List all files in the folder to identify any visibility or mimeType issues
def list_all_files_in_folder(folder_id):
    query = f"'{folder_id}' in parents"
    results = drive_service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    items = results.get('files', [])
    
    # Print each file's name and mimeType to the console
    st.write("Files in folder with mimeTypes:")
    for item in items:
        st.write(f"File: {item['name']}, MimeType: {item['mimeType']}")
    return items

# Call the debugging function to check files in the folder
folder_id = st.secrets["google"]["folder_id"]
all_files = list_all_files_in_folder(folder_id)

# Functions to get files by mimeType
def get_google_files_from_folder(folder_id, mime_type):
    query = f"'{folder_id}' in parents and mimeType='{mime_type}'"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    return results.get('files', [])

# Functions to retrieve content from Google Docs, Sheets, and Slides
def get_document_content(doc_id):
    document = docs_service.documents().get(documentId=doc_id).execute()
    content = ""
    for element in document.get('body').get('content', []):
        if 'paragraph' in element:
            for text_run in element['paragraph']['elements']:
                if 'textRun' in text_run:
                    content += text_run['textRun']['content']
    return content

def get_sheet_content(sheet_id):
    sheet = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheet_content = ""
    for sheet in sheet['sheets']:
        sheet_name = sheet['properties']['title']
        result = sheets_service.spreadsheets().values().get(spreadsheetId=sheet_id, range=sheet_name).execute()
        values = result.get('values', [])
        for row in values:
            sheet_content += ' '.join(row) + "\n"
    return sheet_content

def get_slide_content(slide_id):
    presentation = slides_service.presentations().get(presentationId=slide_id).execute()
    content = ""
    for slide in presentation.get('slides', []):
        for element in slide.get('pageElements', []):
            if 'shape' in element and 'text' in element['shape']:
                for text_run in element['shape']['text']['textElements']:
                    if 'textRun' in text_run:
                        content += text_run['textRun']['content']
    return content

# Separate files by type
docs = get_google_files_from_folder(folder_id, 'application/vnd.google-apps.document')
sheets = get_google_files_from_folder(folder_id, 'application/vnd.google-apps.spreadsheet')
slides = get_google_files_from_folder(folder_id, 'application/vnd.google-apps.presentation')

# Display options for selection in Streamlit UI
doc_choices = [doc['name'] for doc in docs]
sheet_choices = [sheet['name'] for sheet in sheets]
slide_choices = [slide['name'] for slide in slides]

st.write("Available Google Docs:", doc_choices)
st.write("Available Google Sheets:", sheet_choices)
st.write("Available Google Slides:", slide_choices)

selected_docs_names = st.multiselect("Select Google Docs to query", doc_choices)
selected_sheets_names = st.multiselect("Select Google Sheets to query", sheet_choices)
selected_slides_names = st.multiselect("Select Google Slides to query", slide_choices)

# Retrieve content from selected files
selected_docs = [doc for doc in docs if doc['name'] in selected_docs_names]
selected_sheets = [sheet for sheet in sheets if sheet['name'] in selected_sheets_names]
selected_slides = [slide for slide in slides if slide['name'] in selected_slides_names]

doc_contents = [get_document_content(doc['id']) for doc in selected_docs]
sheet_contents = [get_sheet_content(sheet['id']) for sheet in selected_sheets]
slide_contents = [get_slide_content(slide['id']) for slide in selected_slides]

# Combine all contents for querying
all_contents = doc_contents + sheet_contents + slide_contents

# Function to filter document content based on keywords
def keyword_filter(content, keywords):
    filtered_sections = []
    for paragraph in content.split("\n"):
        if any(keyword.lower() in paragraph.lower() for keyword in keywords):
            filtered_sections.append(paragraph)
    return filtered_sections

# Function to truncate content to stay within token limits
def truncate_content(filtered_sections, max_tokens=1600):
    truncated_content = ""
    for section in filtered_sections:
        if len(truncated_content) + len(section) > max_tokens:
            break
        truncated_content += section + "\n"
    return truncated_content

# Function to query GPT-4o-mini
def query_gpt(filtered_sections, question, citations):
    context = truncate_content(filtered_sections, max_tokens=1600)
    
    if not context:
        return "Sorry, no relevant information was found in the document regarding your query."
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Context: {context}\n\nAnswer the following question: {question}"}
        ],
        max_tokens=500
    )

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

# Process query if files are selected
if selected_docs_names or selected_sheets_names or selected_slides_names:
    user_question = st.text_input("Ask a question about the selected files")
    
    if user_question:
        keywords = user_question.split()
        filtered_sections = []
        citations = set()
        
        for doc, content in zip(selected_docs, doc_contents):
            sections = keyword_filter(content, keywords)
            if sections:
                filtered_sections.extend(sections)
                citations.add((doc['name'], doc['id']))
        
        for sheet, content in zip(selected_sheets, sheet_contents):
            sections = keyword_filter(content, keywords)
            if sections:
                filtered_sections.extend(sections)
                citations.add((sheet['name'], sheet['id']))
        
        for slide, content in zip(selected_slides, slide_contents):
            sections = keyword_filter(content, keywords)
            if sections:
                filtered_sections.extend(sections)
                citations.add((slide['name'], slide['id']))
        
        answer = query_gpt(filtered_sections, user_question, citations)
        
        if answer:
            st.write(f"**Answer:** {answer}")
            save_chat_to_github(user_question, answer)
