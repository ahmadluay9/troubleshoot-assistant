# Gunakan official Python runtime sebagai base image
FROM python:3.10-slim

# Tetapkan working directory di dalam container
WORKDIR /app

# Salin semua isi direktori proyek ke dalam container di /app
COPY . /app

# Install semua package yang dibutuhkan dari requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Buat port 8080 (atau PORT dari environment variable) dapat diakses dari luar container
# Cloud Run secara default mengharapkan aplikasi listen pada port yang didefinisikan oleh env var PORT, defaultnya 8080
EXPOSE 8080

# Jalankan app.py menggunakan Gunicorn ketika container dijalankan
# Gunicorn adalah WSGI HTTP Server yang production-ready
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "app:app"]
