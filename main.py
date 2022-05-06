from distutils.command.upload import upload
import os
import logging
import yaml
from google_workspace_utils.drive_exporter import GoogleDriveExporter
from glob import glob
import argparse


DEFAULT_FORM_ID = 'FIXME'
DEFAULT_DRIVE_PARENT_ID = 'ADDME'
DEFAULT_FILE_EXTENSION = 'jpg'


class PhotoFormCreator():

  def __init__(self, args) -> None:
    if args.config:
      assert os.path.exists(args.config), f"Config file {args.config} not found."
      config_data = yaml.load(open(args.config, 'r').read(), yaml.Loader)
      self.local_dir = config_data['local_dir']
      self.form_template_id = config_data['form_template_id']
      self.drive_parent_id = config_data['drive_parent_id']
      self.name = config_data.get('project_name')
      self.file_ext = config_data['file_ext']
    else:
      self.local_dir = args.dir
      self.form_template_id = args.template
      self.drive_parent_id = args.parent
      self.name = args.name
      self.file_ext = args.ext
    self.drive_exporter = GoogleDriveExporter()

  def create(self):
    # get all the files with the extension from the local directory
    filename_pattern = f"{self.local_dir}/*.{self.file_ext}"
    filenames = glob(filename_pattern)
    assert len(filenames) > 0, f"Couldn't find any files to upload from {filename_pattern}."
    # Create new folder
    folder_name = self.name or self.local_dir.split('/')[-1]
    folder_id = self.drive_exporter.create_folder(folder_name, self.drive_parent_id)
    # upload them all to drive
    uploaded_files = {}
    for filename in filenames:
      logging.info(f'processing file {filename}')
      file_id = self.drive_exporter.create_file(filename, [folder_id])
      uploaded_files[filename] = file_id
    logging.info(f"Uploaded {len(uploaded_files.keys())} files")
    logging.debug(f"File ids: {uploaded_files}")
    # create form
    self.create_form()

  def create_form(self):
    # copy form from template
    # replace placeholder question 
    # add each file uploaded to drive to the form as an option
      # filename is the option text
      # drive file is the thumbnail
    # add folder name to title of form
    pass



def main():
  logging.basicConfig(level=logging.DEBUG)
  parser = argparse.ArgumentParser(description="Turn a local folder full of pictures into a Google Drive folder and a form with a question that includes a checkbox for every photo.")
  parser.add_argument('--config', '-c', type=str, nargs='?', default=None, 
                      help='Config file to load options from.')
  parser.add_argument('--dir', '-d', type=str, nargs='?', default='.', 
                      help='path to the directory to upload and attach enclosed files to the new form')
  parser.add_argument('--template', '-t', type=str, nargs='?', default=DEFAULT_FORM_ID, 
                      help="id of the google form to copy as template")
  parser.add_argument('--parent', '-p', type=str, nargs='?', default=DEFAULT_DRIVE_PARENT_ID, 
                      help='id of the google drive folder to become parent of the new folder')
  parser.add_argument('--name', '-n', type=str, nargs='?', default=None, 
                      help='name of the project/form subtitle/new folder to upload to')
  parser.add_argument('--ext', '-x', type=str, nargs='?', default=DEFAULT_FILE_EXTENSION, 
                      help='file extension of the files to be uploaded')
  args = parser.parse_args()

  photo_form = PhotoFormCreator(args)
  photo_form.create()


if __name__ == '__main__':
  main()
