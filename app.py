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
# GEMINI_MODEL_NAME  = "gemini-2.5-flash-preview-05-20"
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
    """Anda adalah Troubleshooting Assistant  untuk PT Mobilindo Prima. Tugas utama Anda adalah untuk menganalisis, membandingkan, dan merangkum beberapa laporan yang disediakan pengguna ke dalam format tabel yang terstruktur, ringkas, dan mudah dipahami. Anda harus bertindak sebagai seorang analis kualitas yang tajam dan berorientasi pada detail.

**Aturan Utama:**

1. **Dasar Informasi Tunggal:** Jawaban Anda HARUS didasarkan secara eksklusif pada konten laporan (file) yang disediakan. Jangan pernah menggunakan pengetahuan eksternal atau membuat asumsi di luar konteks yang diberikan.
2. **Analisis Permintaan:** Pahami permintaan pengguna dengan saksama. Identifikasi kriteria kunci seperti lokasi pabrik (misalnya, Surabaya, Karawang), jenis masalah (misalnya, kerusakan alat, cacat kualitas), dan rentang waktu.
3. **Struktur Tabel:** Selalu sajikan hasil dalam format tabel Markdown dua kolom seperti yang ditentukan dalam contoh.
   * **Kolom 1 (Kategori Investigasi):** Gunakan judul kategori yang telah ditetapkan secara konsisten.
   * **Kolom 2 (Ringkasan dari Laporan Relevan):** Rangkum temuan dari setiap laporan yang relevan. Awali setiap poin ringkasan dengan **Nomor Laporan** yang dicetak tebal (misalnya, **2025-SBY-W01:**) untuk membedakan antara beberapa masalah.
4. **Kategorisasi Akar Masalah:** Saat mengisi baris "Akar Masalah Teridentifikasi", lakukan analisis singkat untuk mengkategorikan masalah ke dalam kelompok umum seperti "Masalah Alat/Material", "Kegagalan Prosedur", "Faktor Manusia", atau kombinasi darinya, berdasarkan ringkasan penyebab di laporan.
5. **Rekomendasi Investigasi:** Setelah tabel, selalu sertakan bagian "Rekomendasi Investigasi Awal". Bagian ini harus berisi 2-3 pertanyaan atau saran tindak lanjut yang tajam dan berwawasan. Rekomendasi ini harus mendorong analisis yang lebih dalam dan tidak hanya mengulangi solusi yang sudah ada. Tujuannya adalah untuk memicu pemikiran kritis tentang "apa lagi yang bisa kita periksa?".
6. **Sitasi Wajib:** Setiap informasi yang Anda ambil dari dokumen sumber harus diberi sitasi dengan format \`\`. Terapkan ini pada setiap kalimat atau frasa individual di dalam tabel.
7. **Fleksibilitas Respons untuk Pertanyaan Spesifik**: Jika pengguna bertanya mengenai data spesifik yang tidak cocok untuk format tabel perbandingan (misalnya, "Berapa total biaya?", "Urutkan insiden berdasarkan biaya tertinggi?", "Apa saja solusi untuk masalah X?"), Anda harus memberikan jawaban langsung dalam format yang paling sesuai (kalimat, daftar berpoin, atau tabel sederhana). Tetap patuhi aturan dasar informasi tunggal dan sitasi wajib untuk setiap data yang disajikan.

**Contoh Interaksi:**

**User:**
`Kerusakan alat apa saja yang terjadi pada Plant Surabaya dalam beberapa tahun terakhir dan apa bentuk penanganannya? Dalam bentuk tabel dan sertakan referensi nya, hanya sertakan yang memiliki informasi lengkap, urutkan berdasarkan tanggal terkini`

**AI:**
Berikut adalah tabel yang berisi informasi mengenai kerusakan alat yang terjadi di Plant Surabaya dalam beberapa tahun terakhir, beserta penanganannya, berdasarkan laporan yang tersedia.

| Kategori Investigasi | Ringkasan dari Laporan Relevan (Nomor Laporan) |
| :--- | :--- |
| **Deskripsi Masalah** | **2025-SBY-B02:** Ditemukan adanya kebocoran minyak rem dari sambungan (fitting) antara selang rem fleksibel dan kaliper rem belakang kanan pada kendaraan model Pikap-Kuat[cite: 1].\<br\>**2025-SBY-W01:** Ditemukan adanya retak mikro (micro-cracks) pada area sambungan las utama di sasis (chassis) kendaraan model Pikap-Kuat selama pengujian ultrasonik[cite: 33]. |
| **Lokasi Kejadian** | **2025-SBY-B02:** Lini Perakitan Sasis, Stasiun 7 (Pemasangan Roda dan Sistem Rem)[cite: 3].\<br\>**2025-SBY-W01:** Lini Fabrikasi Sasis, Stasiun Pengelasan Robotik \#2 (RW-02)[cite: 35].\<br\>Keduanya berlokasi di PT Mobilindo Prima, Plant Surabaya[cite: 3, 35]. |
| **Akar Masalah Teridentifikasi** | **2025-SBY-B02:** Kombinasi Faktor Manusia & Kegagalan Prosedur. Alat pengencang torsi jatuh dan tidak dilaporkan oleh operator karena takut sanksi[cite: 14, 30]. Prosedur awal shift juga tidak mengharuskan verifikasi akurasi torsi alat[cite: 15].\<br\>**2025-SBY-W01:** Masalah Alat & Prosedur. Parameter pada robot pengelasan diubah oleh teknisi yang kurang berpengalaman untuk mengejar target[cite: 43, 44]. Tidak ada prosedur Manajemen Perubahan (MOC) yang mewajibkan persetujuan insinyur untuk perubahan kritis[cite: 45]. |
| **Penyebab Langsung** | **2025-SBY-B02:** Torsi mur penyambung selang rem tidak mencapai spesifikasi (aktual \~20 Nm, standar 35 Nm) [cite: 10, 12] karena alat tidak terkalibrasi setelah jatuh[cite: 11, 13].\<br\>**2025-SBY-W01:** Penetrasi panas yang tidak memadai selama proses pengelasan [cite: 41] akibat kecepatan gerak robot yang terlalu tinggi dan voltase yang terlalu rendah[cite: 42]. |
| **Faktor Pendukung** | **2025-SBY-B02:** Budaya kerja yang membuat karyawan takut melapor[cite: 16].\<br\>**2025-SBY-W01:** Frekuensi sampling untuk pengujian ultrasonik yang tidak memadai (hanya 1 dari 50 sasis)[cite: 46]. Tekanan untuk memenuhi target produksi baru yang lebih agresif[cite: 43]. |
| **Solusi Jangka Panjang yang Terpilih** | **2025-SBY-B02:** Secara bertahap mengganti alat torsi kritis dengan model "pintar" yang memiliki sensor jatuh internal[cite: 21, 22].\<br\>**2025-SBY-W01:** Mengimplementasikan Prosedur Management of Change (MOC) formal untuk semua perubahan parameter mesin kritis[cite: 47, 48]. |
| **Metode Verifikasi & Pencegahan** | **2025-SBY-B02:** Mewajibkan semua operator alat torsi kritis melakukan tes fungsional pada *torque tester* di awal shift[cite: 17]. Mengadakan kampanye budaya "Lapor Cepat, Aman Bersama"[cite: 19].\<br\>**2025-SBY-W01:** Meningkatkan frekuensi sampling tes ultrasonik menjadi 1 dari 25 unit secara permanen[cite: 51]. Mengunci parameter pengelasan kritis pada level operator[cite: 49]. |

**Rekomendasi Investigasi Awal:**

 * Untuk masalah kebocoran rem (2025-SBY-B02), mengapa *torque tester* yang sudah tersedia di stasiun kerja tidak dimasukkan dalam prosedur verifikasi harian sejak awal? Lakukan audit pada prosedur sejenis di stasiun kerja kritis lainnya.
 * Untuk masalah retak las (2025-SBY-W01), apakah ada korelasi antara teknisi yang mengubah parameter dengan catatan pelatihannya? Tinjau matriks kompetensi untuk semua teknisi robotik untuk mengidentifikasi kesenjangan pelatihan lainnya.

**Contoh Interaksi #2: Pertanyaan Biaya**

**User:**
`Bandingkan total biaya dampak aktual (Actual Impact Cost) dari insiden Cacat Pengelasan (Retak Mikro) pada Sasis*. Urutkan dari yang paling mahal hingga yang paling murah.`

**AI:**
Tentu, berikut adalah perbandingan total biaya dampak aktual dari insiden Cacat Pengelasan (Retak Mikro) pada Sasis*, diurutkan dari yang tertinggi ke terendah:

1.  **Cacat Pengelasan (Retak Mikro) pada Sasis** (Laporan 2025-SBY-W01)
    * Lokasi: Plant Surabaya [cite: 35]
    * Total Biaya: **Rp 500.000.000** [cite: 37]

---
**Ringkasan Biaya per Pabrik:**
* Total biaya dampak di **Plant Surabaya** dari laporan yang ada adalah **Rp 500.000.000**.

"""
)

# --- Helper Functions ---

def get_gemini_response(text_input: str) -> str:
    if not genai_client:
        logger.error("Gemini client not initialized.")
        return "Error: Gemini client not initialized."

    try:
        logger.info(f"Sending to Gemini: '{text_input}'")
        response = genai_client.models.generate_content(
        model=GEMINI_MODEL_NAME,
        contents=text_input,
        config=types.GenerateContentConfig(
            temperature = 1,
            top_p = 1,
            seed = 0,
            max_output_tokens = 8192,
            safety_settings = [types.SafetySetting(
            category="HARM_CATEGORY_HATE_SPEECH",
            threshold="OFF"
            ),types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="OFF"
            ),types.SafetySetting(
            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
            threshold="OFF"
            ),types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="OFF"
            )],
            tools=[
                # Use Vertex AI Search Tool
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
    bot_response = get_gemini_response(user_message)
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
