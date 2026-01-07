# Create a social media post with a caption, photos, and fonts using Google Drive and LLM API

import os
import random
import re
from datetime import datetime
from mimetypes import guess_type

import logging

from PIL import Image, ImageDraw, ImageFont

from google_workspace_utils import GoogleDriveExporter
import json

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly"
]


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


# Class to define create and manage a social media post
class SocialMediaPost:

    def __init__(self, config):
        """
        Initialize the SocialMediaPost with the provided configuration.
        
        :param config: Configuration dictionary containing event info, social media post info, photos info, and font info.
        """
        self.config = config
        # Ensure that all required keys are present in the configuration
        required_keys = [
            'event_info', 
            'social_media_info', 
            'photos_info', 
            'font_info'
        ]   
        # event info - date time, location, tagline, title, description, etc.
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required configuration key: {key}")  
        self.event_info = config.get('event_info', {})
        self.social_media_info = config.get('social_media_info', {})
        self.photos_info = config.get('photos_info', {})
        self.font_info = config.get('font_info', {})
        self.drive = GoogleDriveExporter(scopes=SCOPES)
       
        # Validate the configuration
        self.validate_config()
        
        # Initialize the LLM API client with the provided configuration
        self.llm_api_client = {
            'model': self.social_media_info.get('model', ''),
            'temperature': self.social_media_info.get('temperature', 0.7),
            'max_tokens': self.social_media_info.get('max_tokens', 150),
            'api_key': self.social_media_info.get('api_key', ''),
            'api_url': self.social_media_info.get('api_url', ''),
            'api_headers': self.social_media_info.get('api_headers', {}),
            'api_params': self.social_media_info.get('api_params', {}),
            'api_timeout': self.social_media_info.get('api_timeout', 30)
        }
        
        # Load the photos from the Google Drive folder
        self.photos = self.scan_drive_folder(self.photos_info['photos_folder_id'])
        
        if not self.photos:
            raise ValueError("No photos found in the specified folder.")
        # Load the fonts from the specified folder
        self.fonts = self.load_fonts()
        # Initialize the output object
        self.social_media_info['output'] = []
        
        
    # Check all the required configuration is present
    def validate_config(self):
        # check the configuration (received from a POST or config file)
        # llm api info - model, temperature, max tokens, etc.
        if 'model' not in self.social_media_info:
            raise ValueError("Missing required configuration key: model")
        if 'temperature' not in self.social_media_info:
            raise ValueError("Missing required configuration key: temperature")
        if 'max_tokens' not in self.social_media_info:
            raise ValueError("Missing required configuration key: max_tokens")
        if 'api_key' not in self.social_media_info:
            raise ValueError("Missing required configuration key: api_key")
        if 'api_url' not in self.social_media_info:
            raise ValueError("Missing required configuration key: api_url")
        if 'api_headers' not in self.social_media_info:
            raise ValueError("Missing required configuration key: api_headers")
        if 'api_params' not in self.social_media_info:
            raise ValueError("Missing required configuration key: api_params")
        if 'api_timeout' not in self.social_media_info:
            raise ValueError("Missing required configuration key: api_timeout")
        # social media post info - hashtags, target sizes, caption, etc.
        if 'target_sizes' not in self.social_media_info:
            raise ValueError("Missing required configuration key: target_sizes")
        if 'hashtags' not in self.social_media_info:
            raise ValueError("Missing required configuration key: hashtags")
        if 'caption' not in self.social_media_info:
            raise ValueError("Missing required configuration key: caption")
        if 'past_captions' not in self.social_media_info:
            raise ValueError("Missing required configuration key: past_captions")
        if 'photos_per_size' not in self.social_media_info: 
            raise ValueError("Missing required configuration key: photos_per_size")
        # discord channel info - channel id, etc.
        if 'discord_channel_id' not in self.social_media_info:
            raise ValueError("Missing required configuration key: discord_channel_id")
        # photos info - Local photo parent folder, with subfolders for each target size
        if 'photos_folder_id' not in self.photos_info:
            raise ValueError("Missing required configuration key: photos_folder_id")
        if 'output_folder' not in self.photos_info:
            raise ValueError("Missing required configuration key: output_folder")
        # Ensure that the output folder exists
        if not os.path.exists(self.photos_info['output_folder']):
            os.makedirs(self.photos_info['output_folder'])
        # temp download folder for photos inside output folder
        self.photos_info['temp_download_folder'] = os.path.join(self.photos_info['output_folder'], 'temp_download')
        # Ensure that the temp download folder exists
        if not os.path.exists(self.photos_info['temp_download_folder']):
            os.makedirs(self.photos_info['temp_download_folder'])
        # font info - Local font parent folder, with title/ and subtitle/ subfolders
        if 'font_folder' not in self.font_info:
            raise ValueError("Missing required configuration key: font_folder")
        # Ensure that the event info contains all necessary details
        if 'date' not in self.event_info:
            raise ValueError("Missing required event info: date")
        if 'location' not in self.event_info:
            raise ValueError("Missing required event info: location")
        if 'tagline' not in self.event_info:
            raise ValueError("Missing required event info: tagline")
        if 'title' not in self.event_info:
            raise ValueError("Missing required event info: title")
        if 'description' not in self.event_info:
            raise ValueError("Missing required event info: description")
        
             
        self.drive_cache_file = self.photos_info.get('drive_cache_file', 'config/drive_photos_cache.json')
        # Ensure that the drive cache file exists
        if not os.path.exists(self.drive_cache_file):
            with open(self.drive_cache_file, 'w') as f:
                json.dump({}, f)

        # Validate the event info
        if not self.event_info:
            raise ValueError("Event info is required to create a social media post.")


    # Create the post based on the provided configuration
    def create_post(self):
        # Construct the prompt for the LLM API to generate a caption for the post
        prompt = f"Create a social media post caption for the event '{self.event_info['title']}' happening on {self.event_info['date']} at {self.event_info['location']}. " \
                 f"Include the tagline '{self.event_info['tagline']}' and a description: {self.event_info['description']}. " \
                 f"Use the following hashtags: {', '.join(self.social_media_info['hashtags'])}." \
                 f"Use the following examples to inspire the caption: {self.social_media_info['past_captions']}."
        
        # Create a caption for the post by calling LLM API 
        caption = self.call_llm_api(prompt)
        
        # Choose a title font and subtitle font for the image text by random selection from the configured font folder
        title_font = self.select_random_font('title')
        subtitle_font = self.select_random_font('subtitle')
        
        # Iterate through the target sizes for output images
        for target_size in self.social_media_info['target_sizes']:

            # repeat for the number of photos configured for the target size
            for _ in range(self.social_media_info['photos_per_size']):
                
                # Select a random photo from the set of photos with the target size
                photo = self.select_random_photo(target_size)
                
                if not photo:
                    logging.error(f"No photos found for target size: {target_size}. Skipping this size.")
                    continue

                # Place text on the photo about the event 
                photo_with_text = self.add_text_to_photo(photo, caption, title_font, subtitle_font)
                
                # add the photo with text to the output folder
                self.save_photo(photo_with_text, target_size)
                
                # add results to the output object
                self.social_media_info['output'].append({
                    'photo': photo_with_text,
                    'caption': caption,
                    'target_size': target_size,
                    'title_font': title_font,
                    'subtitle_font': subtitle_font
                })
                
        return self.social_media_info['output']
    

    # Scan all the fonts for later random selection
    def load_fonts(self):
        """
        Load all fonts from the specified font folder.
        
        """
        
        # Check if the font folder exists
        if not os.path.exists(self.font_info['font_folder']):
            raise ValueError(f"Font folder {self.font_info['font_folder']} does not exist.")
        
        # Recursively load every font file in the font folder or its subfolders
        fonts = []
        for root, _, files in os.walk(self.font_info['font_folder']):
            for f in files:
                if f.lower().endswith(('.ttf', '.otf')):
                    fonts.append(os.path.join(root, f))
        if not fonts:
            raise ValueError(f"No font files found in {self.font_info['font_folder']}.")
        return fonts


    # Select a random font from the specified folder (title or subtitle)
    def select_random_font(self, font_type):
        """
        Select a random font from the specified font type (title or subtitle).
        
        :param font_type: Type of font to select ('title' or 'subtitle').
        :return: Path to the selected font file.
        """
        # if font_type not in self.fonts:
        #     raise ValueError(f"Invalid font type: {font_type}. Expected 'title' or 'subtitle'.")
        # if not self.fonts[font_type]:
        #     raise ValueError(f"No fonts available for type: {font_type}.")
        return random.choice(self.fonts)


    # Queue-based Drive folder traversal with caching
    def scan_drive_folder(self, root_folder_id):
        """
        Traverse the Drive folder tree using a queue, cache results to a file, and avoid redundant API calls.
        """
        # Set up cache file path and load cache
        cache_file = getattr(self, 'drive_cache_file', self.photos_info.get('drive_cache_file', 'drive_photos_cache.json'))
        if not hasattr(self, 'drive_cache'):
            self.drive_cache = self._load_drive_cache(cache_file)
            photos_metadata = []
            queue = [(root_folder_id, [])]  # Each item: (folder_id, path_so_far)

            while queue:
                folder_id, path_so_far = queue.pop(0)
                # Use cache if available
                if folder_id in self.drive_cache:
                    files = self.drive_cache[folder_id]
                else:
                    files = self.drive.list_files(f"'{folder_id}' in parents", order_by='name')
                self.drive_cache[folder_id] = files
                # Write cache after each new folder fetch
                self._write_drive_cache(cache_file, self.drive_cache)

                for item in files:
                    if item['mimeType'] == 'image/jpeg':
                        self.process_image(photos_metadata, path_so_far, item)
                    elif item['mimeType'] == 'application/vnd.google-apps.folder':
                        # Add folder to queue, updating the path
                        queue.append((item['id'], path_so_far + [item['name']]))

        return photos_metadata

    def process_image(self, photos_metadata, path_so_far, item):
        filename = item['name']
                        # Build the full path for this file
        full_path = "/".join(path_so_far + [filename])
        """ Paths are structured as follows:
        level 1: shows. ex: "20231128-30 launch week Other Folk Avl/Gvl", "20240425 Other Folk Gvl", "20250216 Other Folk - Distinct Cider Room"
        level 2: artist deliverables. ex: "20240822 Other Folk - Wandering Bard - artist assets", "20240125 Other Folk @ Wandering Bard - artist deliverables", "20250216 Other Folk @ Distinct Cider Room - artist deliverables", "20250518 Artist deliverables - Other Folk @ Carolina Bauernhaus"
        level 3: photos by photographer. ex: "Photos by James Wesley Nichols", "photos", "photos by Blushing Fox Creative"
        level 4: sizes (sometimes not present). ex: "Instagram feed post - square 1x1", "Instagram feed post - wide 5x4", "Instagram feed post - tall 4x5"
        the filename itself varies, so output the entire filename as the artist.
        """
        # Extract metadata from full_path using the detailed path structure
        # Example path: "20240425 Other Folk Gvl/20240425 Other Folk @ Wandering Bard - artist deliverables/Photos by James Wesley Nichols/Instagram feed post - square 1x1/photo.jpg"
        path_parts = full_path.split('/')
        # Initialize metadata fields
        date = performer = venue = photographer = size = None

        # Level 1: Show info (date, performer, maybe venue)
        if len(path_parts) > 0:
            show_info = path_parts[0]
            # Try to extract date and performer from the first part
            m = re.match(r'(\d{8})\s+(.+)', show_info)
            if m:
                date_str = m.group(1)
                performer = m.group(2).strip()
            try:
                date = datetime.strptime(date_str, '%Y%m%d')
            except Exception:
                date = None

        # Level 2: Artist deliverables (may contain venue)
        if len(path_parts) > 1:
            deliverable_info = path_parts[1]
            # Try to extract venue from deliverable_info
            m = re.search(r'@ ([^-]+)', deliverable_info)
            if m:
                venue = m.group(1).strip()

        # Level 3: Photographer
        if len(path_parts) > 2:
            photog_info = path_parts[2]
            m = re.search(r'photos? by (.+)', photog_info, re.IGNORECASE)
            if m:
                photographer = m.group(1).strip()
            else:
                photographer = photog_info.strip()

        # Level 4: Size (optional)
        if len(path_parts) > 3:
            size_info = path_parts[3]
            # Try to match to one of the DEFAULT_OUTPUT_SIZES titles
            for key, val in DEFAULT_OUTPUT_SIZES.items():
                if 'title' in val and val['title'].lower() in size_info.lower():
                    size = key
                    break
            if not size:
                size = size_info.strip()

            metadata = {
                'file_id': item['id'],
                'filename': filename,
                'full_path': full_path,
                'date': date,
                'performer': performer,
                'venue': venue,
                'photographer': photographer,
                'size': size,
                'mimeType': item['mimeType'],
                'parents': item.get('parents', [])
            }
            logging.debug(f"Processing photo: {full_path} with metadata: {metadata}")
        if metadata:
            logging.debug(f"Found photo metadata: {metadata}")
            photos_metadata.append(metadata)

    # Helper to load cache from file
    def _load_drive_cache(self, cache_file):
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    # Helper to write cache to file
    def _write_drive_cache(self, cache_file, cache_data):
        try:
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            logging.warning(f"Failed to write drive cache: {e}")
    
    # Select a random photo from the list of photos with the specified target size
    def select_random_photo(self, target_size):
        """
        Select a random photo from the list of photos with the specified target size.
        
        :param target_size: Target size for the photo (e.g., 'square', 'tall', 'wide', etc.).
        :return: Selected photo metadata.
        """
        # Filter photos based on the target size
        filtered_photos = [photo for photo in self.photos if photo['size'] == target_size]
        
        if not filtered_photos:
            logging.error(f"No photos found for target size: {target_size}.")
            return None
        
        # Select a random photo from the filtered list
        return random.choice(filtered_photos)
    
    # Add text to the photo about the event
    def add_text_to_photo(self, photo, caption, title_font, subtitle_font):
        """
        Add text to the photo about the event.
        
        :param photo: Photo metadata containing file ID and other details.
        :param caption: Caption text to add to the photo.
        :param title_font: Path to the title font file.
        :param subtitle_font: Path to the subtitle font file.
        :return: Photo with text added (this is a placeholder, actual implementation will depend on image processing library).
        """
        # construct target path to download the photo temporarily
        temp_photo_path = os.path.join(self.photos_info['temp_download_folder'], photo['filename'])
        
        # Use PIL to open the photo, add text, and return the modified photo
        photo_path = self.drive.download_file(photo['file_id'], temp_photo_path)
        if not photo_path:
            raise ValueError(f"Failed to download photo: {photo['filename']} with ID {photo['file_id']}.")
        # Open the photo using PIL
        img = Image.open(photo_path)
        draw = ImageDraw.Draw(img)
        # Define the position and size for the title and subtitle
        title_position = (50, 50)
        subtitle_position = (50, 150)

        # Load the title and subtitle fonts
        try:
            title_font = ImageFont.truetype(title_font, 50)
            subtitle_font = ImageFont.truetype(subtitle_font, 30)
        except IOError as e:
            raise ValueError(f"Failed to load font: {e}")
        
        # Add the title text to the photo
        draw.text(title_position, self.event_info['title'], font=title_font, fill="white")
        # Add the subtitle text to the photo
        draw.text(subtitle_position, caption, font=subtitle_font, fill="white")
        # Return the modified photo
        return img
    
    # open the svg template, find & replace all the substitution definitions, and write out the resulting SVG file
    def generate_svg(self, template_path, output_path, substitutions):
        # Open the SVG template file
        with open(template_path, 'r') as f:
            svg_template = f.read()
        
        # Replace all the substitution definitions in the SVG template
        for key, val in substitutions.items():
            svg_template = svg_template.replace(key, val)
        
        # Write the resulting SVG file
        with open(output_path, 'w') as f:
            f.write(svg_template)
    
    # Save the photo with the caption to the output folder
    def save_photo(self, photo, target_size):
        """
        Save the photo with the caption to the output folder.
        
        :param photo: Photo with text added (PIL Image object).
        :param target_size: Target size for the photo (e.g., 'square', 'tall', 'wide', etc.).
        """
        # Get the target size configuration
        size_config = DEFAULT_OUTPUT_SIZES.get(target_size, {})
        if not size_config:
            raise ValueError(f"Invalid target size: {target_size}.")
        
        # Create the output folder if it doesn't exist
        output_folder = self.photos_info['output_folder']
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        # Define the output file path
        output_file_path = os.path.join(output_folder, f"{self.event_info['title']}_{target_size}.jpg")
        
        # Resize the photo to the target size if specified
        if 'target_width' in size_config and 'target_height' in size_config:
            photo = photo.resize((size_config['target_width'], size_config['target_height']))
        
        # Save the photo to the output folder
        photo.save(output_file_path, format='JPEG')
        
        print(f"Photo saved to {output_file_path} with caption: {self.social_media_info['caption']}")
        # Return the output file path
        return output_file_path
    
    # TODO: Post the Drive folder with collection of photos on the Discord channel for review
    def post_to_discord(self):
        """
        Post the Drive folder with the collection of photos on the Discord channel for review.
        
        This method is a placeholder and should be implemented to send the photos and captions to the Discord channel.
        """
        # Placeholder for posting to Discord
        # You can use a Discord API client to send messages and files to a specific channel
        print("Posting to Discord channel for review...")
        # Example: discord_client.send_message(channel_id, "Review the photos", files=[photo_file])
        pass

    # Call the LLM API to generate a caption for the post
    def call_llm_api(self, prompt):
        """
        Call the LLM API to generate a caption for the post.
        
        :param prompt: Prompt text to send to the LLM API.
        :return: Generated caption text.
        """
        # Placeholder for calling the LLM API
        # You can use requests or any HTTP client to send a POST request to the LLM API
        print(f"Calling LLM API with prompt: {prompt}")
        
        # Example response from the LLM API (this should be replaced with actual API call)
        response = {
            'caption': "This is a generated caption for the social media post."
        }
        
        return response.get('caption', '')

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # Example configuration for the social media post
    config = {
        'event_info': {
            'date': '2025-09-21',
            'location': 'Carolina Bauernhaus',
            'tagline': "Fall Y'all",
            'title': 'Other Folk September',
            'description': "The leaves are changing but the music is still hot! Join us for an evening of folk, fun, and fall vibes at Other Folk on September 21. Featuring live performances, local art vendors, and craft beer. We hope you'll welcome fall with us in style!",
        },
        'social_media_info': {
            'model': 'gpt-3.5-turbo',
            'temperature': 0.7,
            'max_tokens': 150,
            'api_key': 'your_api_key_here',
            'api_url': 'https://api.example.com/llm',
            'api_headers': {'Authorization': 'Bearer your_api_key_here'},
            'api_params': {},
            'api_timeout': 30,
            'target_sizes': ['square', 'square', 'square'],
            'hashtags': ['#event', '#launchweek', '#exciting'],
            'caption': '',
            'past_captions': ['Excited for the launch!', 'Join us for a week of fun!'],
            'photos_per_size': 3,
            'discord_channel_id': 'your_discord_channel_id',
        },
        'photos_info': {
            # 'photo_folder': 'path/to/photo/folder',
            'photos_folder_id': '1tsx_iODhT7AeaYAwkGbVTpdI5ThHQREl',
            'output_folder': '/Users/cg/code/photo-form-gen/output_photos'
        },
        'font_info': {
            'font_folder': '/Users/cg/Library/Fonts',
        }
    
    }
    # Create a SocialMediaPost instance with the configuration
    social_media_post = SocialMediaPost(config)
    # Create the post
    social_media_post.create_post()
    

    # Post the Drive folder with the collection of photos on the Discord channel for review
    output = social_media_post.post_to_discord()
    print("Social media post created successfully:", output)

        
