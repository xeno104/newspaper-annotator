# Newspaper Annotator

A Flask app for downloading today's Delhi newspapers and cropping out the article images. It saves every page as a JPG, lets you draw boxes around articles in a simple crop tool, and then compiles all the boxes into one A4 PDF.

## How to Run

1. Install the dependencies:

```bash
pip install flask requests pillow pymupdf
```

2. Start the server:

```bash
python app.py
```

3. Open `http://127.0.0.1:5000` in your browser.

On Windows you can run `start.bat` instead — it installs the dependencies and starts the app in one go.

## Features

- **Edition filter** — shows only the Hindi and English Delhi editions from the source
- **Page download** — pages are saved as JPGs, and PDF pages are converted at 150 DPI on the fly
- **Retries** — a failed download is retried three times with a growing delay
- **Crop tool** — draw boxes around articles on any page; each box is saved next to the image as a JSON file
- **PDF export** — every annotated box is cropped and placed into a multi-page A4 PDF, two articles per page with the paper name and date
- **Fresh workspace** — the downloads folder is cleared at the start of every download job

## Project Structure

```
newspaper-annotator/
├── app.py              # Flask server, downloader and PDF export
├── templates/
│   ├── index.html      # edition picker and download progress
│   └── crop.html       # box drawing tool
├── test.py             # standalone test for the payload decoder
└── start.bat           # Windows launcher
```