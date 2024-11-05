import os
import streamlit as st
from googleapiclient.discovery import build
from google.oauth2 import service_account
from openai import OpenAI
from datetime import datetime
import base64
import httpx

# Set up OpenAI and Google API client
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

# 1. List all files accessible by the service account for debugging
def list_all_files():
    results = drive_service.files().list(fields="files(id, name, mimeType)").execute()
    items = results.get('files', [])
    
    # Display all accessible files with their mimeTypes
    st.write("All accessible files in Google Drive:")
    if items:
        for item in items:
            st.write(f"File Name: {item['name']}, ID: {item['id']}, MimeType: {item['mimeType']}")
    else:
        st.write("No files found accessible to this service account.")
    return items

# Call the function to list all files in Google Drive
all_files = list_all_files()

# 2. Attempt to access a specific Google Slides file directly by its ID
# Replace 'YOUR_GOOGLE_SLIDES_FILE_ID' with the actual file ID for the Slide you want to test
TEST_SLIDE_ID = '1280uvub1-IaOoa9aYEYloWePjlTvlY1BNDHGUnUGtAc'

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
        st.write("Successfully accessed Google Slides content:")
        st.write(content)
    except Exception as e:
        st.write(f"Failed to access Google Slides content. Error: {e}")

# Try fetching content from a specific Google Slides file
st.write("Testing access to a specific Google Slides file by ID:")
get_slide_content(TEST_SLIDE_ID)
