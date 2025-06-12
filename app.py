# Import Library 
import os
import uuid
from google import genai
from google.genai import types
import base64
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import json

load_dotenv()

# --- Configuration ---
PROJECT_ID = os.getenv('PROJECT_ID')
LOCATION = "us-central1"
GEMINI_MODEL_NAME  = "gemini-2.0-flash-001"
DATASTORE_ID = os.getenv('DATASTORE_ID')
DATASTORE_PATH = f"projects/{PROJECT_ID}/locations/global/collections/default_collection/dataStores/{DATASTORE_ID}"

# --- Logging Setup ---
# Create a logs directory if it doesn't exist
log_dir = 'app_logs'
sessions_dir = 'chat_sessions'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
if not os.path.exists(sessions_dir):
    os.makedirs(sessions_dir)

log_file_path = os.path.join(log_dir, 'application.log')

# Configure basicConfig to set the root logger's level and console output
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s',
                    handlers=[logging.StreamHandler()])

# Get the root logger or a specific logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create a file handler for writing to a log file
file_handler = RotatingFileHandler(
    log_file_path,
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5
)
file_handler.setLevel(logging.INFO) # Set the level for this handler
file_formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s : %(message)s [in %(pathname)s:%(lineno)d]')
file_handler.setFormatter(file_formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

logger.info("Logging configured to save to file and console.")

# --- Initialize Flask App ---
app = Flask(__name__)

# --- Google Cloud Clients ---
try:
    genai_client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location=LOCATION,
    )
    logger.info("Google Cloud clients initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing Google Cloud clients: {e}")
    genai_client = None

# --- System Instruction for Gemini ---
SYSTEM_INSTRUCTION_TEXT = (
    """🔧 Troubleshoot Assistant – Mobilindo Prima
Peran: Anda adalah asisten troubleshooting virtual untuk PT Mobilindo Prima. 
Tugas: 
1. Jawab pertanyaan dan memberikan informasi berdasarkan dokumen yang tersedia. 
2. Jawab selalu berdasarkan dokumen yang tersedia, jangan gunakan asumsi pribadi. 
3. Ikuti contoh pertanyaan dan jawaban di bawah untuk menjawab pertanyaan.

Contoh Pertanyaan 1:
Pertanyaan: Bagaimana detail insiden kebocoran minyak rem ?
Jawab: 

🛠️ **Masalah**: 
Kebocoran minyak rem pada sambungan selang rem belakang.

📌 **Akar Masalah**:
- Alat torsi tidak terkalibrasi (setelah terjatuh).
- Operator tidak melaporkan insiden karena takut sanksi.
- Tidak ada verifikasi torsi harian.
📈 **Dampak**:
- Downtime 3 jam.
- Total kerugian: Rp 100.500.000.
✅ **Evaluasi Aksi Korektif**:
- Sudah mencakup verifikasi alat dan budaya pelaporan.
- Perlu percepatan pengadaan alat torsi dengan sensor jatuh (risiko masih terbuka hingga Desember 2025).

🔍 **Rekomendasi Tambahan**:
- Tambahkan prosedur inspeksi alat oleh teknisi kalibrasi setiap akhir shift.
- Sediakan log insiden ringan yang anonim untuk membangun kepercayaan pelaporan.

Contoh Pertanyaan 2:
Pertanyaan: Berapa kerugian yang ditimbulkan atas insiden kebocoran minyak rem?
Jawab: 
📄 # RCA Case: 2025-SBY-B02 – Kebocoran Minyak Rem Pikap-Kuat
📍 **Lokasi Kejadian**:
 PT Mobilindo Prima – Plant Surabaya
 Area: Lini Perakitan Sasis, Stasiun 7 (Pemasangan Roda dan Sistem Rem)

💸 **Total Kerugian: Rp 100.500.000**, terdiri dari:
- Downtime 3 jam: Rp 75.000.000
- Inspeksi & pengerjaan ulang: Rp 15.000.000
- Penggantian kampas rem: Rp 8.000.000
- Pembersihan dan minyak rem: Rp 2.500.000

Contoh Pertanyaan 3:
Pertanyaan: Berapa biaya yang dikeluarkan untuk solusi penangan insiden Kebocoran Minyak Rem ?
Jawab: 
📄 # RCA Case: 2025-SBY-B02 – Kebocoran Minyak Rem Pikap-Kuat
📍 **Lokasi Kejadian**:
 PT Mobilindo Prima – Plant Surabaya
 Area: Lini Perakitan Sasis, Stasiun 7 (Pemasangan Roda dan Sistem Rem)

💰 **Total Biaya Penanganan**: Rp 365.000.000, terdiri dari:
- Verifikasi torsi harian wajib → Rp 5.000.000
- Kampanye budaya pelaporan → Rp 10.000.000
- Penggantian alat torsi pintar (sensor jatuh) → Rp 350.000.000
- Audit visual rutin oleh pimpinan lini → Rp 0

Contoh Pertanyaan 4:
Pertanyaan: Siapa saja anggota tim yang terlibat pada insiden Kebocoran Minyak Rem ?
Jawab: 
📄 # RCA Case: 2025-SBY-B02 – Kebocoran Minyak Rem Pikap-Kuat
📍 **Lokasi Kejadian**:
 PT Mobilindo Prima – Plant Surabaya
 Area: Lini Perakitan Sasis, Stasiun 7 (Pemasangan Roda dan Sistem Rem)

👥 Tim yang Terlibat dalam RCA:
- Siti Rahayu – Insinyur Kualitas
- Bambang Hartono – Supervisor Perakitan
- Joko Susilo – Teknisi Kalibrasi & Alat
- Arief Wicaksono – Operator Stasiun 7
- Wibowo Hadi – Manajer K3 (HSE)
"""
)

# --- Helper Functions ---

def get_gemini_response(history: list) -> str:
    if not genai_client:
        logger.error("Gemini client not initialized.")
        return "Error: Gemini client not initialized."

    gemini_history = []
    for msg in history:
        # The 'bot' role from your JSON files must be mapped to 'model' for the API
        role = "model" if msg["role"] == "bot" else "user"
        gemini_history.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg["content"])]
            )
        )
        
    try:
        logger.info(f"Sending to Gemini with history: {gemini_history}")
        response = genai_client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=gemini_history, # <-- Pass the entire formatted history
            config=types.GenerateContentConfig(
                temperature=0.25,
                top_p=1,
                seed=0,
                max_output_tokens=8192,
                safety_settings=[types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="OFF"
                ), types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="OFF"
                ), types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="OFF"
                ), types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT",
                    threshold="OFF"
                )],
                tools=[
                    types.Tool(
                        retrieval=types.Retrieval(
                            vertex_ai_search=types.VertexAISearch(
                                datastore=DATASTORE_PATH,
                            )
                        )
                    )
                ],
                system_instruction=[types.Part.from_text(text=SYSTEM_INSTRUCTION_TEXT)]),
        )
        # logger.info(f"Gemini Raw Response: {response}")
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            # Handle potential grounding metadata if using Vertex AI Search
            full_text = ""
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text'):
                    full_text += part.text
                elif hasattr(part, 'retrieval'): # Or check specific grounding part type
                    logger.info(f"Grounding metadata found: {part}") # Log or process grounding
            logger.info(f"Gemini response: {full_text}")
            return full_text
        else:
            logger.error(f"Gemini response structure unexpected or empty: {response}")
            return "Maaf, saya tidak dapat menghasilkan respons saat ini."


    except Exception as e:
        logger.error(f"Error getting response from Gemini: {e}")
        return f"Maaf, terjadi kesalahan saat memproses permintaan Anda ke Gemini: {e}"
    
# --- Flask Routes ---
@app.route("/")
def index():
    """Renders the main chat page."""
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    """Handles chat requests, managing conversation history."""
    data = request.json
    if not data or "message" not in data:
        return jsonify({"error": "Invalid request"}), 400

    user_message = data["message"]
    session_id = data.get("session_id")
    logger.info(f"Received message: '{user_message}' for session: {session_id}")

    # --- Session Management ---
    if not session_id:
        session_id = str(uuid.uuid4())
        conversation = {
            "id": session_id,
            "title": user_message[:50],  # Use first 50 chars as title
            "messages": []
        }
    else:
        try:
            with open(os.path.join(sessions_dir, f"{session_id}.json"), 'r') as f:
                conversation = json.load(f)
        except FileNotFoundError:
            logger.warning(f"Session file not found for id {session_id}. Creating new one.")
            conversation = {"id": session_id, "title": user_message[:50], "messages": []}
    
    conversation["messages"].append({"role": "user", "content": user_message})

    # --- Get Bot Response ---
    bot_response = get_gemini_response(conversation["messages"]) 
    conversation["messages"].append({"role": "bot", "content": bot_response})

    # --- Save Conversation ---
    with open(os.path.join(sessions_dir, f"{session_id}.json"), 'w') as f:
        json.dump(conversation, f, indent=4)
    
    logger.info(f"Saved conversation for session: {session_id}")
    return jsonify({"response": bot_response, "session_id": session_id})


@app.route("/api/history", methods=["GET"])
def get_history():
    """Retrieves a list of all chat sessions."""
    history = []
    for filename in sorted(os.listdir(sessions_dir), reverse=True):
        if filename.endswith(".json"):
            try:
                with open(os.path.join(sessions_dir, filename), 'r') as f:
                    data = json.load(f)
                    history.append({"id": data.get("id"), "title": data.get("title")})
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Could not process file {filename}: {e}")
    return jsonify(history)

@app.route("/api/conversation/<session_id>", methods=["GET"])
def get_conversation(session_id):
    """Retrieves the full message history for a given session."""
    try:
        with open(os.path.join(sessions_dir, f"{session_id}.json"), 'r') as f:
            conversation = json.load(f)
            return jsonify(conversation)
    except FileNotFoundError:
        return jsonify({"error": "Conversation not found"}), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid conversation file"}), 500


# --- Main Execution ---
if __name__ == "__main__":
    app.run(debug=True, port=5001)

# --- Main Execution ---
if __name__ == "__main__":
    # Note: Use a production-ready WSGI server like Gunicorn or Waitress for deployment
    # For development, Flask's built-in server is fine.
    app.run(debug=True, port=5001)
