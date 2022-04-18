import logging

# from google_drive import drive_exporter
from glob import glob
import argparse


DEFAULT_FORM_ID = 'FIXME'
DEFAULT_DRIVE_PARENT_ID = 'ADDME'
DEFAULT_FILE_EXTENSION = 'jpg'


class PhotoFormCreator():

  def __init__(self, config) -> None:
      self.local_dir = config.dir
      self.form_template_id = config.template
      self.drive_parent_id = config.parent
      self.name = config.name
      self.file_ext = config.ext

  def create(self):
    # get all the files from the folder
    filenames = glob(f"{self.local_dir}/*.{self.file_ext}")
    
    # upload them all to drive
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
  # TODO: Check for config file, add it as a source of defaults for these options, and/or add an option to pass a config file on the command line
  logging.basicConfig(level=logging.DEBUG)
  parser = argparse.ArgumentParser(description="Turn a local folder full of pictures into a Google Drive folder and a form with a question that includes a checkbox for every photo.")
  parser.add_argument('--dir', '-d', type=str, nargs='?', default='.', help='path to the directory to upload and attach to the new form')
  parser.add_argument('--template', '-t', type=str, nargs='?', default=DEFAULT_FORM_ID, help="id of the google form to copy as template")
  parser.add_argument('--parent', '-p', type=str, nargs='?', default=DEFAULT_DRIVE_PARENT_ID, help='id of the google drive folder to become parent of the new folder')
  parser.add_argument('--name', '-n', type=str, nargs='?', default=None, help='name of the project/form subtitle/new folder to upload to')
  parser.add_argument('--ext', '-x', type=str, nargs='?', default=DEFAULT_FILE_EXTENSION, help='file extension of the files to be uploaded')
  args = parser.parse_args()

  photo_form = PhotoFormCreator(args)
  photo_form.create()


if __name__ == '__main__':
  main()