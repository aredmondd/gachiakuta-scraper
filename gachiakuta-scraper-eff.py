import os
import requests
import PyPDF2
import img2pdf
import sys
import pprint
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from playsound import playsound
import threading

# Initialize a list to store chapters with missing 'src' attributes
busted_chapters = []
lock = threading.Lock()  # To manage access to busted_chapters

# Function to play sound asynchronously
def play_sound(sound_file):
    threading.Thread(target=playsound, args=(sound_file,), daemon=True).start()

def scrape(url, chapter_name_slug, img_dir, session, max_workers=10):
    try:
        # Send a GET request to the webpage using the session
        response = session.get(url, timeout=10)
        response.raise_for_status()  # Check for request errors
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all the images (update selectors based on the website's structure)
        main_div = soup.find('div', class_='entry-content')
        img_tags = main_div.find_all('img', class_='article_ed__img')

        # Create a directory to store downloaded images
        os.makedirs(img_dir, exist_ok=True)

        # Function to download a single image
        def download_image(img_tag, index):
            try:
                img_url = img_tag['src']
            except KeyError:
                with lock:
                    busted_chapters.append(chapter_name_slug)
                print(f"Error: 'src' attribute missing in chapter '{chapter_name_slug}'. Skipping...")
                play_sound('sounds/error.mp3')
                return

            img_extension = os.path.splitext(urlparse(img_url).path)[-1]
            img_name = f"{chapter_name_slug}-page-{index}{img_extension}"
            img_path = os.path.join(img_dir, img_name)

            try:
                img_response = session.get(img_url, timeout=10)
                img_response.raise_for_status()
                with open(img_path, 'wb') as img_file:
                    img_file.write(img_response.content)
                print(f"Downloaded: {img_name}")
            except requests.exceptions.RequestException as e:
                with lock:
                    busted_chapters.append(chapter_name_slug)
                print(f"Error downloading {img_url}: {e}")
                play_sound('sounds/error.mp3')

        # Use ThreadPoolExecutor to download images concurrently
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(download_image, img_tag, idx+1): img_tag for idx, img_tag in enumerate(img_tags)}
            for future in as_completed(futures):
                pass  # All handling is done inside download_image

        print("All images downloaded successfully.")

    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve URL {url}: {e}")
        play_sound('sounds/error.mp3')

def images_to_pdf(directory, output_name):
    try:
        # List all JPEG and PNG files in the directory
        image_files = [f for f in os.listdir(directory) if f.lower().endswith((".jpg", ".jpeg", ".png"))]

        # Sort the image files based on page number
        image_files.sort(key=lambda x: int(''.join(filter(str.isdigit, x.split('-page-')[1]))))

        # Prepare full paths for img2pdf
        image_paths = [os.path.join(directory, img) for img in image_files]

        # Convert images to PDF
        with open(output_name, "wb") as f:
            f.write(img2pdf.convert(image_paths))

        print(f"PDF created: {output_name}")

    except Exception as e:
        print(f"Error creating PDF {output_name}: {e}")
        play_sound('sounds/error.mp3')

def reverse_pdf(input_pdf, output_pdf):
    try:
        with open(input_pdf, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            writer = PyPDF2.PdfWriter()

            # Reverse the order of pages
            for page_num in reversed(range(len(reader.pages))):
                writer.add_page(reader.pages[page_num])

            with open(output_pdf, 'wb') as output_file:
                writer.write(output_file)

        play_sound('sounds/success.mp3')
        print(f"Reversed PDF created: {output_pdf}")

    except Exception as e:
        print(f"Error reversing PDF {input_pdf}: {e}")
        play_sound('sounds/error.mp3')

def get_chapter_links(url, session):
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        chapters = soup.find("li", id="ceo_latest_comics_widget-3")
        links = chapters.find_all("li")

        return links

    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve chapter links from {url}: {e}")
        play_sound('sounds/error.mp3')
        return []

def chapter_name(link):
    try:
        url = link.find("a")["href"]
        start_index = url.find("manga/")
        if start_index != -1:
            start_index += len("manga/")
            end_index = url.find("/", start_index)
            if end_index != -1:
                return url[start_index:end_index]
        return None
    except (AttributeError, TypeError, KeyError) as e:
        print(f"Error extracting chapter name: {e}")
        play_sound('sounds/error.mp3')
        return None

def main():
    base_url = 'https://www.gachiakutascans.com/'

    with requests.Session() as session:
        session.headers.update({'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36'})

        links = get_chapter_links(base_url, session)

        for link in links:
            url = link.find("a")["href"]
            chapter_name_slug = chapter_name(link)
            if not chapter_name_slug:
                print("Invalid chapter name slug. Skipping...")
                play_sound('sounds/error.mp3')
                continue

            img_dir = os.path.join('fast_content', 'images', chapter_name_slug)
            input_pdf = os.path.join('fast_content', 'regular_pdfs', f"{chapter_name_slug}.pdf")
            output_pdf = os.path.join('fastcontent', 'reversed_pdfs', f"{chapter_name_slug}-reversed.pdf")

            print(f"CURRENTLY PROCESSING {img_dir}...")

            # Ensure output directories exist
            os.makedirs(os.path.dirname(input_pdf), exist_ok=True)
            os.makedirs(os.path.dirname(output_pdf), exist_ok=True)

            # Gather all the images from the specified URL
            scrape(url, chapter_name_slug, img_dir, session)

            # Turn those images into a PDF
            images_to_pdf(img_dir, input_pdf)

            # Reverse the PDF so it's readable
            reverse_pdf(input_pdf, output_pdf)

            print(f"COMPLETED PROCESSING {img_dir}.")
            print("===============================================")
            print()

        # After processing all chapters, notify completion
        print("ALL CHAPTERS DOWNLOADED!")
        if busted_chapters:
            print("Here is the list of all the chapters that had 'src' issues. You should probably check them:")
            print(pprint.pformat(busted_chapters))
        else:
            print("No chapters had 'src' issues.")

        # Play completion sound
        play_sound('sounds/done.mp3')

if __name__ == '__main__':
    main()
