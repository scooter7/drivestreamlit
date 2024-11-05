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

# Function to list all files accessible by the service account
def list_all_files():
    try:
        results = drive_service.files().list(fields="files(id, name, mimeType)").execute()
        items = results.get('files', [])
        if not items:
            st.write("No files found accessible to this service account.")
        else:
            st.write("Accessible files for the service account with MIME types:")
            for item in items:
                st.write(f"File Name: {item['name']}, ID: {item['id']}, MimeType: {item['mimeType']}")
        return items
    except Exception as e:
        st.write(f"Error accessing files: {e}")
        return []

# Retrieve all accessible files
all_files = list_all_files()

# Separate files by type based on mimeTypes
docs = [file for file in all_files if file['mimeType'] == 'application/vnd.google-apps.document']
sheets = [file for file in all_files if file['mimeType'] == 'application/vnd.google-apps.spreadsheet']
slides = [file for file in all_files if file['mimeType'] == 'application/vnd.google-apps.presentation']

# Display options for selection in Streamlit UI
doc_choices = [doc['name'] for doc in docs]
sheet_choices = [sheet['name'] for sheet in sheets]
slide_choices = [slide['name'] for slide in slides]

st.write("Available Google Docs:", doc_choices)
st.write("Available Google Sheets:", sheet_choices)
st.write("Available Google Slides:", slide_choices)

# Selection for user interaction
selected_docs_names = st.multiselect("Select Google Docs to query", doc_choices)
selected_sheets_names = st.multiselect("Select Google Sheets to query", sheet_choices)
selected_slides_names = st.multiselect("Select Google Slides to query", slide_choices)

# Functions to retrieve content from Google Docs, Sheets, and Slides
def get_document_content(doc_id):
    try:
        document = docs_service.documents().get(documentId=doc_id).execute()
        content = ""
        for element in document.get('body').get('content', []):
            if 'paragraph' in element:
                for text_run in element['paragraph']['elements']:
                    if 'textRun' in text_run:
                        content += text_run['textRun']['content']
        return content
    except Exception as e:
        st.write(f"Error accessing Google Doc content: {e}")
        return ""

def get_sheet_content(sheet_id):
    try:
        sheet = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheet_content = ""
        for sheet in sheet['sheets']:
            sheet_name = sheet['properties']['title']
            result = sheets_service.spreadsheets().values().get(spreadsheetId=sheet_id, range=sheet_name).execute()
            values = result.get('values', [])
            for row in values:
                sheet_content += ' '.join(row) + "\n"
        return sheet_content
    except Exception as e:
        st.write(f"Error accessing Google Sheet content: {e}")
        return ""

def get_slide_content(slide_id):
    try:
        presentation = slides_service.presentations().get(presentationId=slide_id).execute()
        content = ""
        for slide in presentation.get('slides', []):
            for element in slide.get('pageElements', []):
                if 'shape' in element and 'text' in element['shape']:
                    for text_run in element['shape']['text']['textElements']:
                        if 'textRun' in text_run:
                            content += text_run['textRun']['content']
        return content
    except Exception as e:
        st.write(f"Error accessing Google Slide content: {e}")
        return ""

# Testing retrieval of selected files
selected_docs = [doc for doc in docs if doc['name'] in selected_docs_names]
selected_sheets = [sheet for sheet in sheets if sheet['name'] in selected_sheets_names]
selected_slides = [slide for slide in slides if slide['name'] in selected_slides_names]

doc_contents = [get_document_content(doc['id']) for doc in selected_docs]
sheet_contents = [get_sheet_content(sheet['id']) for sheet in selected_sheets]
slide_contents = [get_slide_content(slide['id']) for slide in selected_slides]

# Combine contents for querying or further processing
all_contents = doc_contents + sheet_contents + slide_contents
st.write("Combined content for selected files:", all_contents)
