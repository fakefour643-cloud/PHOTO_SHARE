import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

FOLDER_ID = '1uVnaQZS9p-9XhfbcuE4pjKObPQ-rc1kG'
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    # Load credentials directly from environment variable or local file
    token_json_str = os.environ.get("GOOGLE_TOKEN_JSON")
    if token_json_str:
        info = json.loads(token_json_str)
        creds = Credentials.from_authorized_user_info(info, SCOPES)
    else:
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    return build('drive', 'v3', credentials=creds)

def upload_file_to_drive(file_path, filename):
    """Uploads a file to the 5 TB Drive folder and returns its web view/content link."""
    service = get_drive_service()
    
    file_metadata = {
        'name': filename,
        'parents': [FOLDER_ID]
    }
    media = MediaFileUpload(file_path, resumable=True)
    
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink, webContentLink'
    ).execute()
    
    return uploaded_file.get('id'), uploaded_file.get('webViewLink')
