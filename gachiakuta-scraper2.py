import os
import requests
import PyPDF2
import img2pdf
import pdb
import sys
import pprint
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from playsound import playsound  # Import playsound

# Initialize a list to store chapters with missing 'src' attributes
busted_chapters = []

def scrape(url, chapter_name_slug, img_dir):
    try:
        # Send a GET request to the webpage, and then parse the HTML content
        response = requests.get(url)
        response.raise_for_status()  # Check for request errors
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all the images (update selectors based on the website's structure)
        main_div = soup.find('div', class_='entry-content')
        img_tags = main_div.find_all('img', class_='article_ed__img')

        # Create a directory to store downloaded images
        if not os.path.exists(img_dir):
            os.makedirs(img_dir)

        # Loop through all <img> tags and download images
        i = 1
        for img_tag in img_tags:
            try:
                img_url = img_tag['src']
            except KeyError:
                # Add chapter to busted_chapters if 'src' is missing
                busted_chapters.append(chapter_name_slug)
                print(f"Error: 'src' attribute missing in chapter '{chapter_name_slug}'. Skipping...")
                playsound('sounds/error.mp3')  # Play error sound
                continue

            img_name = f"{chapter_name_slug}-page-{i}"
            img_extension = os.path.splitext(urlparse(img_url).path)[-1]  # Ensure the image has an extension
            img_path = os.path.join(img_dir, img_name + img_extension)  # Path to save the image

            try:
                # Download image content
                img_response = requests.get(img_url)
                img_response.raise_for_status()  # Check for request errors

                # Save image content to file
                with open(img_path, 'wb') as img_file:
                    img_file.write(img_response.content)

                print(f"Downloaded: {img_name}")
            except requests.exceptions.RequestException as e:
                # Handle download errors
                print(f"Error downloading {img_url}: {e}")
                playsound('sounds/error.mp3')  # Play error sound
                busted_chapters.append(chapter_name_slug)
                continue

            i += 1

        print("All images downloaded successfully.")

    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve URL {url}: {e}")
        playsound('sounds/error.mp3')  # Play error sound

def images_to_pdf(directory, output_name):
    try:
        # List all files in the directory and filter only JPEG images (ending with ".jpg")
        image_files = [i for i in os.listdir(directory) if i.endswith(".jpg") or i.endswith(".jpeg")]

        # Sort the image files based on page number
        image_files = sorted(image_files, key=lambda x: int(x.split('-page-')[1].split('.')[0]))

        # Initialize a list to store image data
        image_data = []

        # Read each image file and add its data to the list
        for image_file in image_files:
            with open(os.path.join(directory, image_file), "rb") as f:
                image_data.append(f.read())

        # Convert the list of image data to a single PDF file
        pdf_data = img2pdf.convert(image_data)

        # Write the PDF content to a file
        with open(output_name, "wb") as file:
            file.write(pdf_data)

        print("PDF MADE!")

    except Exception as e:
        print(f"Error creating PDF {output_name}: {e}")
        playsound('sounds/error.mp3')  # Play error sound

def reverse_pdf(input_pdf, output_pdf):
    try:
        # Open the input PDF file
        with open(input_pdf, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            writer = PyPDF2.PdfWriter()

            # Reverse the order of pages
            for page_num in range(len(reader.pages) - 1, -1, -1):
                writer.add_page(reader.pages[page_num])

            # Write the reversed PDF to the output file
            with open(output_pdf, 'wb') as output_file:
                writer.write(output_file)

        playsound('sounds/success.mp3')
        print("PDF REVERSED!")

    except Exception as e:
        print(f"Error reversing PDF {input_pdf}: {e}")
        playsound('sounds/error.mp3')  # Play error sound

def get_chapter_links(url):
    try:
        # Send a GET request to the webpage, and then parse the HTML content
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        chapters = soup.find("li", id="ceo_latest_comics_widget-3")
        links = chapters.find_all("li")

        return links

    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve chapter links from {url}: {e}")
        playsound('sounds/error.mp3')  # Play error sound
        return []

def chapter_name(link):
    try:
        # Find the URL within the <a> tag
        url = link.find("a")["href"]

        # Find the position of "manga/" in the URL
        start_index = url.find("manga/")
        if start_index != -1:  # Check if "manga/" was found
            start_index += len("manga/")
            # Find the position of the next "/" after "manga/"
            end_index = url.find("/", start_index)
            if end_index != -1:  # Check if "/" was found
                # Extract the desired substring
                return url[start_index:end_index]
        # Return None if "manga/" or "/" was not found
        return None

    except (AttributeError, TypeError, KeyError) as e:
        print(f"Error extracting chapter name: {e}")
        playsound('sounds/error.mp3')  # Play error sound
        return None

def main():
    # Get all of the links to each chapter
    links = get_chapter_links('https://www.gachiakutascans.com/')

    for link in links:
        url = link.find("a")["href"]
        chapter_name_slug = chapter_name(link)
        if not chapter_name_slug:
            print("Invalid chapter name slug. Skipping...")
            playsound('sounds/error.mp3')  # Play error sound
            continue

        img_dir = f'all_content/images/{chapter_name_slug}'
        input_name = f'all_content/regular_pdfs/{chapter_name_slug}.pdf'
        output_name = f'all_content/reversed_pdfs/{chapter_name_slug}-reversed.pdf'

        print(f"CURRENTLY PROCESSING {img_dir}...")

        # Gather all the images from the specified URL
        scrape(url, chapter_name_slug, img_dir)

        # Turn those images into a PDF
        images_to_pdf(img_dir, input_name)

        # Reverse the PDF so it's readable
        reverse_pdf(input_name, output_name)

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
    playsound('sounds/done.mp3')

if __name__ == '__main__':
    main()
