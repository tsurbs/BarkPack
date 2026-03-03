import os
import asyncio
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.tools.base import BaseTool

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
from email.message import EmailMessage

def get_google_creds():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    
    if not (client_id and client_secret and refresh_token) or "your_" in client_id:
        return None
        
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token"
    )

# --- GMAIL ---
class ReadGmailArgs(BaseModel):
    query: str = Field(description="Search query to filter emails (e.g. 'is:unread subject:invoice').", default="")
    max_results: int = Field(description="Maximum number of messages to return.", default=10)

class ReadGmailMessagesTool(BaseTool):
    name = "read_gmail_messages"
    description = "Read emails from the user's Gmail inbox using the Gmail API."
    args_schema = ReadGmailArgs
    
    async def run(self, args: ReadGmailArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Error: Google OAuth credentials not set."
        
        def _fetch():
            service = build('gmail', 'v1', credentials=creds)
            results = service.users().messages().list(userId='me', q=args.query, maxResults=args.max_results).execute()
            messages = results.get('messages', [])
            
            if not messages:
                return f"No messages found matching '{args.query}'."
                
            output = []
            for msg in messages:
                txt = service.users().messages().get(userId='me', id=msg['id'], format='metadata', metadataHeaders=['Subject', 'From', 'Date']).execute()
                headers = txt.get("payload", {}).get("headers", [])
                subj = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
                frm = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
                output.append(f"- ID: {msg['id']} | From: {frm} | Subject: {subj}")
            return f"Top messages matching '{args.query}':\n" + "\n".join(output)
            
        return await asyncio.to_thread(_fetch)

class SendGmailArgs(BaseModel):
    to: str = Field(description="Comma-separated list of recipient email addresses.")
    subject: str = Field(description="Email subject line.")
    body: str = Field(description="Body of the email. HTML is supported.")

class SendGmailTool(BaseTool):
    name = "send_gmail"
    description = "Send an email on behalf of the user using the Gmail API."
    args_schema = SendGmailArgs
    
    async def run(self, args: SendGmailArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Error: Google OAuth credentials not set."
        
        def _send():
            service = build('gmail', 'v1', credentials=creds)
            message = EmailMessage()
            message.set_content(args.body)
            message['To'] = args.to
            message['From'] = 'me'
            message['Subject'] = args.subject
            
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {'raw': encoded_message}
            send_message = service.users().messages().send(userId="me", body=create_message).execute()
            return f"Successfully sent email to {args.to}. Message ID: {send_message['id']}"
            
        return await asyncio.to_thread(_send)

class DraftGmailArgs(BaseModel):
    to: str = Field(description="Comma-separated list of recipient email addresses.")
    subject: str = Field(description="Email subject line.")
    body: str = Field(description="Body of the email. HTML is supported.")

class DraftGmailTool(BaseTool):
    name = "draft_gmail"
    description = "Create an email draft on behalf of the user using the Gmail API, without sending it."
    args_schema = DraftGmailArgs
    
    async def run(self, args: DraftGmailArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Error: Google OAuth credentials not set."
        
        def _draft():
            service = build('gmail', 'v1', credentials=creds)
            message = EmailMessage()
            message.set_content(args.body)
            message['To'] = args.to
            message['From'] = 'me'
            message['Subject'] = args.subject
            
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {'message': {'raw': encoded_message}}
            draft = service.users().drafts().create(userId="me", body=create_message).execute()
            return f"Successfully created email draft to {args.to}. Draft ID: {draft['id']}"
            
        return await asyncio.to_thread(_draft)

# --- CALENDAR ---
class CreateCalendarEventArgs(BaseModel):
    summary: str = Field(description="Event title or summary.")
    start_time: str = Field(description="ISO string for start time.")
    end_time: str = Field(description="ISO string for end time.")
    attendees: List[str] = Field(description="List of attendee email addresses.", default_factory=list)
    create_meet_link: bool = Field(description="If True, generates a Google Meet conferencing link.", default=True)

class CreateCalendarEventTool(BaseTool):
    name = "create_calendar_event"
    description = "Create a new meeting in Google Calendar, optionally with a Meet link."
    args_schema = CreateCalendarEventArgs
    
    async def run(self, args: CreateCalendarEventArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Error: Google credentials not configured."
        
        def _create_event():
            service = build('calendar', 'v3', credentials=creds)
            event = {
                'summary': args.summary,
                'start': {'dateTime': args.start_time},
                'end': {'dateTime': args.end_time},
                'attendees': [{'email': e} for e in args.attendees],
            }
            if args.create_meet_link:
                event['conferenceData'] = {
                    'createRequest': {'requestId': os.urandom(10).hex()}
                }
            created = service.events().insert(calendarId='primary', body=event, conferenceDataVersion=1).execute()
            return f"Event created: {created.get('htmlLink')}"
            
        return await asyncio.to_thread(_create_event)

class FindFreeBusyArgs(BaseModel):
    emails: List[str] = Field(description="List of emails to check availability for.")
    time_min: str = Field(description="ISO start time for the search window.")
    time_max: str = Field(description="ISO end time for the search window.")

class FindCalendarFreeBusyTool(BaseTool):
    name = "find_calendar_freebusy"
    description = "Query the free/busy status of multiple attendees to find a common meeting time."
    args_schema = FindFreeBusyArgs
    
    async def run(self, args: FindFreeBusyArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Error: Google credentials not set."
        
        def _freebusy():
            service = build('calendar', 'v3', credentials=creds)
            body = {
                "timeMin": args.time_min,
                "timeMax": args.time_max,
                "items": [{"id": e} for e in args.emails]
            }
            eventsResult = service.freebusy().query(body=body).execute()
            calendars = eventsResult.get('calendars', {})
            output = []
            for cal_id, cal_data in calendars.items():
                busy_slots = cal_data.get('busy', [])
                output.append(f"{cal_id}: {len(busy_slots)} busy slots.")
            return f"FreeBusy Query Results:\n" + "\n".join(output)
            
        return await asyncio.to_thread(_freebusy)

# --- DRIVE ---
class SearchDriveArgs(BaseModel):
    query: str = Field(description="The Drive API query (e.g. 'name contains \"Budget\" and mimeType=\"application/pdf\"').")

class SearchDriveFilesTool(BaseTool):
    name = "search_drive_files"
    description = "Search Google Drive for files and folders using Drive API query syntax."
    args_schema = SearchDriveArgs
    
    async def run(self, args: SearchDriveArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Error: Credentials not set."
        
        def _search():
            service = build('drive', 'v3', credentials=creds)
            results = service.files().list(q=args.query, pageSize=10, fields="files(id, name, mimeType)").execute()
            items = results.get('files', [])
            if not items: return f"No files found matching '{args.query}'."
            return f"Top Drive files:\n" + "\n".join([f"- {i['name']} ({i['id']})" for i in items])
            
        return await asyncio.to_thread(_search)

class ModifyDrivePermissionsArgs(BaseModel):
    file_id: str = Field(description="The Google Drive File ID.")
    email: str = Field(description="The email to grant access to.")
    role: str = Field(description="The role to grant ('reader', 'commenter', 'writer', 'owner').")

class ModifyDrivePermissionsTool(BaseTool):
    name = "modify_drive_permissions"
    description = "Share a Google Drive file or folder with a specific user."
    args_schema = ModifyDrivePermissionsArgs
    
    async def run(self, args: ModifyDrivePermissionsArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Error credentials missing."
        
        def _perms():
            service = build('drive', 'v3', credentials=creds)
            permission = {'type': 'user', 'role': args.role, 'emailAddress': args.email}
            service.permissions().create(fileId=args.file_id, body=permission, fields='id').execute()
            return f"Successfully granted '{args.role}' access to {args.email} on File {args.file_id}."
            
        return await asyncio.to_thread(_perms)

# --- DOCS & SHEETS ---
class CreateGoogleDocArgs(BaseModel):
    title: str = Field(description="The title of the new Google Doc.")
    body_text: str = Field(description="The textual content to insert into the document.")

class CreateGoogleDocTool(BaseTool):
    name = "create_google_doc"
    description = "Create a new Google Document and insert text using the Google Docs API."
    args_schema = CreateGoogleDocArgs
    
    async def run(self, args: CreateGoogleDocArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Credential error."
        
        def _create_doc():
            service = build('docs', 'v1', credentials=creds)
            document = service.documents().create(body={'title': args.title}).execute()
            doc_id = document.get('documentId')
            
            requests = [{'insertText': {'location': {'index': 1}, 'text': args.body_text}}]
            service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
            return f"Successfully created document '{args.title}': https://docs.google.com/document/d/{doc_id}"
            
        return await asyncio.to_thread(_create_doc)

class ReadGoogleDocArgs(BaseModel):
    document_id: str = Field(description="The ID of the Google Document to read.")

class ReadGoogleDocTool(BaseTool):
    name = "read_google_doc"
    description = "Read the text content of a Google Document."
    args_schema = ReadGoogleDocArgs
    
    async def run(self, args: ReadGoogleDocArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Credential error."
        
        def _read_doc():
            service = build('docs', 'v1', credentials=creds)
            document = service.documents().get(documentId=args.document_id).execute()
            
            content = document.get('body').get('content')
            text_content = ""
            for item in content:
                if 'paragraph' in item:
                    elements = item.get('paragraph').get('elements')
                    for element in elements:
                        if 'textRun' in element:
                            text_content += element.get('textRun').get('content')
            return f"Document Content:\n\n{text_content}"
            
        return await asyncio.to_thread(_read_doc)

class UpdateGoogleSheetArgs(BaseModel):
    spreadsheet_id: str = Field(description="The ID of the Google Sheet.")
    range: str = Field(description="A1 notation of the range to update (e.g. 'Sheet1!A1:B2').")
    values: List[List[str]] = Field(description="A 2D array of string values to insert.")

class UpdateGoogleSheetTool(BaseTool):
    name = "update_google_sheet"
    description = "Write data into a Google Sheet cell range."
    args_schema = UpdateGoogleSheetArgs
    
    async def run(self, args: UpdateGoogleSheetArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Credential error."
        
        def _sheet():
            service = build('sheets', 'v4', credentials=creds)
            body = {'values': args.values}
            result = service.spreadsheets().values().update(
                spreadsheetId=args.spreadsheet_id, range=args.range,
                valueInputOption="RAW", body=body).execute()
            return f"Successfully updated {result.get('updatedCells')} cells."
            
        return await asyncio.to_thread(_sheet)

class ReadGoogleSheetArgs(BaseModel):
    spreadsheet_id: str = Field(description="The ID of the Google Sheet.")
    range: str = Field(description="A1 notation of the range to read (e.g. 'Sheet1!A1:D10').")

class ReadGoogleSheetTool(BaseTool):
    name = "read_google_sheet"
    description = "Read data from a Google Sheet cell range."
    args_schema = ReadGoogleSheetArgs
    
    async def run(self, args: ReadGoogleSheetArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Credential error."
        
        def _read_sheet():
            service = build('sheets', 'v4', credentials=creds)
            result = service.spreadsheets().values().get(
                spreadsheetId=args.spreadsheet_id, range=args.range).execute()
            values = result.get('values', [])
            
            if not values:
                return "No data found."
                
            output = []
            for row in values:
                output.append(" | ".join(row))
            return f"Sheet Data:\n\n" + "\n".join(output)
            
        return await asyncio.to_thread(_read_sheet)

# --- EVENTS & ADMIN ---
class SubscribeWorkspaceEventsArgs(BaseModel):
    resource_url: str = Field(description="The API URL of the Chat Space, Drive Folder, or User to monitor.")
    event_types: List[str] = Field(description="List of CloudEvents to listen for (e.g. 'google.workspace.chat.message.v1.created').")

class SubscribeWorkspaceEventsTool(BaseTool):
    name = "subscribe_workspace_events"
    description = "Create a Pub/Sub event subscription to monitor real-time changes in Google Workspace."
    args_schema = SubscribeWorkspaceEventsArgs
    
    async def run(self, args: SubscribeWorkspaceEventsArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        # Note: Implementing true PubSub subscriptions dynamically is complex and requires setting up Cloud Pub/Sub topics.
        # This tool will just return a placeholder explaining this.
        return f"Warning: True event subscription requires a pre-configured Google Cloud Pub/Sub Topic and Push Endpoint. Mock: Subscribed to {args.resource_url} for events: {args.event_types}."

class ManageCloudIdentityGroupsArgs(BaseModel):
    group_email: str = Field(description="The email of the Cloud Identity Group.")
    user_email: str = Field(description="The email of the user to add/remove.")
    action: str = Field(description="'add' or 'remove'.")

class ManageCloudIdentityGroupsTool(BaseTool):
    name = "manage_cloud_identity_groups"
    description = "Add or remove a user from a Google Cloud Identity or Workspace Security Group."
    args_schema = ManageCloudIdentityGroupsArgs
    
    async def run(self, args: ManageCloudIdentityGroupsArgs, user: User, db: Optional[AsyncSession] = None) -> str:
        creds = get_google_creds()
        if not creds: return "Credential error."
        
        def _manage():
            service = build('cloudidentity', 'v1', credentials=creds)
            # Find group ID by email
            response = service.groups().lookup(groupKey={'id': args.group_email}).execute()
            group_name = response.get('name')
            if not group_name: return f"Could not find group {args.group_email}"
            
            if args.action == 'add':
                member = {'preferredMemberKey': {'id': args.user_email}, 'roles': [{'name': 'MEMBER'}]}
                service.groups().memberships().create(parent=group_name, body=member).execute()
                return f"Successfully added {args.user_email} to {args.group_email}."
            else:
                mb_response = service.groups().memberships().lookup(parent=group_name, memberKey={'id': args.user_email}).execute()
                mb_name = mb_response.get('name')
                if mb_name:
                    service.groups().memberships().delete(name=mb_name).execute()
                    return f"Successfully removed {args.user_email} from {args.group_email}."
                return f"User {args.user_email} not in group."
                
        return await asyncio.to_thread(_manage)
