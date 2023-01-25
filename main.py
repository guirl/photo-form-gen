import os
import logging
from pprint import pprint
import yaml
from google_workspace_utils.drive_exporter import GoogleDriveExporter
from google_workspace_utils.forms import GoogleForms
from glob import glob
import argparse
from itertools import islice
from copy import deepcopy


DEFAULT_FILE_EXTENSION = 'jpg'
DEFAULT_OPTIONS_PER_SECTION = 10
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/forms"]


def replace_deep(data, a, b):
    if isinstance(data, str):
        return data.replace(a, b)
    elif isinstance(data, dict):
        return {
            k: replace_deep(v, a, b)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [replace_deep(v, a, b) for v in data]
    else:
        # nothing to do?
        return data


class PhotoFormCreator():
    local_dir = ""
    form_template_id = ""
    drive_parent_id = ""
    name = ""
    file_ext = ""

    def __init__(self, args) -> None:
        if args.config:
            assert os.path.exists(args.config), f"Config file {args.config} not found."
            config_data = yaml.load(open(args.config, 'r').read(), yaml.Loader)
            self.local_dir = config_data.get('local_dir')
            self.form_template_id = config_data['form_template_id']
            self.drive_parent_id = config_data['drive_parent_id']
            self.drive_folder_id = config_data.get('drive_folder_id')
            self.name = config_data.get('project_name')
            self.file_ext = config_data['file_ext']
            self.options_per_section = config_data['options_per_section']
        else:
            self.local_dir = args.dir
            self.form_template_id = args.template
            self.drive_parent_id = args.parent
            self.drive_folder_id = args.folder
            self.name = args.name
            self.file_ext = args.ext
            self.options_per_section = args.options_per_section
        self.drive_exporter = GoogleDriveExporter(scopes=SCOPES)
        self.forms = GoogleForms(scopes=SCOPES)
        assert self.form_template_id, "Template form id must be provided."
        if self.local_dir:
            assert os.path.exists(self.local_dir), f"Local directory {self.local_dir} not found."
            assert self.drive_parent_id, "Drive parent id must be provided."
            self.name = self.name or self.local_dir.split('/')[-1]
        else:
            assert self.drive_folder_id, "Either local directory or Drive folder id must be provided."

    def process_images(self):
        if self.local_dir:
            self.upload_files()
        elif self.drive_folder_id:
            self.drive_folder_listing()
        # TODO: ensure the folder is set to anyone with the link can view

    def upload_files(self):
        # get all the files with the extension from the local directory
        filename_pattern = f"{self.local_dir}/*.{self.file_ext}"
        filenames = glob(filename_pattern)
        assert len(filenames) > 0, f"Couldn't find any files to upload from {filename_pattern}."
        # Create new folder
        # FIXME: parent folder ID is not correctly used
        self.folder_id = self.drive_exporter.create_folder(self.name, [self.drive_parent_id])
        # upload them all to drive
        self.drive_files = {}
        for filename in filenames:
            logging.info(f'processing file {filename}')
            file_id = self.drive_exporter.create_file(filename, [self.folder_id])
            self.drive_files[filename] = file_id
        logging.info(f"Uploaded {len(self.drive_files.keys())} files")
        logging.debug(f"File ids: {self.drive_files}")

    def drive_folder_listing(self):
        if not self.name:
            self.name = self.drive_exporter.get_folder_name(self.drive_folder_id)
        file_list = self.drive_exporter.list_files(f"mimeType='image/jpeg' and '{self.drive_folder_id}' in parents")
        self.folder_id = self.drive_folder_id
        self.drive_files = {
            file['name']: file['id']
            for file in file_list
        }
        logging.debug(f"Files: {self.drive_files}")

    def create_form(self):
        logging.info(f"Creating new form from template {self.form_template_id}")
        # Get form contents from template so they can be modified
        form = self.forms.get_form(self.form_template_id)
        logging.debug(f"Template form: {form}")
        # Replace sections of form that have templated fields with the supplied text
        for template, new_value in self.replace_text().items():
            form = replace_deep(form, template, new_value)
        ### add each file uploaded to drive to the form as an option
        # filename is the option text drive file is the thumbnail
        image_files = {
            filename.split('/')[-1]: self.static_image_url(file_id)
            for filename, file_id in self.drive_files.items()
        }
        checkbox_options = self.forms.build_checkbox_image_options(image_files)
        logging.debug(f"Checkbox options: {checkbox_options}")
        ## add new sections every so often to break up the form
        # iterate over the items in the form to locate the index of photo-choice section
        photo_section_index = 0
        photo_section = None
        for item in form['items']:
            if '~favorite photos~' in item['title']:
                photo_section = item
                break
            photo_section_index += 1
        if photo_section is None:
            raise Exception(f"Couldn't find photo section in form {form}")
        # Remove the id so that we don't end up with duplicate ids when we copy this
        photo_section.pop('itemId')
        # build new items list with sections inserted
        new_items = []
        grouped_checkbox_opts = self.grouper(checkbox_options, self.options_per_section)
        checkbox_groups = list(grouped_checkbox_opts)
        num_pages = len(checkbox_groups)
        for i, group in enumerate(checkbox_groups):
            logging.debug(f"Checkbox group {i}: {group}")
            new_question = self.forms.build_checkbox_question("Choose your favorites!", group)
            new_items.append(new_question)
            if num_pages > 1 and i < num_pages - 1:
                # Copy the existing photo section and add a page number
                new_photo_section = deepcopy(photo_section)
                new_photo_section['title'] += f" (Page {i + 2}/{num_pages})"
                new_items.append(new_photo_section)
        if num_pages > 1:
            photo_section['title'] += f" (Page 1/{num_pages})"
        # insert the checkbox options into the photo-choice section
        final_form_items = \
            form['items'][:photo_section_index + 1] + \
            new_items + \
            form['items'][photo_section_index + 1:]
        logging.debug(f"Final form items: {final_form_items}")
        # update the form with the new items
        new_form = form
        new_form['items'] = final_form_items
        self.new_form_id = self.forms.create_form(new_form)
        logging.info(f"Created new form! - {self.forms.form_url(self.new_form_id)}")
        # TODO: Put form in forms folder
        # TODO: get email notifications on new form responses
        # TODO: settings do not allow respondents from outside the domain to view the form

    def grouper(self, iterable, size):
        it = iter(iterable)
        while True:
            group = tuple(islice(it, None, size))
            if not group:
                break
            yield group

    def replace_text(self):
        return {
            '_SUBTITLE_': self.name,
            '_DATE_': 'tehdate', # todo: get date from file name
            '_DRIVE_FOLDER_LINK_': self.drive_exporter.get_folder_url(self.folder_id)
        }

    def static_image_url(self, file_id):
        return f"https://lh3.googleusercontent.com/d/{file_id}"


def main():
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser(description="Turn a local folder full of pictures into a Google Drive folder and a form with a question that includes a checkbox for every photo.")
    parser.add_argument('--config', '-c', type=str, nargs='?', default=None, 
                        help='Config file to load options from.')
    parser.add_argument('--dir', '-d', type=str, nargs='?', default=None, 
                        help="path to the directory to upload and attach enclosed files to the new form (can't be used with --folder)")
    parser.add_argument('--folder', '-f', type=str, nargs='?', default=None,
                        help="Google Drive folder already full of photos to attach to the new form (can't be used with --dir)")
    parser.add_argument('--template', '-t', type=str, nargs='?', default=None, 
                        help="id of the google form to copy as template")
    parser.add_argument('--parent', '-p', type=str, nargs='?', default=None, 
                        help='id of the google drive folder to become parent of the new folder')
    parser.add_argument('--name', '-n', type=str, nargs='?', default=None, 
                        help='name of the project/form subtitle/new folder to upload to')
    parser.add_argument('--ext', '-x', type=str, nargs='?', default=DEFAULT_FILE_EXTENSION, 
                        help='file extension of the files to be uploaded')
    parser.add_argument('--options-per-section', '-o', type=int, nargs='?', default=DEFAULT_OPTIONS_PER_SECTION,
                        help='number of photo checkbox options to include in each photo choice page of the form')
    args = parser.parse_args()

    photo_form = PhotoFormCreator(args)
    photo_form.process_images()
    photo_form.create_form()


if __name__ == '__main__':
    main()
