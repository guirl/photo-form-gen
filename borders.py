import logging
import os
import re
from PIL import Image
from argparse import ArgumentParser
from glob import glob
from google_workspace_utils.drive_exporter import GoogleDriveExporter
import yaml


SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive.readonly", "https://www.googleapis.com/auth/forms"]
DEFAULT_OUTPUT_SIZES = {
    'square': {
        'title': "Instagram feed post - square 1x1",
        'target_width': 1080,
        'target_height': 1080
    },
    'tall': {
        'title': "Instagram feed post - tall 4x5",
        'target_width': 1080,
        'target_height': 1350
    },
    'wide': {
        'title': "Instagram feed post - wide 5x4",
        'target_width': 1080,
        'target_height': 864
    },
    'story': {
        'title': "Instagram story",
        'target_width': 1080,
        'target_height': 1920
    },
    'sdtv': {
        'title': "SD TV 640x480",
        'target_width': 640,
        'target_height': 480
    },
    'unpadded': {
        'title': "website, facebook - no padding, on Insta use only with images of same size",
    }
}
DEFAULT_DRIVE_PARENT_ID = None


class DeliverImages():
    def __init__(self, args):
        self.args = args
        self.config = self.load_config()
        if self.args.dir[-1] == '/':
            self.args.dir = self.args.dir[0:-1]
        if self.args.file is not None:
            self.images = [self.args.file]
        else:
            self.images = glob(f"{self.args.dir}/*.{self.args.input_ext}")
        assert len(self.images) > 0, f"Couldn't find any files to upload from {self.args.dir}."
        self.bkgd_color = tuple([int(color) for color in self.args.background.split(',')])
        assert len(self.bkgd_color) == 3, f"Background color {self.args.background} is not a triplet"
        logging.info(f'Background color: {self.bkgd_color}')
        self.output_size_configs = self.config.get('output_sizes', DEFAULT_OUTPUT_SIZES)
        self.output_sizes = ['square', 'tall', 'wide', 'story', 'unpadded'] # ['sdtv']
        logging.debug(f'Output sizes: {self.output_size_configs}')
        self.drive_parent_id = self.config.get('drive_parent_id', DEFAULT_DRIVE_PARENT_ID)
        self.watermark_path = self.args.watermark
        self.watermark_img: Image.Image = None
        self.watermark_scale_factor = self.args.scale_watermark
        if self.watermark_path is not None:
            logging.info(f"loading watermark image {self.watermark_path}")
            self.watermark_img: Image.Image = Image.open(self.watermark_path)
        else:
            logging.info("No watermark specified.")
        self.drive_exporter = GoogleDriveExporter(scopes=SCOPES)

    def load_config(self):
        # load from yaml file
        if self.args.config is not None:
            assert os.path.exists(self.args.config), f"Config file {self.args.config} not found."
            return yaml.load(open(self.args.config, 'r').read(), yaml.Loader)
        return {}

    def process_files(self):
        logging.info(f'Processing files from {self.args.dir}')
        for img_filename in self.images:
            logging.info(f'processing file {img_filename}')
            file_base = self.get_base_filename(img_filename)
            logging.debug(f'filename base: {file_base}')
            img = Image.open(img_filename)
            for output_size, sizing_info in self.output_size_configs.items():
                if output_size not in self.output_sizes:
                    logging.info(f"Size {output_size} is not enabled, skipping.")
                    continue
                # Scale the image if needed
                new_img = None
                if output_size == 'unpadded':
                    new_img = img
                else:
                    sizing_func = getattr(self, f'{output_size}_image')
                    new_img = sizing_func(img, sizing_info)
                if new_img is None:
                    logging.info(f'No output for image "{img_filename}" on size "{output_size}"')
                    continue
                # Add the watermark
                new_img = self.apply_watermark(new_img, sizing_info)
                # Write out the file
                output_dir = self.get_output_dir(output_size, create=True)
                new_filename = f"{file_base}-{output_size}.{self.args.output_ext}"
                new_file_path = os.path.join(output_dir, new_filename)
                logging.info(f'Saving new image to {new_file_path}')
                new_img.save(new_file_path, quality=self.args.quality)

    def upload_files(self):
        project_folder_name = self.args.dir.split('/')[-1]
        logging.info(f'Uploading files to Google Drive folder {project_folder_name}')
        self.project_folder_id = self.drive_exporter.find_or_create_subfolder(project_folder_name, self.drive_parent_id)
        self.drive_files = {}
        for output_size, sizing_info in self.output_size_configs.items():
            output_dir = self.get_output_dir(output_size)
            if output_dir is None:
                logging.debug(f'No output dir for size "{output_size}"')
                continue
            # get all the files with the extension from the local directory
            filename_pattern = f"{output_dir}/*.{self.args.output_ext}"
            filenames = glob(filename_pattern)
            if len(filenames) == 0:
                logging.warning(f"Couldn't find any files to upload from {filename_pattern}, skipping size {output_size}.")
                continue
            # Create new folder for this size in the project folder
            self.folder_id = self.drive_exporter.find_or_create_subfolder(sizing_info['title'], self.project_folder_id)
            # upload them all to drive
            for filename in filenames:
                logging.info(f'processing file {filename}')
                file_id = self.drive_exporter.create_file(filename, [self.folder_id])
                self.drive_files[filename] = file_id
        logging.info(f"Uploaded {len(self.drive_files.keys())} files")
        logging.debug(f"File ids: {self.drive_files}")

    def get_output_dir(self, output_size, create=False):
        if 'dir' in self.output_size_configs[output_size]:
            return self.output_size_configs[output_size]['dir']
        dir_name = self.output_size_configs[output_size]['title']
        output_dir = os.path.join(self.args.dir, dir_name)
        if not os.path.exists(output_dir):
            logging.info(f'/{dir_name} not found')
            if not create: return None
            logging.info(f'creating directory {output_dir}')
            os.makedirs(output_dir)
        self.output_size_configs[output_size]['dir'] = output_dir
        return output_dir

    def get_base_filename(self, img_filename):
        escaped_dir = re.escape(self.args.dir)
        pattern = rf'{escaped_dir}/(.*)\.{self.args.input_ext}$'
        match = re.match(pattern, img_filename)
        # print(f"filename: {img_filename}, dir: {self.args.dir}, pattern: {pattern} match: {match}")
        base = match.group(1)
        return base

    def apply_watermark(self, img: Image.Image, sizing_info: dict=None):
        if self.watermark_img is None:
            logging.warning(f"watermarking not enabled, skipping")
            return img
        wm_data = sizing_info.get('_wm_data')
        if wm_data is None:
            logging.debug(f"Calculating watermark size.")
            wm_width, wm_height = self.watermark_img.size
            width, height = img.size
            wm_opacity_pct = 0.65 # TODO add config
            new_width = width * self.watermark_scale_factor
            if new_width > wm_width:
                logging.warning(f"watermark width is {wm_width}, scaling it to image width {width} * scale factor {self.watermark_scale_factor} results in upscaling. Retaining original watermark size.")
                new_width = wm_width
            new_height = wm_height * (new_width / wm_width)
            x_padding = new_width * 0.5
            y_padding = new_height * 0.5
            wm_data = {
                'alpha': int(255 * wm_opacity_pct),
                'width': int(new_width),
                'height': int(new_height),
                'x': width - int(new_width + x_padding),
                'y': height - int(new_height + y_padding)
            }
            wm_data['scaled_img'] = self.watermark_img.resize((wm_data['width'], wm_data['height']))
            # wm_data['scaled_img'].putalpha(wm_data['alpha'])
            logging.debug(f"Calculated watermark data: {wm_data}")
            sizing_info['_wm_data'] = wm_data
        else:
            logging.debug(f"Found cached watermark data: {wm_data}")
        new_img = Image.new('RGBA', img.size, self.bkgd_color)
        new_img.paste(img)
        new_img.alpha_composite(wm_data['scaled_img'], (wm_data['x'], wm_data['y']))
        new_img = new_img.convert('RGB')
        return new_img

    def scale_image(self, img: Image.Image, sizing_info):
        width, height = img.size
        img_filename = img.filename
        if height > sizing_info['target_height'] or width > sizing_info['target_width']:
            scale = min(sizing_info['target_height'] / height, sizing_info['target_width'] / width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            img = img.resize((new_width, new_height))
            img.filename = img_filename
        return img

    def square_image(self, img, sizing_info=None):
        img = self.scale_image(img, sizing_info)
        # get the width and height of the image
        width, height = img.size
        if width > sizing_info['target_width']:
            logging.warning(f"Image {img.filename} is larger than {sizing_info['target_width']} wide")
            return None
        if width == height:
            logging.debug(f'Image {img.filename} is already square')
            return img
        elif width > height:
            logging.debug(f'Image {img.filename} is wider than tall')
            result = Image.new(img.mode, (width, width), self.bkgd_color)
            result.paste(img, (0, (width - height) // 2))
            return result
        else:
            logging.debug(f'Image {img.filename} is taller than wide')
            result = Image.new(img.mode, (height, height), self.bkgd_color)
            result.paste(img, ((height - width) // 2, 0))
            return result

    def tall_image(self, img, sizing_info=DEFAULT_OUTPUT_SIZES['tall']):
        img = self.scale_image(img, sizing_info)
        width, height = img.size

        if height == sizing_info['target_height']:
            # check to see if side padding is needed
            if width < sizing_info['target_width']:
                result = Image.new(img.mode, (sizing_info['target_width'], height), self.bkgd_color)
                result.paste(img, ((sizing_info['target_width'] - width) // 2, 0))
                return result
            elif width == sizing_info['target_height']:
                return img
            else:
                logging.warning(f"Skipping image {img.filename} - wider than tall, wouldn't look good as a tall image")
                return None
        else:
            logging.warning(f"Image {img.filename} is not {sizing_info['target_height']} tall, won't be able to use as a tall image")
            return None
    
    def wide_image(self, img, sizing_info=DEFAULT_OUTPUT_SIZES['wide']):
        img = self.scale_image(img, sizing_info)
        width, height = img.size
        if height > width: 
            logging.warning(f"Tall images are not supported for wide output, skipping {img.filename}")
            return None
        
        width_scale_factor = sizing_info['target_width'] / width
        height_scale_factor = sizing_info['target_height'] / height
        if width_scale_factor < height_scale_factor:
            scale_factor = width_scale_factor
        else:
            scale_factor = height_scale_factor
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        result = Image.new(img.mode, (sizing_info['target_width'], sizing_info['target_height']), self.bkgd_color)
        logging.debug(f"Scaling image {img.filename} from {width}x{height} to {new_width}x{new_height}, placing at {(sizing_info['target_width'] - new_width) // 2}x{(sizing_info['target_height'] - new_height) // 2}")
        result.paste(img, ((sizing_info['target_width'] - new_width) // 2, (sizing_info['target_height'] - new_height) // 2))
        return result
    
    def story_image(self, img, sizing_info=DEFAULT_OUTPUT_SIZES['story']):
        return self.tall_image(img, sizing_info)

    def sdtv_image(self, img, sizing_info=DEFAULT_OUTPUT_SIZES['sdtv']):
        return self.wide_image(img, sizing_info)


def main():
    logging.basicConfig(level=logging.DEBUG)
    parser = ArgumentParser(description="Take a folder full of photos and produce new photos with added borders to pad them to square.")
    parser.add_argument('--config', '-c', type=str, nargs='?', default=None,
                        help="Yaml config file to load options from.")
    parser.add_argument('--dir', '-d', type=str, nargs='?', default=None,
                        help="Path to the directory of photos to process.")
    parser.add_argument('--file', '-f', type=str, nargs='?', default=None,
                        help="Single filename to run on instead (exclusive of directory).")
    parser.add_argument('--input-ext', '-i', type=str, nargs='?', default='png',
                        help="File extension to look for.")
    parser.add_argument('--output-ext', '-o', type=str, nargs='?', default='jpg',
                        help="File extension for the type to output.")
    parser.add_argument('--background', '-b', type=str, nargs='?', default="255,255,255",
                        help="Background color to use for the padded image.")
    parser.add_argument('--quality', '-q', type=int, nargs='?', default=95,
                        help="Quality of the output image.")
    parser.add_argument('--watermark', '-w', type=str, nargs='?', default=None,
                        help="Path to a file to use for a watermark.")
    parser.add_argument('--scale-watermark', '-s', type=float, nargs='?', default=0.08,
                        help="Scale factor for the watermark.")
    args = parser.parse_args()
    assert args.dir is not None, "Must specify a directory to process."
    delivery = DeliverImages(args)
    delivery.process_files()
    delivery.upload_files()


if __name__ == '__main__':
    main()
