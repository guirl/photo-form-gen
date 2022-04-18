from connector import GoogleConnector, execute_request
from googleapiclient.http import MediaFileUpload
from mimetypes import guess_type


DEFAULT_PARENT_FOLDER_ID = "Oops, you didn't include a drive folder id in your config"


class GoogleDriveExporter:
    service = None
    pending_creates = []

    def __init__(self):
        self.init_google_drive()

    def init_google_drive(self):
        connector = GoogleConnector('drive', 'v3')
        self.service = connector.service()
        self.files = self.service.files()

    def create_folder(self, name, parents=[DEFAULT_PARENT_FOLDER_ID]):
        file_metadata = {
            # 'supportsAllDrives': 'true',
            # 'includeItemsFromAllDrives': 'true',
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': parents
        }
        request = self.files.create(body=file_metadata, fields='id')
        response = execute_request(request)
        return response.get('id')

    def create_file(self, file_path, parents):
        filename = file_path.split('/')[-1]
        file_metadata = {
            # 'supportsAllDrives': 'true',
            # 'includeItemsFromAllDrives': 'true',
            'name': filename,
            'parents': parents
        }
        mime_type = guess_type(file_path)[0]
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        request = self.files.create(body=file_metadata, media_body=media, fields='id')
        response = execute_request(request)
        return response.get('id')

    def upload_files_to_folder(self, folder_name, files_list, parents=[DEFAULT_PARENT_FOLDER_ID]):
        folder_id = self.create_folder(folder_name, parents)
        for file_path in files_list: # glob(files_path):
            file_id = self.create_file(file_path, [folder_id])
        return folder_id

    def get_folder_url(self, folder_id):
        return f"https://drive.google.com/drive/folders/{folder_id}"


def main():
    gdrive = GoogleDriveExporter()
    folder_name = 'test_folder'
    filenames = ['test.txt']
    folder_id = gdrive.upload_files_to_folder(folder_name, filenames)
    folder_url = gdrive.get_folder_url(folder_id)
    print(f"Folder uploaded: {folder_url}")


if __name__ == "__main__":
    main()
