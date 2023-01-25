from main import PhotoFormCreator
from flask import Flask
from markupsafe import escape

app = Flask(__name__)

@app.route('/')
def hello_world():
    return "<p>hello wurld</p>"

@app.route("/form/<form_id>")
def create_form(form_id):
    form_id_esc = escape(form_id)
    photo_form = PhotoFormCreator(form_id_esc)
    photo_form.upload_files()
    new_form_id = photo_form.create_form()
    return f"<p>You passed in form Id {form_id_esc}.</p>" \
        f"<p>Uploaded {len(photo_form.uploaded_files)} files</p>" \
        f"<p>Created form {new_form_id}</p>"



