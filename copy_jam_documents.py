#!/usr/bin/env python3
"""
Delete all the files in a specified Google Drive folder.
Retrive a list of Conflence documents based upon a given label.
Download all the files with that label.
Upload those files to the Google Drive folder.
"""

import os
import unicodedata
import re
import mimetypes
from atlassian import Confluence
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload


def read_google_drive(scoped_credentials):
    """
    Reads contents of the first 50 Google drive items that the
    service acount has access to.
    """
    with build("drive", "v3", credentials=scoped_credentials) as service:
        results = service.files().list(pageSize=50).execute()
        items = results.get("files", [])
    if not items:
        print("No files found.")
        return

    return items


def upload_google_drive(filename, directory_id, scoped_credentials):
    """Upload a file to Google drive in a folder specified by directory_id"""

    with build("drive", "v3", credentials=scoped_credentials) as service:
        file_metadata = {"name": filename, "parents": [directory_id]}
        mime_type, _ = mimetypes.guess_type(filename)
        media = MediaFileUpload(filename, mimetype=mime_type)

        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )

        print(f'File ID: {file.get("id")}')

    return file.get("id")


def delete_from_google_drive(file_id, credentials):
    """Delete a file specified by ID from Google drive"""

    with build("drive", "v3", credentials=credentials) as service:
        service.files().delete(fileId=file_id).execute()
        print(f" deleted file ID {file_id}")

    return


def slugify(value):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert spaces or repeated dashes to single dashes.
    Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = re.sub(r"[^\w\s-]", "", value.lower())

    return re.sub(r"[-\s]+", "-", value).strip("-_")


def main():
    """
    The main program
    """
    # confluence account and permissions
    jira_domain = os.getenv("CONFLUENCE_DOMAIN")
    jira_token = os.getenv("JIRA_TOKEN")
    jira_user = os.getenv("JIRA_USER")
    confluence_label = os.getenv("CONFLUENCE_LABEL", "jam")
    # Google drive directory ID must be given permission for service account to write
    directory_id = os.getenv(
        "GOOGLE_DRIVE_FOLDER_ID", "1HsnsarPvc7UyD-fgvCcdx_Zm9FBhv4mM"
    )

    assert jira_domain, "CONFLUENCE_DOMAIN not set as environmental variable"
    assert jira_token, "JIRA_TOKEN not set as environmental variable"
    assert jira_user, "JIRA_USER not set as environmental variable"
    assert confluence_label, "CONFLUENCE_LABEL not set as environmental variable"

    ## google Drive account and permission
    scopes = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.appdata",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
    ]
    credentials = service_account.Credentials.from_service_account_file(
        "credentials.json"
    ).with_scopes(scopes)

    confluence = Confluence(
        url=f"https://{jira_domain}.atlassian.net",
        username=jira_user,
        password=jira_token,
        api_version="cloud",
    )

    pages = confluence.get_all_pages_by_label(
        label=confluence_label,
        start=0,
        limit=50,
    )

    drive_files = list(
        filter(
            lambda x: x["mimeType"] != "application/vnd.google-apps.folder",
            read_google_drive(credentials),
        )
    )
    for drive_file in drive_files:
        delete_from_google_drive(drive_file["id"], credentials)

    for page in pages:
        content = confluence.get_page_as_pdf(page["id"])
        title = slugify(page["title"])
        with open("/tmp/" + title + ".pdf", "wb") as pdf_file:
            pdf_file.write(content)
            print("Downloaded " + title)
            upload_google_drive("/tmp/" + title + ".pdf", directory_id, credentials)


if __name__ == "__main__":
    main()
