import os
import logging
import argparse
import yaml
from google_workspace_utils.drive_exporter import GoogleDriveExporter


SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/forms"]


class GoogleDriveFolderEditorSwap:
    """
    Service class to perform the editor swap 
    """
    def __init__(self, args) -> None:
        
        ### get the parent folder id
        self.parent_folder_id : str = args.folder
        # if there's a config load it
        if args.config:
            assert os.path.exists(args.config), f"Config file {args.config} not found."
            config_data = yaml.load(open(args.config, 'r').read(), yaml.Loader)
            self.parent_folder_id = config_data['parent_folder_id']

        logging.debug(f"Looking for files in folder '{self.parent_folder_id}'")
        self.drive_exporter = GoogleDriveExporter(scopes=SCOPES)

    def get_folder_permissions(self, folder_id: str):
        """
        Find all the users who have access to this folder and return a dict of
        user id to permission level (viewer, commentor, editor, owner).

        Parameters
        ----------
        folder_id : str
            Google Drive id of the folder
        """
        permissions: dict[str, str] = {}
        # retrieve the permissions from GDrive API
        return permissions

    def get_subfolder_ids(self, parent_folder_id: str):
        """
        return a list of all the folder ids in a folder

        Parameters
        ----------
        parent_folder_id: str
            Google Drive id of the parent folder

        Returns: list[str]
        """
        assert parent_folder_id is not None, "Pass in a valid parent folder id"
        # iterate all the objects in the folder 
        query = "mimeType = 'application/vnd.google-apps.folder' and" \
            f" '{parent_folder_id}' in parents"
        file_ids = self.drive_exporter.list_files(query)
        # if they are of type folder add them to the list
        return file_ids

    def swap_editors(self):
        """
        Swap the editor of each folder

        Ensures: former editor should become a viewer

        Parameters
        ----------
        args : argparse args result object
            _description_
        """
        ### get the current state of the subfolders
        # find the subfolders of the parent id in our config
        subfolder_ids : list[str] = self.get_subfolder_ids(self.parent_folder_id)
        print(subfolder_ids)
        return 
        folder_access : dict[str, str] = {}
        for subfolder_id in subfolder_ids:
            # get the permissions on the folder
            folder_access[subfolder_id] = self.get_folder_permissions(subfolder_id)

        ### build the new permissions for each folder
        # all_editors = set

        ### assign the new permissions


    def notify_discord(self):
        raise NotImplemented("No one has connected this to discord yet lol")


def main():
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser(description="Swap the permissions on the subfolders of a Google Drive folder to randomize who has edit permissions.")
    parser.add_argument('--config', '-c', type=str, nargs='?', default=None, 
                        help='Config file to load options from.')
    parser.add_argument('--folder', '-f', type=str, nargs='?', default=None,
                        help="Google Drive folder already full of photos to attach to the new form (can't be used with --dir)")

    args = parser.parse_args()

    # instantiate service class
    drive_folder_swapper = GoogleDriveFolderEditorSwap(args)
    # do the thing
    drive_folder_swapper.swap_editors()
    # notify a discord channel
    drive_folder_swapper.notify_discord()


if __name__ == '__main__':
    main()
