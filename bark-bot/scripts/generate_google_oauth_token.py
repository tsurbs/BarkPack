import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the file token.json.
# These scopes allow full access to Gmail, Calendar, Drive, and Docs/Sheets.
SCOPES = [
    'https://mail.google.com/',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets'
]

def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        print("Found existing token.json!")

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            print("Starting new OAuth flow. Please ensure 'credentials.json' is in this directory.")
            if not os.path.exists('credentials.json'):
                print("ERROR: 'credentials.json' not found.")
                print("1. Go to Google Cloud Console > APIs & Services > Credentials")
                print("2. Create an OAuth 2.0 Client ID (Desktop app).")
                print("3. Download the JSON and rename it to 'credentials.json' and place it in the bark-bot root folder.")
                return

            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print(f"Success! token.json has been created.")

    print("\n--- ACTION REQUIRED ---")
    print("Add the following properties to your .env file:\n")
    
    cred_dict = json.loads(creds.to_json())
    print(f"GOOGLE_CLIENT_ID={cred_dict.get('client_id')}")
    print(f"GOOGLE_CLIENT_SECRET={cred_dict.get('client_secret')}")
    print(f"GOOGLE_REFRESH_TOKEN={cred_dict.get('refresh_token')}")
    print(f"\nNote: Keep the GOOGLE_REFRESH_TOKEN secret. It grants perpetual access to the bot account.")

if __name__ == '__main__':
    main()
