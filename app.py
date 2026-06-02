import os
import json
import time
import shutil
import requests
import random
import urllib.parse
import io
import re
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_from_directory, send_file, Response, stream_with_context
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF: For converting downloaded PDFs to images

app = Flask(__name__)
DOWNLOADS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'downloads'))
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

MASTER_API_DATA = {}
CURRENT_DATE_STR = "20260529"

# =====================================================================
# UTILITY: FONT LOADER
# =====================================================================
def get_font(size):
    try:
        import platform
        if platform.system() == 'Windows': return ImageFont.truetype("arial.ttf", size)
        elif platform.system() == 'Darwin': return ImageFont.truetype("Arial.ttf", size)
        else: return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()

# =====================================================================
# 1. FETCH & FILTER DATA
# =====================================================================
def fetch_and_filter_newspapers():
    global MASTER_API_DATA
    url = f"https://data.tradingref.com/{CURRENT_DATE_STR}.json"
    headers = {
        "Host": "data.tradingref.com",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
        "Sec-Ch-Ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.tradingref.com",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://www.tradingref.com/",
        "Accept-Encoding": "gzip, deflate"
    }

    try:
        print(f"Fetching live newspaper data from {url}...")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        response_text = response.text.strip()
        if not response_text.startswith('{'):
            print("\n❌ ERROR: The server did not return JSON data.")
            MASTER_API_DATA = {}
            return

        MASTER_API_DATA = response.json()
        print("Data fetched and decoded successfully!")

    except Exception as e:
        print(f"\n❌ Failed to fetch live data: {e}")
        MASTER_API_DATA = {}

def get_filtered_frontend_list():
    sources = []
    target_langs = ["hindi", "english"]
    target_city = "delhi"

    for lang, papers in MASTER_API_DATA.items():
        if lang.lower() not in target_langs: continue
        for paper_name, editions in papers.items():
            for edition_name, payload in editions.items():
                if target_city in edition_name.lower():
                    unique_id = f"{lang}|{paper_name}|{edition_name}"
                    sources.append({
                        "id": unique_id, "name": paper_name,
                        "region": edition_name.capitalize(), "language": lang.capitalize()
                    })
    return sources

fetch_and_filter_newspapers()

# =====================================================================
# 2. THE DECODER
# =====================================================================
def deobfuscate_string(encoded_str):
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/"
    reversed_alphabet = alphabet[::-1]
    decoded_str = ""
    for char in encoded_str:
        index = reversed_alphabet.find(char)
        if index != -1: decoded_str += alphabet[index]
        else: decoded_str += char
    return decoded_str

def parse_newspaper_data(encoded_str):
    decoded_str = deobfuscate_string(encoded_str)
    parts = decoded_str.split("q!")
    if len(parts) >= 3:
        return {"type": parts[0], "base_url": parts[1], "pages": [p.strip() for p in parts[2].split("m%") if p.strip()]}
    return None

# =====================================================================
# 3. FLASK ROUTES & STREAMING DOWNLOADER
# =====================================================================
@app.route('/')
def index(): return render_template('index.html')

@app.route('/crop')
def crop(): return render_template('crop.html')

@app.route('/api/newspapers', methods=['GET'])
def get_newspapers(): return jsonify(get_filtered_frontend_list())

@app.route('/api/download', methods=['POST'])
def trigger_download():
    news_ids = request.json.get('ids', [])

    if not news_ids:
        return jsonify({"status": "error", "message": "No newspapers selected"}), 400

    def generate_stream():
        # 1. PURGE OLD FOLDERS
        yield json.dumps({"status": "info", "message": "Purging old workspace..."}) + "\n"
        for filename in os.listdir(DOWNLOADS_DIR):
            file_path = os.path.join(DOWNLOADS_DIR, filename)
            try:
                if os.path.isfile(file_path): os.unlink(file_path)
                elif os.path.isdir(file_path): shutil.rmtree(file_path)
            except Exception: pass

        # 2. PRE-CALCULATE INITIAL TOTAL PAGES
        yield json.dumps({"status": "info", "message": "Calculating total pages..."}) + "\n"
        download_tasks = []
        total_pages = 0

        for unique_id in news_ids:
            lang, paper_name, edition_name = unique_id.split('|')
            safe_name = paper_name.replace(' ', '_')
            target_dir = os.path.join(DOWNLOADS_DIR, f"{safe_name}-{CURRENT_DATE_STR}")

            encrypted_payload = MASTER_API_DATA.get(lang, {}).get(paper_name, {}).get(edition_name, "")
            if not encrypted_payload: continue

            parsed_data = parse_newspaper_data(encrypted_payload)
            if not parsed_data: continue

            pages = parsed_data['pages']
            total_pages += len(pages)

            download_tasks.append({
                "paper_name": paper_name, "target_dir": target_dir,
                "base_url": parsed_data['base_url'], "pages": pages, "doc_type": parsed_data['type']
            })

        if total_pages == 0:
            yield json.dumps({"status": "error", "message": "No valid pages found to download."}) + "\n"
            return

        yield json.dumps({"status": "start", "total_pages": total_pages}) + "\n"

        # 3. SEQUENTIAL DOWNLOADING WITH STREAMING PROGRESS
        downloaded_pages = 0
        dl_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.tradingref.com/",
            "Connection": "close"
        }

        for task in download_tasks:
            os.makedirs(task['target_dir'], exist_ok=True)
            master_page_counter = 1

            for idx, page_path in enumerate(task['pages'], start=1):
                raw_url = f"{task['base_url']}/{page_path}"

                # Apply Proxies dynamically
                if task['doc_type'] == 'image': file_url = f"https://wsrv.nl/?url={urllib.parse.quote(raw_url)}&output=jpg&q=80"
                elif task['doc_type'] == 'pdfl': file_url = f"https://www.tradingref.com/epaper{urllib.parse.urlparse(raw_url).path}"
                elif task['doc_type'] == 'pdfc': file_url = f"https://www.tradingref.com/proxy?quest={urllib.parse.quote(raw_url)}"
                else: file_url = raw_url

                yield json.dumps({"status": "info", "message": f"Connecting to {task['paper_name']}..."}) + "\n"

                # Jitter to avoid bot-bans
                #time.sleep(random.uniform(0.5, 1.5))

                for attempt in range(3):
                    try:
                        response = requests.get(file_url, headers=dl_headers, timeout=60)
                        response.raise_for_status()
                        content_type = response.headers.get('Content-Type', '').lower()

                        # Convert PDF to Images on the fly
                        if 'application/pdf' in content_type or task['doc_type'] in ['pdfl', 'pdfc']:
                            pdf_doc = fitz.open(stream=response.content, filetype="pdf")
                            if pdf_doc.needs_pass:
                                pdf_doc.authenticate(page_path.split('/')[-1][:10])

                            pdf_length = len(pdf_doc)

                            # If the PDF has multiple pages, dynamically increase the total_pages goal
                            if pdf_length > 1:
                                total_pages += (pdf_length - 1)

                                # Stream a progress update FOR EVERY PAGE extracted
                            for p_num in range(pdf_length):
                                pdf_page = pdf_doc.load_page(p_num)
                                pix = pdf_page.get_pixmap(dpi=150)
                                out_idx = idx + p_num if task['doc_type'] == 'pdfc' else idx
                                pix.save(os.path.join(task['target_dir'], f"page_{master_page_counter}.jpg"))
                                master_page_counter += 1

                                downloaded_pages += 1
                                percent = int((downloaded_pages / total_pages) * 100)
                                yield json.dumps({
                                    "status": "progress", "downloaded": downloaded_pages,
                                    "total": total_pages, "percent": percent, "paper": f"{task['paper_name']} (Extracting PDF...)"
                                }) + "\n"

                            pdf_doc.close()

                        # Standard Image Save
                        else:
                            with open(os.path.join(task['target_dir'], f"page_{master_page_counter}.jpg"), 'wb') as f:
                                f.write(response.content)
                            master_page_counter += 1

                            # Update progress for single images
                            downloaded_pages += 1
                            percent = int((downloaded_pages / total_pages) * 100)
                            yield json.dumps({
                                "status": "progress", "downloaded": downloaded_pages,
                                "total": total_pages, "percent": percent, "paper": task['paper_name']
                            }) + "\n"

                        break # Success, break out of the retry loop

                    except Exception as e:
                        yield json.dumps({"status": "info", "message": f"Retry {attempt+1}/3 for {task['paper_name']}..."}) + "\n"
                        time.sleep(2 ** attempt)

        # Signal completion
        yield json.dumps({"status": "success"}) + "\n"

    # Crucial: Keeps the connection alive by streaming data line-by-line
    return Response(stream_with_context(generate_stream()), mimetype='application/x-ndjson')


# --- WORKSPACE ANNOTATION API ---
def get_file_tree():
    tree = []
    if not os.path.exists(DOWNLOADS_DIR): return tree
    folders = sorted([f for f in os.listdir(DOWNLOADS_DIR) if os.path.isdir(os.path.join(DOWNLOADS_DIR, f))])
    for folder in folders:
        folder_path = os.path.join(DOWNLOADS_DIR, folder)
        images = [img for img in os.listdir(folder_path) if img.lower().endswith(('.png', '.jpg', '.jpeg'))]

        # Natural number sorting (ensures page_2 comes before page_10)
        images.sort(key=lambda f: int(re.search(r'\d+', f).group()) if re.search(r'\d+', f) else 0)

        if images: tree.append({"folder": folder, "images": images})
    return tree

@app.route('/api/tree')
def api_tree(): return jsonify(get_file_tree())

@app.route('/images/<folder>/<filename>')
def serve_image(folder, filename): return send_from_directory(os.path.join(DOWNLOADS_DIR, folder), filename)

@app.route('/api/save_box', methods=['POST'])
def save_box():
    data = request.json
    folder, filename = data.get('folder'), data.get('filename')
    base_name, _ = os.path.splitext(filename)
    json_path = os.path.join(DOWNLOADS_DIR, folder, f"{base_name}.json")
    with open(json_path, 'w') as f: json.dump({"boxes": data.get('boxes', [])}, f, indent=4)
    return jsonify({"status": "success"})

@app.route('/api/load_boxes')
def load_boxes():
    folder, filename = request.args.get('folder'), request.args.get('filename')
    base_name, _ = os.path.splitext(filename)
    json_path = os.path.join(DOWNLOADS_DIR, folder, f"{base_name}.json")
    if os.path.exists(json_path):
        with open(json_path, 'r') as f: return jsonify(json.load(f))
    return jsonify({"boxes": []})

@app.route('/api/create_pdf', methods=['POST'])
def create_pdf():
    tree = get_file_tree()
    articles = []

    for item in tree:
        folder = item['folder']
        parts = folder.split('-')
        raw_name = parts[0].replace('_', ' ').title() if len(parts) > 0 else "Unknown Newspaper"
        date_raw = parts[1] if len(parts) > 1 else "Unknown Date"
        date_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}" if len(date_raw) == 8 else date_raw

        for img_name in item['images']:
            base_name, _ = os.path.splitext(img_name)
            json_path = os.path.join(DOWNLOADS_DIR, folder, f"{base_name}.json")
            img_path = os.path.join(DOWNLOADS_DIR, folder, img_name)

            if os.path.exists(json_path) and os.path.exists(img_path):
                with open(json_path, 'r') as f: meta = json.load(f)
                if meta.get('boxes'):
                    with Image.open(img_path) as im:
                        if im.mode in ("RGBA", "P"): im = im.convert("RGB")
                        for box in meta['boxes']:
                            left, top = min(box['x1'], box['x2']), min(box['y1'], box['y2'])
                            right, bottom = max(box['x1'], box['x2']), max(box['y1'], box['y2'])
                            cropped = im.crop((left, top, right, bottom))
                            articles.append({
                                "image": cropped.copy(),
                                "name": raw_name,
                                "date": date_str
                            })

    if not articles:
        return jsonify({"status": "error", "message": "No annotated boxes found to compile!"}), 400

    A4_WIDTH, A4_HEIGHT = 1240, 1754
    MARGIN = 60
    HEADER_HEIGHT = 50
    PAGE_USABLE_WIDTH = A4_WIDTH - (2 * MARGIN)
    PAGE_USABLE_HEIGHT = A4_HEIGHT - (2 * MARGIN)

    font = get_font(28)
    pdf_pages = []
    current_page = None
    draw = None
    current_y = MARGIN
    articles_on_page = 0

    def create_new_page():
        nonlocal current_page, draw, current_y, articles_on_page
        if current_page is not None: pdf_pages.append(current_page)
        current_page = Image.new('RGB', (A4_WIDTH, A4_HEIGHT), 'white')
        draw = ImageDraw.Draw(current_page)
        current_y = MARGIN
        articles_on_page = 0

    create_new_page()

    for article in articles:
        img, name, date = article['image'], article['name'], article['date']

        img_w, img_h = img.size
        scale = min(1.0, PAGE_USABLE_WIDTH / img_w)
        new_w, new_h = int(img_w * scale), int(img_h * scale)

        if new_h > (PAGE_USABLE_HEIGHT - HEADER_HEIGHT):
            scale_h = (PAGE_USABLE_HEIGHT - HEADER_HEIGHT) / new_h
            new_w, new_h = int(new_w * scale_h), int(new_h * scale_h)

        total_needed_height = HEADER_HEIGHT + new_h + 40

        if articles_on_page >= 2 or (current_y + total_needed_height > A4_HEIGHT - MARGIN and articles_on_page > 0):
            create_new_page()

        draw.text((MARGIN, current_y), name, fill="black", font=font)
        try: date_w = draw.textlength(date, font=font)
        except AttributeError: date_w = font.getsize(date)[0]
        draw.text((A4_WIDTH - MARGIN - date_w, current_y), date, fill="black", font=font)

        current_y += HEADER_HEIGHT
        x_offset = MARGIN + (PAGE_USABLE_WIDTH - new_w) // 2

        resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        current_page.paste(resized_img, (x_offset, current_y))

        current_y += new_h + 40
        articles_on_page += 1

    if current_page is not None: pdf_pages.append(current_page)

    pdf_bytes = io.BytesIO()
    pdf_pages[0].save(pdf_bytes, format='PDF', save_all=True, append_images=pdf_pages[1:])
    pdf_bytes.seek(0)

    return send_file(pdf_bytes, download_name=f'extracted_articles_{CURRENT_DATE_STR}.pdf', as_attachment=True, mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=True, port=5000)