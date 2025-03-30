from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
from werkzeug.utils import secure_filename

import os

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


import base64
from google import genai
from google.genai import types



def generate(filename, prompt):
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    files = [
        # Please ensure that the file is available in local system working direrctory or change the file path.
        client.files.upload(file=filename),
    ]
    model = "gemini-2.0-flash"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(
                    file_uri=files[0].uri,
                    mime_type=files[0].mime_type,
                ),
                types.Part.from_text(text=prompt),
            ],
        ),  
    ]
    generate_content_config = types.GenerateContentConfig(
        response_mime_type="text/plain",
    )

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )
    print(response)
    return response.text

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files():    # uploads
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if allowed_file(filename):
            files.append(filename)
            print(filename)
    files.sort(reverse=True)
    return files


@app.route('/')
def index():
    files = get_files()
    return render_template('index.html', files=files)

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio data')
        return redirect(request.url)
    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file:
        # filename = secure_filename(file.filename)
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        #
        #
        # Modify this block to call the speech to text API
        # Save transcript to same filename but .txt
        #
        #

        prompt = """
        Please provide an exact trascript for the audio, followed by sentiment analysis.

        Your response should follow the format:

        Text: USERS SPEECH TRANSCRIPTION

        Sentiment Analysis: positive|neutral|negative
        """
        text = generate(file_path, prompt)
        f = open(file_path+'.txt', 'w')
        f.write(text)
        f.close()


    return redirect('/') #success

# @app.route('/upload/<filename>')
# def get_file(filename):
#     return send_file(filename)


@app.route('/script.js',methods=['GET'])
def scripts_js():
    return send_file('./script.js')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    app.run(debug=True)
