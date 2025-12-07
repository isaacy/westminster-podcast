import requests
from bs4 import BeautifulSoup
from podgen import Podcast, Episode, Media, Person, Category
from datetime import datetime, timedelta
import re
from urllib.parse import urljoin
import os

# Constants
BASE_URL = "https://www.westminster.org/messages/"
RSS_FILENAME = "podcast.xml"

def get_soup(url):
    """Fetches a URL and returns a BeautifulSoup object."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_date(date_str):
    """Parses date string like 'November 9, 2025'."""
    try:
        return datetime.strptime(date_str.strip(), "%B %d, %Y").replace(tzinfo=None) # Naive for now, podgen handles TZ
    except ValueError:
        return datetime.now()

def scrape_messages():
    """Scrapes the main messages page for message links."""
    soup = get_soup(BASE_URL)
    if not soup:
        return []

    messages = []
    # Find all links containing '/mediacast/'
    # We want to avoid duplicates and ensure we get the actual message pages
    seen_urls = set()
    
    for link in soup.find_all('a', href=True):
        href = link['href']
        # Normalize URL
        if href.startswith('/'):
            href = urljoin(BASE_URL, href)
            
        if '/mediacast/' in href and href != "https://www.westminster.org/mediacast/":
             if href not in seen_urls:
                 seen_urls.add(href)
                 messages.append({'url': href})
    
    return messages

def get_message_details(message_url):
    """Visits a message page and extracts details."""
    soup = get_soup(message_url)
    if not soup:
        return None

    details = {}
    details['url'] = message_url
    
    # Title - usually in an h1
    title_tag = soup.find('h1')
    details['title'] = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

    # Audio URL
    # Look for the audio tag as seen in research: 
    # <audio class="wp-audio-shortcode" ... src="...">
    audio_tag = soup.find('audio', class_='wp-audio-shortcode')
    if audio_tag:
        if audio_tag.get('src'):
            details['audio_url'] = audio_tag['src']
        elif audio_tag.find('source'):
            details['audio_url'] = audio_tag.find('source')['src']
        elif audio_tag.find('a'):
            details['audio_url'] = audio_tag.find('a')['href']
    
    if 'audio_url' not in details:
        print(f"No audio found for {message_url}")
        return None

    # Date and Speaker extraction from audio filename
    # Pattern: .../Messages/YYYY-MM-DD+Message+-+Speaker+Name.mp3
    audio_filename = details['audio_url'].split('/')[-1]
    
    # Date
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', audio_filename)
    if date_match:
        details['date'] = datetime.strptime(date_match.group(1), "%Y-%m-%d")
    else:
        # Fallback to current time if date not found
        details['date'] = datetime.now()

    # Speaker
    from urllib.parse import unquote
    decoded_filename = unquote(audio_filename)
    if " - " in decoded_filename:
        parts = decoded_filename.split(" - ")
        if len(parts) > 1:
            # Remove extension from last part
            speaker = parts[-1].replace(".mp3", "").strip()
            # Remove query params if any
            speaker = speaker.split("?")[0]
            details['speaker'] = speaker
    else:
        details['speaker'] = "Westminster Chapel"

    details['description'] = f"Message by {details.get('speaker', 'Unknown')} on {details['date'].strftime('%B %d, %Y')}"

    return details

def generate_feed(messages):
    """Generates the Podcast RSS feed."""
    p = Podcast(
        name="Westminster Chapel Messages",
        description="Audio messages from Westminster Chapel of Bellevue.",
        website=BASE_URL,
        explicit=False,
        image="https://isaacy.github.io/westminster-podcast/cover.png",
        authors=[Person("Westminster Chapel - Bellevue")],
        owner=Person("Westminster Chapel - Bellevue", "info@westminster.org"),
        category=Category("Religion & Spirituality", "Christianity"),
        language="en",
    )

    for msg in messages:
        if not msg: continue
        
        try:
            ep = Episode()
            ep.title = msg['title']
            ep.media = Media(msg['audio_url'], size=0, type="audio/mpeg")
            ep.summary = msg['description']
            ep.publication_date = msg['date'].replace(tzinfo=datetime.now().astimezone().tzinfo)
            ep.link = msg['url']
            if 'speaker' in msg:
                ep.authors = [Person(msg['speaker'])]
            
            p.add_episode(ep)
        except Exception as e:
            print(f"Error adding episode {msg.get('title')}: {e}")

    p.rss_file(RSS_FILENAME, minimize=True)
    print(f"Podcast feed generated: {RSS_FILENAME}")

def main():
    print("Scraping messages...")
    message_links = scrape_messages()
    print(f"Found {len(message_links)} potential message links.")
    
    details_list = []
    # Limit to last 20 for now
    for link_obj in message_links[:20]: 
        print(f"Processing {link_obj['url']}...")
        details = get_message_details(link_obj['url'])
        if details:
            details_list.append(details)
            print(f"  Found: {details['title']} - {details['date'].date()}")
    
    if details_list:
        generate_feed(details_list)
    else:
        print("No messages found to generate feed.")

if __name__ == "__main__":
    main()
