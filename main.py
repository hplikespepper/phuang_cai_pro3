from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory
from werkzeug.utils import secure_filename

import os

app = Flask(__name__)

# Configure upload folder
UPLOAD_AUDIO_FOLDER = 'uploads' 
UPLOAD_BOOK_FOLDER = 'books'    
UPLOAD_TTS_FOLDER = 'tts'

ALLOWED_AUDIO_EXTENSIONS = {'wav'}
ALLOWED_BOOK_EXTENSIONS = {'pdf'}

app.config['UPLOAD_AUDIO_FOLDER'] = UPLOAD_AUDIO_FOLDER
app.config['UPLOAD_BOOK_FOLDER'] = UPLOAD_BOOK_FOLDER
app.config['UPLOAD_TTS_FOLDER'] = UPLOAD_TTS_FOLDER

os.makedirs(UPLOAD_AUDIO_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_BOOK_FOLDER, exist_ok=True)
os.makedirs(UPLOAD_TTS_FOLDER, exist_ok=True)


import base64
from google import genai
from google.genai import types
from google.cloud import texttospeech_v1

text_to_speech_client = texttospeech_v1.TextToSpeechClient()

def allowed_audio(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_AUDIO_EXTENSIONS

def allowed_book(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_BOOK_EXTENSIONS


# tts
def sample_synthesize_speech(text=None, ssml=None):
    input = texttospeech_v1.SynthesisInput()
    if ssml:
        input.ssml = ssml
    else:
        input.text = text

    voice = texttospeech_v1.VoiceSelectionParams()
    voice.language_code = "en-UK"
    # voice.ssml_gender = "MALE"

    audio_config = texttospeech_v1.AudioConfig()
    audio_config.audio_encoding = "LINEAR16"

    request = texttospeech_v1.SynthesizeSpeechRequest(
        input=input,
        voice=voice,
        audio_config=audio_config,
    )

    response = text_to_speech_client.synthesize_speech(request=request)

    return response.audio_content


# def generate(filename, prompt):
#     client = genai.Client(
#         api_key=os.environ.get("GEMINI_API_KEY"),
#     )

#     files = [
#         # Please ensure that the file is available in local system working direrctory or change the file path.
#         client.files.upload(file=filename),
#     ]
#     model = "gemini-2.0-flash"
#     contents = [
#         types.Content(
#             role="user",
#             parts=[
#                 types.Part.from_uri(
#                     file_uri=files[0].uri,
#                     mime_type=files[0].mime_type,
#                 ),
#                 types.Part.from_text(text=prompt),
#             ],
#         ),  
#     ]
#     generate_content_config = types.GenerateContentConfig(
#         response_mime_type="text/plain",
#     )

#     response = client.models.generate_content(
#         model=model,
#         contents=contents,
#         config=generate_content_config,
#     )
#     print(response)
#     return response.text

def generate(pdf_path, audio_path, prompt):
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    pdf_file = client.files.upload(file=pdf_path)
    audio_file = client.files.upload(file=audio_path)
       
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(file_uri=pdf_file.uri, mime_type=pdf_file.mime_type),
                types.Part.from_uri(file_uri=audio_file.uri, mime_type=audio_file.mime_type),
                types.Part.from_text(text=prompt),
            ],
        )
    ]
    generate_content_config = types.GenerateContentConfig(
        response_mime_type="text/plain",
    )
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=contents,
        config=generate_content_config,
    )
    return response.text


# book
def get_books():
    books = []
    for filename in os.listdir(UPLOAD_BOOK_FOLDER):
        if allowed_book(filename):
            books.append(filename)
    books.sort(reverse=True)
    return books

def get_audio_questions():
    audios = []
    for filename in os.listdir(UPLOAD_AUDIO_FOLDER):
        if allowed_audio(filename):
            audios.append(filename)
    audios.sort(reverse=True)
    return audios

def get_tts_files():
    files = []
    for filename in os.listdir(UPLOAD_TTS_FOLDER):
        if allowed_audio(filename):
            files.append(filename)
    files.sort(reverse=True)
    return files

@app.route('/')
def index():
    books = get_books()
    questions = get_audio_questions()
    tts_files = get_tts_files()
    return render_template('index.html', books=books, questions=questions, tts_files=tts_files)


@app.route('/upload_book', methods=['POST'])
def upload_book():
    if 'book_file' not in request.files:
        flash('No book file provided')
        return redirect(request.url)
    file = request.files['book_file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_book(file.filename):
        filename = secure_filename(file.filename)
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p_") + filename
        file_path = os.path.join(app.config['UPLOAD_BOOK_FOLDER'], filename)
        file.save(file_path)
    return redirect('/')

@app.route('/upload', methods=['POST'])
def upload_question():
    if 'audio_data' not in request.files:
        flash('No audio data provided')
        return redirect(request.url)
    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    if file and allowed_audio(file.filename):
        audio_filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        audio_path = os.path.join(app.config['UPLOAD_AUDIO_FOLDER'], audio_filename)
        file.save(audio_path)
        
        books = get_books()
        if not books:
            flash('No book uploaded. Please upload a book first.')
            return redirect('/')
        
        book_filename = books[0]
        pdf_path = os.path.join(app.config['UPLOAD_BOOK_FOLDER'], book_filename)
        
        prompt = "Answer the user's query in the audio file based on the pdf book"

        answer_text = generate(pdf_path, audio_path, prompt)
        
        audio_answer = sample_synthesize_speech(text=answer_text)
        tts_filename = 'tts_' + datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        tts_path = os.path.join(app.config['UPLOAD_TTS_FOLDER'], tts_filename)
        with open(tts_path, 'wb') as f:
            f.write(audio_answer)

        text_file = tts_path + '.txt'
        with open(text_file, 'w') as f:
            f.write(answer_text)

    return redirect('/')

@app.route('/books/<filename>')
def uploaded_book(filename):
    return send_from_directory(app.config['UPLOAD_BOOK_FOLDER'], filename)

@app.route('/uploads/<filename>')
def uploaded_audio(filename):
    return send_from_directory(app.config['UPLOAD_AUDIO_FOLDER'], filename)

@app.route('/tts/<filename>')
def tts_audio(filename):
    return send_from_directory(app.config['UPLOAD_TTS_FOLDER'], filename)


@app.route('/script.js',methods=['GET'])
def scripts_js():
    return send_file('./script.js')

# @app.route('/uploads/<filename>')
# def uploaded_file(filename):
#     return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    app.run(debug=True)
