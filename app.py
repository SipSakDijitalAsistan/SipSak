from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import random
import json
import torch
from model import NeuralNet
from nltk_utils import bag_of_words, tokenize
from gtts import gTTS
import os
import tempfile
import uuid
from googletrans import Translator
import logging
import speech_recognition as sr
from nltk.chat.util import Chat, reflections
from pydub import AudioSegment

app = Flask(__name__, static_folder='static', static_url_path='/static')
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Loglama ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with open('intents.json', 'r', encoding='utf-8') as json_data:
    intents = json.load(json_data)

FILE = "data.pth"
data = torch.load(FILE)

input_size = data["input_size"]
hidden_size = data["hidden_size"]
output_size = data["output_size"]
all_words = data['all_words']
tags = data['tags']
model_state = data["model_state"]

model = NeuralNet(input_size, hidden_size, output_size).to(device)
model.load_state_dict(model_state)
model.eval()

bot_name = "ŞipŞak"
translator = Translator()

# NLTK Chatbot için kalıplar
pairs = [
    [
        r"merhaba|selam|hey",
        ["Merhaba! Nasıl yardımcı olabilirim?", "Selam! Size nasıl yardımcı olabilirim?"]
    ],
    [
        r"adın ne?",
        ["Benim adım ŞipŞak. Size nasıl yardımcı olabilirim?"]
    ],
    [
        r"nasılsın?",
        ["İyiyim, teşekkür ederim. Sizin için ne yapabilirim?", "Harika! Size nasıl yardımcı olabilirim?"]
    ],
    [
        r"(.*) hakkında bilgi ver",
        ["Maalesef %1 hakkında detaylı bilgim yok. Başka bir konuda yardımcı olabilir miyim?"]
    ],
    [
        r"(.*)",
        ["Anlamadım. Lütfen başka türlü ifade edebilir misiniz?",
         "Bu konu hakkında bilgim yok. Başka bir şey sormak ister misiniz?"]
    ]
]

nltk_chatbot = Chat(pairs, reflections)

def text_to_speech(text, lang='tr'):
    tts = gTTS(text=text, lang=lang, slow=False)
    filename = f"{uuid.uuid4()}.mp3"
    temp_dir = tempfile.gettempdir()
    filepath = os.path.join(temp_dir, filename)
    tts.save(filepath)
    return filename

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    if "message" in request.json:
        message = request.json["message"]
    elif "speech" in request.json:
        message = request.json["speech"]
    else:
        return jsonify({"error": "No message or speech provided"}), 400

    sentence = tokenize(message)
    X = bag_of_words(sentence, all_words)
    X = X.reshape(1, X.shape[0])
    X = torch.from_numpy(X).to(device)

    output = model(X)
    _, predicted = torch.max(output, dim=1)

    tag = tags[predicted.item()]

    probs = torch.softmax(output, dim=1)
    prob = probs[0][predicted.item()]

    if prob.item() > 0.75:  # Eşik değeri 0.75'ten 0.60'a düşürüldü
        for intent in intents['intents']:
            if tag == intent["tag"]:
                response = random.choice(intent['responses'])
                logger.info(f"Intent cevabı: {response}")
                audio_file = text_to_speech(response)
                return jsonify({"response": response, "audio_file": audio_file, "sender": "bot"})


    # Intent bulunamazsa NLTK Chatbot'u kullan
    nltk_response = nltk_chatbot.respond(message)
    if nltk_response is None:
        nltk_response = "Üzgünüm, bu konuda yardımcı olamıyorum. Başka bir şey sormak ister misiniz?"
    logger.info(f"NLTK Chatbot cevabı: {nltk_response}")
    audio_file = text_to_speech(nltk_response)
    return jsonify({"response": nltk_response, "audio_file": audio_file})

@app.route("/audio/<path:filename>")
def serve_audio(filename):
    temp_dir = tempfile.gettempdir()
    return send_file(os.path.join(temp_dir, filename), mimetype="audio/mpeg")

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route("/speech-to-text", methods=["POST"])
def speech_to_text():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    file = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        file.save(temp_audio.name)
        temp_audio_path = temp_audio.name

    recognizer = sr.Recognizer()

    try:
        # WebM formatını WAV'a dönüştür
        audio = AudioSegment.from_file(temp_audio_path, format="webm")
        wav_path = temp_audio_path.replace(".webm", ".wav")
        audio.export(wav_path, format="wav")

        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        text = recognizer.recognize_google(audio_data, language="tr-TR")
        return jsonify({"text": text})
    except Exception as e:
        logger.error(f"Speech recognition error: {str(e)}")
        return jsonify({"error": "Speech could not be recognized"}), 400
    finally:
        os.unlink(temp_audio_path)
        if os.path.exists(wav_path):
            os.unlink(wav_path)

if __name__ == "__main__":
    app.run(debug=True)