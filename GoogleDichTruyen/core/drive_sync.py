import os
import mimetypes
from .config import DRIVE_SCOPES, DRIVE_TOKEN_FILE

try:
	from google.oauth2.credentials import Credentials
	from googleapiclient.discovery import build
	from googleapiclient.errors import HttpError
	from googleapiclient.http import MediaFileUpload
	from google_auth_oauthlib.flow import InstalledAppFlow
	from google.auth.transport.requests import Request
except ImportError:
	Credentials = None
	build = None
	HttpError = None
	MediaFileUpload = None
	InstalledAppFlow = None
	Request = None


def ensure_drive_dependencies() -> bool:
	return all([Credentials, build, MediaFileUpload, InstalledAppFlow, Request])


def get_drive_credentials(credentials_path: str, token_path: str):
	if not credentials_path or not os.path.isfile(credentials_path):
		raise FileNotFoundError("Không tìm thấy file credentials Google Drive.")

	creds = None
	if token_path and os.path.exists(token_path):
		creds = Credentials.from_authorized_user_file(token_path, DRIVE_SCOPES)

	if not creds or not creds.valid:
		if creds and creds.expired and creds.refresh_token:
			creds.refresh(Request())
		else:
			flow = InstalledAppFlow.from_client_secrets_file(credentials_path, DRIVE_SCOPES)
			creds = flow.run_local_server(port=0)
		if token_path:
			with open(token_path, "w", encoding="utf-8") as token_file:
				token_file.write(creds.to_json())

	return creds


def upload_file_to_drive(file_path: str, credentials_path: str, folder_id: str = "", token_path: str = DRIVE_TOKEN_FILE) -> tuple[str, str]:
	if not ensure_drive_dependencies():
		raise RuntimeError("Thiếu thư viện Google Drive API.")
	if not file_path or not os.path.isfile(file_path):
		raise FileNotFoundError("Không tìm thấy file output để upload.")

	creds = get_drive_credentials(credentials_path, token_path)
	service = build("drive", "v3", credentials=creds)
	mime_type, _ = mimetypes.guess_type(file_path)
	media = MediaFileUpload(file_path, mimetype=mime_type or "application/octet-stream", resumable=True)
	metadata = {"name": os.path.basename(file_path)}
	if folder_id:
		metadata["parents"] = [folder_id]

	result = service.files().create(body=metadata, media_body=media, fields="id,name,webViewLink").execute()
	file_id = result.get("id", "")
	web_link = result.get("webViewLink") or (f"https://drive.google.com/file/d/{file_id}/view" if file_id else "")
	return file_id, web_link
