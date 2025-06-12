import requests
from bs4 import BeautifulSoup
import re
import zipfile
import io
import pandas as pd
from pathlib import Path
import time

def fetch_ff5_urls() -> dict[str, str]:
    """
    Fetch Fama/French 5 Factor URLs from Dartmouth website.
    Returns a dictionary mapping region names to CSV download URLs.
    """
    URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
    
    try:
        # Add headers to mimic a real browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        resp = requests.get(URL, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        print(f"✅ Successfully fetched webpage (status: {resp.status_code})")
        
        # Find all links that end with CSV.zip
        csv_links = soup.find_all("a", href=re.compile(r"CSV\.zip$", re.IGNORECASE))
        print(f"🔍 Found {len(csv_links)} total CSV.zip links")
        
        urls = {}
        
        # Look for specific patterns in the link text and surrounding context
        for link in csv_links:
            href = link.get("href", "")
            
            # Get the parent element to understand context
            parent = link.parent
            if parent:
                context_text = parent.get_text(" ", strip=True)
                
                # Debug: print context for analysis
                print(f"📄 Link context: {context_text[:100]}...")
                
                # Look for 5 Factors patterns and exclude Daily data
                if "5 Factors" in context_text and "Daily" not in context_text:
                    
                    # Extract region information
                    if "North American" in context_text or "North America" in context_text:
                        region_key = "Fama/French North American 5 Factors"
                    elif "European" in context_text or "Europe" in context_text:
                        region_key = "Fama/French European 5 Factors"
                    elif "Asia Pacific ex Japan" in context_text:
                        region_key = "Fama/French Asia Pacific ex Japan 5 Factors"
                    elif "Asia Pacific" in context_text and "Japan" not in context_text:
                        region_key = "Fama/French Asia Pacific ex Japan 5 Factors"
                    else:
                        # Try to extract a more general region name
                        region_match = re.search(r"Fama/French\s+([^TXT]+?)\s+5\s+Factors", context_text)
                        if region_match:
                            region_key = f"Fama/French {region_match.group(1).strip()} 5 Factors"
                        else:
                            continue
                    
                    # Construct full URL if needed
                    if href.startswith("/"):
                        full_url = "https://mba.tuck.dartmouth.edu" + href
                    else:
                        full_url = href
                    
                    urls[region_key] = full_url
                    print(f"✅ Added: {region_key} -> {full_url}")
        
        # Alternative approach: Look for specific table structures
        if not urls:
            print("🔄 Trying alternative parsing approach...")
            
            # Find all table rows and look for factor data
            rows = soup.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 3:  # Expecting description, TXT, CSV, Details columns
                    row_text = " ".join([cell.get_text(" ", strip=True) for cell in cells])
                    
                    if "5 Factors" in row_text and "Daily" not in row_text:
                        # Find CSV link in this row
                        csv_link = row.find("a", href=re.compile(r"CSV\.zip$", re.IGNORECASE))
                        if csv_link:
                            href = csv_link.get("href", "")
                            
                            # Extract region from row text
                            if "North American" in row_text:
                                region_key = "Fama/French North American 5 Factors"
                            elif "European" in row_text:
                                region_key = "Fama/French European 5 Factors"
                            elif "Asia Pacific ex Japan" in row_text:
                                region_key = "Fama/French Asia Pacific ex Japan 5 Factors"
                            else:
                                continue
                            
                            if href.startswith("/"):
                                full_url = "https://mba.tuck.dartmouth.edu" + href
                            else:
                                full_url = href
                            
                            urls[region_key] = full_url
                            print(f"✅ Added (alt method): {region_key} -> {full_url}")
        
        print(f"🎯 Final result: Found {len(urls)} FF5 factor files")
        return urls
        
    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
        raise RuntimeError(f"Failed to fetch webpage: {e}")
    except Exception as e:
        print(f"❌ Parsing error: {e}")
        raise RuntimeError(f"Failed to parse webpage: {e}")

def download_and_extract_ff5_data():
    """
    Download and extract Fama/French 5 Factor data to local folders.
    """
    urls = fetch_ff5_urls()
    
    if not urls:
        raise RuntimeError("No FF5 URLs found to download")
    
    # Create data directory
    data_dir = Path("ff5_data")
    data_dir.mkdir(exist_ok=True)
    
    for region, url in urls.items():
        try:
            print(f"📥 Downloading {region}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Extract ZIP file
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                file_list = zip_file.namelist()
                print(f"📦 ZIP contains: {file_list}")
                
                for file_name in file_list:
                    if file_name.lower().endswith('.txt'):
                        # Extract and save the data file
                        with zip_file.open(file_name) as data_file:
                            content = data_file.read().decode('utf-8')
                            
                            # Clean region name for filename
                            clean_name = re.sub(r'[^\w\s-]', '', region).strip()
                            clean_name = re.sub(r'[-\s]+', '_', clean_name)
                            
                            output_file = data_dir / f"{clean_name}.txt"
                            with open(output_file, 'w', encoding='utf-8') as f:
                                f.write(content)
                            
                            print(f"✅ Saved: {output_file}")
            
            # Add small delay to be respectful to the server
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Failed to download {region}: {e}")
            continue
    
    print("🎉 Download process completed!")

if __name__ == "__main__":
    print("🚀 Testing Fama/French URL scraper...")
    
    try:
        urls = fetch_ff5_urls()
        print("\n" + "="*60)
        print("✅ SCRAPING SUCCESSFUL!")
        print("="*60)
        
        for region, url in urls.items():
            print(f"📡 {region}")
            print(f"   🔗 {url}")
            print()
        
        print(f"📊 Total regions found: {len(urls)}")
        
        # Test download functionality
        if urls:
            print("\n🔄 Testing download functionality...")
            download_and_extract_ff5_data()
            
    except Exception as e:
        print(f"\n❌ SCRAPING FAILED: {e}")
        import traceback
        traceback.print_exc()
