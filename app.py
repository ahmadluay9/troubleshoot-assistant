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

# Contoh Pertanyaan 1:
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

# Contoh Pertanyaan 2:
Pertanyaan: Apa penyebab insiden Kebocoran Minyak Rem Pikap-Kuat?
Jawab: 
Penyebab utama adalah mur penyambung selang rem tidak dikencangkan sesuai standar (kurang dari 35 Nm) karena alat torsi elektrik tidak terkalibrasi dengan benar setelah terjatuh dari meja kerja.

# Contoh Pertanyaan 3:
Pertanyaan: Kapan dan di mana insiden ini terjadi?
Jawab: 
Insiden terjadi pada tanggal 3 Juni 2025 di PT Mobilindo Prima, Plant Surabaya, tepatnya di Stasiun 7 (Pemasangan Roda dan Sistem Rem) pada lini perakitan sasis.

# Contoh Pertanyaan 4:
Pertanyaan: Berapa total kerugian yang ditimbulkan atas insiden kebocoran minyak rem?
Jawab: 
💸 **Total Kerugian: Rp 100.500.000**, terdiri dari:
- Downtime 3 jam: Rp 75.000.000.

- Inspeksi & pengerjaan ulang: Rp 15.000.000.

- Penggantian kampas rem: Rp 8.000.000.

- Pembersihan dan minyak rem: Rp 2.500.000.

# Contoh Pertanyaan 5:
Pertanyaan: Apa solusi yang diambil untuk mencegah kejadian serupa dengan insiden keboncoran minyak rem?
Jawab: 
💰 **Total Biaya Penanganan**: Rp 365.000.000, terdiri dari:
- Verifikasi torsi harian wajib → Rp 5.000.000.

- Kampanye budaya pelaporan → Rp 10.000.000.

- Penggantian alat torsi pintar (sensor jatuh) → Rp 350.000.000.

- Audit visual rutin oleh pimpinan lini → Rp 0.

# Contoh Pertanyaan 6:
Pertanyaan: Siapa saja yang terlibat dalam tim RCA pada insiden Kebocoran Minyak Rem ?
Jawab: 
👥 Tim yang Terlibat dalam RCA:
- Siti Rahayu – Insinyur Kualitas.

- Bambang Hartono – Supervisor Perakitan.

- Joko Susilo – Teknisi Kalibrasi & Alat.

- Arief Wicaksono – Operator Stasiun 7.

- Wibowo Hadi – Manajer K3 (HSE).

# Contoh Pertanyaan 7:
Pertanyaan: Apa penyebab tidak langsung dari kegagalan ini?
Jawab: 
- Budaya kerja yang membuat operator takut melapor.

- Prosedur pemeriksaan alat torsi yang tidak memadai.

- Tidak adanya sensor deteksi jatuh pada alat.

- Kurangnya pengawasan proaktif oleh pimpinan lini.


# Contoh Pertanyaan 8:
Pertanyaan: Berapa nomor Dokumen SOP verifikasi torsi harian wajib?
Jawab: 
Nomor dokumen SOP Torsi harian wajib adalah **SOP - PROD - 012**.

# Contoh Pertanyaan 9:
Pertanyaan: Apa tujuan Dokumen SOP verifikasi torsi harian wajib?
Jawab: 
Untuk memastikan alat pengencang torsi bekerja akurat agar sambungan baut di titik-titik kritis memenuhi standar teknis, mencegah kegagalan fungsi, dan menjaga keselamatan serta kualitas produk.

# Contoh Pertanyaan 10:
Pertanyaan: Kapan verifikasi torsi wajib dilakukan?
Jawab: 
Verifikasi torsi wajib dilakukan setiap awal shift produksi.

# Contoh Pertanyaan 11:
Pertanyaan: Apa saja yang termasuk dalam ruang lingkup SOP verifikasi torsi harian wajib?
Jawab: 
SOP ini berlaku untuk semua alat pengencang torsi di titik kritis pengencangan, termasuk:

- Pemasangan komponen suspensi
- Baut mesin (engine mounting)
- Baut roda
- Sambungan utama sasis dan bodi

# Contoh Pertanyaan 12:
Pertanyaan: Apa definisi dari “Master Torque Checker”?
Jawab: 
Master Torque Checker adalah alat ukur presisi yang sudah dikalibrasi secara berkala dan digunakan sebagai standar acuan untuk memverifikasi alat torsi.

# Contoh Pertanyaan 13:
Pertanyaan: Apa langkah-langkah utama dalam verifikasi harian torsi?”
Jawab: 
1. Persiapan: Siapkan alat & formulir

2. Verifikasi: Uji alat dengan Master Torque Checker

3. Analisis: Bandingkan hasil dengan target ±5%

4. Keputusan:

Lolos → beri label hijau dan boleh digunakan

Gagal → beri label merah dan jangan digunakan

5. Pencatatan: Formulir ditandatangani dan diserahkan ke QC

# Contoh Pertanyaan 14:
Pertanyaan: Apa tindakan jika alat torsi gagal verifikasi?
Jawab: 
- Diberi label merah "GAGAL - JANGAN GUNAKAN"

- Dipisahkan dari area kerja

- Dilaporkan ke Supervisor

- Tidak boleh digunakan sebelum diperbaiki/kalibrasi ulang

# Contoh Pertanyaan 15:
Pertanyaan: Siapa saja yang bertanggung jawab dalam pelaksanaan SOP ini?
Jawab: 
- **Operator/Team Leader**: Melakukan verifikasi dan lapor jika ada kegagalan

- **Supervisor Produksi**: Memastikan SOP dilaksanakan dan menyediakan alat pengganti

- **Supervisor QC**: Melakukan audit acak, mengelola formulir, dan menindaklanjuti alat gagal

# Contoh Pertanyaan 16:
Pertanyaan: Apa tujuan utama dari kampanye “Lapor Cepat, Aman Bersama”?
Jawaban:
Mendorong budaya kerja proaktif dan terbuka agar setiap karyawan merasa aman melaporkan potensi masalah sejak dini, guna meningkatkan kualitas, keselamatan, dan kecepatan respons manajemen terhadap insiden.

# Contoh Pertanyaan 17:
Pertanyaan: Apa filosofi utama dari kampanye "Lapor, Cepat, Aman Bersama"?
Jawaban:
Tiga pilar utama kampanye:

1. Fokus pada solusi, bukan menyalahkan (Blameless Reporting)

2. Setiap laporan berharga – No report is too small

3. Keamanan psikologis karyawan dijamin – tanpa balasan negatif

# Contoh Pertanyaan 18:
Pertanyaan: Apa filosofi utama dari kampanye "Lapor, Cepat, Aman Bersama"?
Jawaban:
Tiga pilar utama kampanye:

1. Fokus pada solusi, bukan menyalahkan (Blameless Reporting)

2. Setiap laporan berharga – No report is too small

3. Keamanan psikologis karyawan dijamin – tanpa balasan negatif

# Contoh Pertanyaan 19:
Pertanyaan: Apa saja saluran pelaporan yang disediakan dalam kampanye "Lapor, Cepat, Aman Bersama"?
Jawaban:

1. Atasan Langsung – cara tercepat, verbal atau tertulis

2. Kotak “Lapor Cepat” – bisa anonim

3. Hotline & Email K3 – dijamin rahasia

- Email: laporcepat@mobilindo.co.id

- Hotline: (021) 555-SAFE (7233)

# Contoh Pertanyaan 20:
Pertanyaan: Apa saja saluran pelaporan yang disediakan dalam kampanye "Lapor, Cepat, Aman Bersama"?
Jawaban:

1. Atasan Langsung – cara tercepat, verbal atau tertulis

2. Kotak “Lapor Cepat” – bisa anonim

3. Hotline & Email K3 – dijamin rahasia

- Email: laporcepat@mobilindo.co.id

- Hotline: (021) 555-SAFE (7233)

# Contoh Pertanyaan 21:
Pertanyaan: Apa manfaat dari melaporkan masalah kecil seperti baut longgar atau tetesan oli?
Jawaban:
Masalah kecil yang dilaporkan hari ini bisa menjadi bencana besar yang berhasil dicegah di masa depan. Setiap laporan adalah informasi berharga.

# Contoh Pertanyaan 22:
Pertanyaan: Bagaimana alur tindak lanjut dari laporan yang masuk?
Jawaban:

1. Dicatat dan diberi nomor tiket oleh tim K3.

2. Diteruskan ke departemen terkait untuk investigasi.

3. Pelapor (jika diketahui) menerima feedback dalam waktu maks. 3x24 jam.

# Contoh Pertanyaan 23:
Pertanyaan: Apa yang dilakukan pada Fase 1 kampanye ini?
Jawaban:

- Town Hall Kick-off oleh Manajer Plant.

- Pemasangan media kampanye (poster, spanduk).

- Briefing khusus Supervisor.

- Distribusi kartu saku informasi kampanye ke seluruh karyawan.

# Contoh Pertanyaan 24:
Pertanyaan: Apa bentuk penghargaan terhadap karyawan yang aktif melapor?
Jawaban:

- Penghargaan bulanan “Pelapor Terbaik”.

- Laporan mereka dijadikan studi kasus positif dalam Safety Talk mingguan (P5M).

# Contoh Pertanyaan 25:
Pertanyaan: Apa jaminan perusahaan terhadap pelapor?
Jawaban:
Perusahaan menjamin tidak akan ada tindakan balasan (retaliasi) terhadap siapa pun yang melapor dengan jujur dan niat baik.

# Contoh Pertanyaan 26:
Pertanyaan: Bagaimana kampanye ini dijaga keberlanjutannya setelah 6 bulan?
Jawaban:
- Dilakukan survei budaya kerja.

- Analisis data tren laporan.

- Integrasi materi kampanye ke program orientasi karyawan baru.

# Contoh Pertanyaan 27:
Pertanyaan: Apa tujuan utama dari SOP Penggunaan Alat Torsi Pintar ini?
Jawaban:
Untuk memastikan alat torsi pintar yang mengalami benturan atau terjatuh tidak digunakan sebelum diverifikasi ulang, demi menjaga akurasi dan keselamatan kerja di titik pengencangan kritis.

# Contoh Pertanyaan 28:
Pertanyaan: Apa itu alat torsi pintar?
Jawaban:
Alat torsi pintar adalah alat pengencang torsi yang dilengkapi dengan sensor jatuh (drop sensor) dan indikator status visual LED untuk mendeteksi dan menandai kondisi alat.

# Contoh Pertanyaan 29:
Pertanyaan: Apa arti indikator warna pada alat torsi pintar?
Jawaban:

HIJAU: Alat dalam kondisi OK dan siap digunakan.

MERAH: Alat telah mendeteksi benturan dan masuk ke mode terkunci — tidak boleh digunakan.

# Contoh Pertanyaan 30:
Pertanyaan: Apa tindakan yang harus dilakukan jika alat menunjukkan indikator merah?
Jawaban:

- Jangan gunakan alat tersebut.

- Segera laporkan ke Supervisor.

- Supervisor akan menempelkan label merah dan membawa alat ke stasiun verifikasi.

# Contoh Pertanyaan 31:
Pertanyaan: Siapa saja yang boleh melakukan reset sensor jatuh pada alat?
Jawaban:
Hanya personel yang telah ditunjuk dan dilatih, seperti Supervisor, QC, atau teknisi maintenance. Operator dilarang keras melakukan reset sendiri.

# Contoh Pertanyaan 31:
Pertanyaan: Apa yang harus dilakukan jika alat torsi terjatuh saat shift berlangsung?
Jawaban:

- Segera berhenti bekerja.

- Laporkan insiden ke Supervisor.

- Periksa indikator status alat, meskipun tidak berubah warna, insiden tetap harus dilaporkan.

# Contoh Pertanyaan 31:
Pertanyaan: Apa yang terjadi jika hasil verifikasi ulang menunjukkan alat masih dalam kondisi baik?
Jawaban:
Sensor akan di-reset oleh personel berwenang, indikator kembali menjadi hijau, dan alat bisa digunakan kembali dalam produksi.

# Contoh Pertanyaan 32:
Pertanyaan: Apa yang terjadi jika hasil verifikasi menunjukkan alat gagal?
Jawaban:

- Alat tetap dalam mode terkunci

- Diserahkan ke Departemen Maintenance/Kalibrasi untuk perbaikan dan kalibrasi penuh

- Tidak boleh kembali ke lini sebelum diperbaiki.

# Contoh Pertanyaan 33:
Pertanyaan: Apa tanggung jawab utama operator dalam SOP Penggunaan Alat Torsi Pintar ini?
Jawaban:

- Melakukan pemeriksaan awal shift.

- Menggunakan alat dengan hati-hati.

- Melaporkan setiap insiden jatuh atau benturan secepatnya.

# Contoh Pertanyaan 34:
Pertanyaan: Apa tujuan utama dari pelaksanaan Layered Process Audit (LPA)?
Jawaban:
Untuk memastikan kepatuhan terhadap standar kerja secara konsisten, meningkatkan kehadiran pimpinan di area produksi, mempercepat koreksi penyimpangan kecil sebelum menjadi masalah besar, dan membuka komunikasi dua arah antara pimpinan dan operator.

# Contoh Pertanyaan 35:
Pertanyaan: Apa itu Layered Process Audit (LPA)?
Jawaban:
LPA adalah sistem audit singkat dan frekuen yang dilakukan oleh berbagai tingkatan manajemen (Team Leader, Supervisor, Manajer) guna memverifikasi apakah proses berjalan sesuai standar.

# Contoh Pertanyaan 36:
Pertanyaan: Siapa saja yang melakukan audit LPA dan seberapa sering dilakukan?
Jawaban:

- Lapis 1 (Team Leader): Setiap hari per stasiun (5–10 menit).

- Lapis 2 (Supervisor): 2–3 kali seminggu pada stasiun berbeda (15 menit).

- Lapis 3 (Manajer): 1 kali seminggu (20–30 menit).

# Contoh Pertanyaan 37:
Pertanyaan: Apa yang dimaksud dengan checklist LPA?
Jawaban:
Checklist LPA adalah daftar 5–10 pertanyaan "Ya/Tidak" yang berfokus pada elemen-elemen kunci proses, dan bersifat spesifik untuk tiap stasiun kerja.


# Contoh Pertanyaan 38:
Pertanyaan: Apa yang harus dilakukan auditor jika menemukan penyimpangan?
Jawaban:

- Tidak menyalahkan operator

- Gunakan pendekatan pembinaan (coaching)

- Tanyakan alasan di balik penyimpangan

- Lakukan tindakan korektif langsung bila memungkinkan

- Catat semua penyimpangan dan tindak lanjutnya

# Contoh Pertanyaan 39:
Pertanyaan: Apa contoh pertanyaan dalam LPA saat audit?
Jawaban:

- "Apakah verifikasi torsi harian sudah dilakukan dan ditandatangani?"

- "Bolehkah saya lihat bagaimana Anda memeriksa kualitas hasil las?"

# Contoh Pertanyaan 40:
Pertanyaan: Bagaimana hasil audit LPA disampaikan dan ditindaklanjuti?
Jawaban:
Checklist dikembalikan ke Papan Manajemen Visual LPA, lalu dipasang stiker indikator (hijau/kuning/merah). Data checklist direkap mingguan oleh Supervisor Kualitas dan dibahas dalam rapat mingguan untuk melihat tren penyimpangan.

# Contoh Pertanyaan 41:
Pertanyaan: Apa arti dari tindakan korektif langsung (on-the-spot corrective action)?
Jawaban:
Tindakan perbaikan yang dilakukan langsung di lapangan saat audit, seperti membantu mengambil APD atau memperbaiki posisi komponen agar sesuai instruksi kerja.

# Contoh Pertanyaan 42:
Pertanyaan: Apa yang dilakukan jika masalah yang ditemukan bersifat sistemik?
Jawaban:
Masalah sistemik seperti alat rusak atau instruksi kerja tidak jelas harus dieskalasikan ke level manajemen yang sesuai untuk penanganan lebih lanjut.
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
