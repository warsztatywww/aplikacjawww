#!/usr/bin/env python

import os
import sys
import requests
from bs4 import BeautifulSoup

ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif'}

# ID of the album to upload images - it has to be created beforehand via admin panel
ALBUM_ID = ""
FORM_URL = "https://warsztatywww.pl/gallery/upload"

# To set the below cookie go to your browser, make a request to the gallery upload page and copy the sessionid cookie
SESSION_ID = ""

HEADERS = {
    "Referer": "https://warsztatywww.pl",
}


def send_file(session, path):
    form_response = session.get(FORM_URL, headers=HEADERS)
    if form_response.status_code != 200:
        print("Failed to get form page")
        print(form_response.text)
        return False
    soup = BeautifulSoup(form_response.text, 'html.parser')
    csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})['value']
    filename = path.split("/")[-1]
    files = [("data", (filename, open(path, 'rb')))]
    payload = {'csrfmiddlewaretoken': csrf_token,
               "apk": ALBUM_ID, "next": f"/gallery/album/{ALBUM_ID}/upload"}
    res = session.post(FORM_URL, files=files, data=payload, headers=HEADERS)
    return res.status_code == 200


def upload_images(images_dir):
    session = requests.Session()
    session.cookies.set("sessionid", SESSION_ID)
    print(f"Uploading images from {images_dir} to album {ALBUM_ID}...")
    for root, dirs, files in os.walk(images_dir):
        for file in files:
            if any(file.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
                full_path = os.path.join(root, file)
                print(f"Uploading {full_path}...")
                success = send_file(session, full_path)
                if success:
                    print(f"Uploaded {full_path} successfully.")
                else:
                    print(f"Failed to upload {full_path}.")
                    return


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) > 0:
        upload_images(args[0])
    else:
        print("Usage: upload_images_to_gallery.py <images_dir>")
        sys.exit(1)
