"""
Shared Google Sheets queue writer for all marketing agents.
Agents write draft outreach here; human reviews before sending.
"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_sheet(sheet_id: str, worksheet_name: str = "Queue"):
    creds_path = os.environ.get("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON", "")
    if not creds_path:
        raise RuntimeError("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON not set. See CREDENTIALS.md.")
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    try:
        return sheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=worksheet_name, rows=1000, cols=20)


def append_to_queue(sheet_id: str, row: list, worksheet_name: str = "Queue") -> None:
    """Append a row to the review queue sheet."""
    ws = get_sheet(sheet_id, worksheet_name)
    ws.append_row(row, value_input_option="USER_ENTERED")
