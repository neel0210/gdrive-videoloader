from urllib.parse import unquote, urlparse, parse_qs
import requests
import argparse
import sys
from tqdm import tqdm
import os
import re

def extract_video_id(link_or_id: str) -> str:
    """Extract video ID whether input is a full Google Drive link or just an ID."""
    # Case 1: Already looks like an ID
    if re.match(r'^[\w-]{20,}$', link_or_id):  # Drive IDs are usually long (25+ chars)
        return link_or_id
    
    # Case 2: It's a link, try to parse
    parsed = urlparse(link_or_id)
    query = parse_qs(parsed.query)

    # Link format: https://drive.google.com/file/d/<ID>/view
    match = re.search(r'/d/([\w-]+)', parsed.path)
    if match:
        return match.group(1)

    # Link format: https://drive.google.com/open?id=<ID>
    if "id" in query:
        return query["id"][0]

    # Fallback: return input
    return link_or_id

def get_video_url(page_content: str, verbose: bool) -> tuple[str, str]:
    """Extracts the video playback URL and title from the page content."""
    if verbose:
        print("[INFO] Parsing video playback URL and title.")
    contentList = page_content.split("&")
    video, title = None, None
    for content in contentList:
        if content.startswith('title=') and not title:
            title = unquote(content.split('=')[-1])
        elif "videoplayback" in content and not video:
            video = unquote(content).split("|")[-1]
        if video and title:
            break

    if verbose:
        print(f"[INFO] Video URL: {video}")
        print(f"[INFO] Video Title: {title}")
    return video, title

def download_file(url: str, cookies: dict, filename: str, chunk_size: int, verbose: bool) -> None:
    """Downloads the file from the given URL with provided cookies, supports resuming."""
    headers = {}
    file_mode = 'wb'

    downloaded_size = 0
    if os.path.exists(filename):
        downloaded_size = os.path.getsize(filename)
        headers['Range'] = f"bytes={downloaded_size}-"
        file_mode = 'ab'

    if verbose:
        print(f"[INFO] Starting download from {url}")
        if downloaded_size > 0:
            print(f"[INFO] Resuming download from byte {downloaded_size}")

    response = requests.get(url, stream=True, cookies=cookies, headers=headers)
    if response.status_code in (200, 206):  # 200 for new downloads, 206 for partial content
        total_size = int(response.headers.get('content-length', 0)) + downloaded_size
        with open(filename, file_mode) as file:
            with tqdm(total=total_size, initial=downloaded_size, unit='B', unit_scale=True, desc=filename, file=sys.stdout) as pbar:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        file.write(chunk)
                        pbar.update(len(chunk))
        print(f"\n{filename} downloaded successfully.")
    else:
        print(f"Error downloading {filename}, status code: {response.status_code}")

def sanitize_filename(filename: str) -> str:
    """Sanitizes the filename by removing invalid characters and normalizing."""
    # Replace '+' with spaces
    filename = filename.replace('+', ' ')
    
    # Remove invalid characters for Windows and Unix systems
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)
    
    filename = filename.strip()
    
    # Ensure file has an extension (default to .mp4)
    if not os.path.splitext(filename)[1]:
        filename += ".mp4"
    
    return filename

def main(video_input: str, output_file: str = None, chunk_size: int = 1024, verbose: bool = False) -> None:
    """Main function to process video input (link or ID) and download the video file."""
    video_id = extract_video_id(video_input)
    drive_url = f'https://drive.google.com/u/0/get_video_info?docid={video_id}&drive_originator_app=303'
    
    if verbose:
        print(f"[INFO] Accessing {drive_url}")

    response = requests.get(drive_url)
    page_content = response.text
    cookies = response.cookies.get_dict()

    video, title = get_video_url(page_content, verbose)

    filename = output_file if output_file else title
    filename = sanitize_filename(filename)
    
    if verbose and filename != (output_file if output_file else title):
        print(f"[INFO] Filename sanitized to: {filename}")

    if video:
        download_file(video, cookies, filename, chunk_size, verbose)
    else:
        print("Unable to retrieve the video URL. Ensure the video link/ID is correct and accessible.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script to download videos from Google Drive.")
    parser.add_argument("video_input", type=str, help="The Google Drive video link or video ID.")
    parser.add_argument("-o", "--output", type=str, help="Optional output file name for the downloaded video (default: video name in gdrive).")
    parser.add_argument("-c", "--chunk_size", type=int, default=1024, help="Optional chunk size (in bytes) for downloading the video. Default is 1024 bytes.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose mode.")
    parser.add_argument("--version", action="version", version="%(prog)s 1.0")

    args = parser.parse_args()
    main(args.video_input, args.output, args.chunk_size, args.verbose)
