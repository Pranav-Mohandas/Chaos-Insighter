import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import json
import csv
from urllib.parse import urljoin, urlparse
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sqlite3
from datetime import datetime
import schedule
from openai import OpenAI
import threading
import os
import streamlit as st
import os
# Removed redundant import as WebDataHarvester is already defined in this file

class WebDataHarvester:
    def __init__(self):
        # Initialize OpenAI client for insights
        self.client = OpenAI(
            api_key="8124c85892537a0bfcdae4b999e4eba2909c367431cab6a72589c2278e4c2cc4",
            base_url="https://api.together.xyz/v1"
        )
        self.model_name = "meta-llama/Llama-3.3-70B-Instruct-Turbo"

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('crawler.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # Initialize database
        self.init_database()

        # Selenium setup
        self.setup_selenium()

        # Default headers for requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Rate limiting
        self.request_delay = 2  # seconds between requests

    def init_database(self):
        """Initialize SQLite database for storing scraped data"""
        self.conn = sqlite3.connect('harvested_data.db', check_same_thread=False)
        self.cursor = self.conn.cursor()

        # Create tables
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraped_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                title TEXT,
                content TEXT,
                metadata TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_type TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_id INTEGER,
                insight_type TEXT,
                insight_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (data_id) REFERENCES scraped_data (id)
            )
        ''')

        self.conn.commit()

    def setup_selenium(self):
        """Setup Selenium WebDriver for JavaScript-heavy sites"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run in background
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.logger.info("Selenium WebDriver initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Selenium: {e}")
            self.driver = None

    def simple_scrape(self, url: str, selectors: dict = None) -> dict:
        """Simple BeautifulSoup-based scraping for static content"""
        try:
            time.sleep(self.request_delay)  # Rate limiting

            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Default extraction
            data = {
                'url': url,
                'title': soup.find('title').get_text(strip=True) if soup.find('title') else 'No Title',
                'content': soup.get_text(strip=True),
                'metadata': {
                    'status_code': response.status_code,
                    'content_type': response.headers.get('content-type', ''),
                    'scraped_method': 'simple'
                }
            }

            # Custom selectors
            if selectors:
                for key, selector in selectors.items():
                    elements = soup.select(selector)
                    data[key] = [elem.get_text(strip=True) for elem in elements]

            self.logger.info(f"Successfully scraped: {url}")
            return data

        except Exception as e:
            self.logger.error(f"Error scraping {url}: {e}")
            return None

    def dynamic_scrape(self, url: str, selectors: dict = None, wait_for: str = None) -> dict:
        """Selenium-based scraping for JavaScript-heavy sites"""
        if not self.driver:
            self.logger.error("Selenium driver not available")
            return None

        try:
            self.driver.get(url)

            # Wait for specific element if specified
            if wait_for:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_for))
                )
            else:
                time.sleep(3)  # Default wait

            # Extract basic data
            title = self.driver.title
            content = self.driver.find_element(By.TAG_NAME, "body").text

            data = {
                'url': url,
                'title': title,
                'content': content,
                'metadata': {
                    'scraped_method': 'dynamic',
                    'page_source_length': len(self.driver.page_source)
                }
            }

            # Custom selectors
            if selectors:
                for key, selector in selectors.items():
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        data[key] = [elem.text for elem in elements]
                    except Exception as e:
                        self.logger.warning(f"Selector {selector} failed: {e}")
                        data[key] = []

            self.logger.info(f"Successfully scraped (dynamic): {url}")
            return data

        except Exception as e:
            self.logger.error(f"Error dynamic scraping {url}: {e}")
            return None

    # def crawl_sitemap(self, sitemap_url: str) -> list:
    #     """Extract URLs from sitemap"""
    #     try:
    #         response = requests.get(sitemap_url, headers=self.headers)
    #         soup = BeautifulSoup(response.content, 'xml')

    #         urls = []
    #         for url_tag in soup.find_all('url'):
    #             loc = url_tag.find('loc')
    #             if loc:
    #                 urls.append(loc.text)

    #         self.logger.info(f"Found {len(urls)} URLs in sitemap")
    #         return urls

    #     except Exception as e:
    #         self.logger.error(f"Error crawling sitemap {sitemap_url}: {e}")
    #         return []
    def crawl_sitemap(self, sitemap_url: str) -> list:
        try:
            response = requests.get(sitemap_url, headers=self.headers)
            soup = BeautifulSoup(response.content, 'xml')
            urls = []

            # Handle regular URLs
            for url_tag in soup.find_all('url'):
                loc = url_tag.find('loc')
                if loc:
                    urls.append(loc.text)

            # Handle sitemap indexes recursively
            for sitemap_tag in soup.find_all('sitemap'):
                loc = sitemap_tag.find('loc')
                if loc:
                    # Recursively crawl each sitemap
                    urls.extend(self.crawl_sitemap(loc.text))

            self.logger.info(f"Found {len(urls)} URLs in sitemap")
            return urls

        except Exception as e:
            self.logger.error(f"Error crawling sitemap {sitemap_url}: {e}")
            return []


    def bulk_scrape(self, urls: list, scrape_type: str = 'simple', selectors: dict = None) -> list:
        """Scrape multiple URLs"""
        results = []

        for i, url in enumerate(urls):
            self.logger.info(f"Scraping {i+1}/{len(urls)}: {url}")

            if scrape_type == 'simple':
                data = self.simple_scrape(url, selectors)
            elif scrape_type == 'dynamic':
                data = self.dynamic_scrape(url, selectors)
            else:
                self.logger.error(f"Unknown scrape type: {scrape_type}")
                continue

            if data:
                results.append(data)
                self.store_data(data)

        return results

    def store_data(self, data: dict) -> int:
        """Store scraped data in database"""
        try:
            self.cursor.execute('''
                INSERT INTO scraped_data (url, title, content, metadata, source_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                data['url'],
                data['title'],
                data['content'],
                json.dumps(data['metadata']),
                data['metadata'].get('scraped_method', 'unknown')
            ))

            data_id = self.cursor.lastrowid
            self.conn.commit()
            self.logger.info(f"Stored data with ID: {data_id}")
            return data_id

        except Exception as e:
            self.logger.error(f"Error storing data: {e}")
            return None

    def generate_insights(self, data_id: int = None) -> str:
        """Generate AI insights from scraped data"""
        try:
            if data_id:
                # Analyze specific data
                self.cursor.execute('SELECT * FROM scraped_data WHERE id = ?', (data_id,))
                row = self.cursor.fetchone()
                if not row:
                    return "Data not found"

                content = row[3]  # content column
                title = row[2]   # title column
            else:
                # Analyze recent data
                self.cursor.execute('''
                    SELECT title, content FROM scraped_data
                    ORDER BY scraped_at DESC LIMIT 10
                ''')
                rows = self.cursor.fetchall()

                if not rows:
                    return "No data available for analysis"

                content = "\n\n".join([f"Title: {row[0]}\nContent: {row[1][:500]}..." for row in rows])
                title = "Recent scraped data"

            prompt = f"""Analyze the following scraped web data and provide comprehensive insights:

Title: {title}

Content:
{content[:4000]}

Please provide:
1. Key themes and topics identified
2. Important information or trends
3. Data quality assessment
4. Potential use cases for this data
5. Recommendations for further analysis

Insights:"""

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500
            )

            insights = response.choices[0].message.content.strip()

            # Store insights
            if data_id:
                self.cursor.execute('''
                    INSERT INTO insights (data_id, insight_type, insight_content)
                    VALUES (?, ?, ?)
                ''', (data_id, 'ai_analysis', insights))
                self.conn.commit()

            return insights

        except Exception as e:
            self.logger.error(f"Error generating insights: {e}")
            return f"Error generating insights: {e}"

    def export_data(self, format_type: str = 'csv', filename: str = None) -> str:
        """Export scraped data to various formats"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"scraped_data_{timestamp}"

        try:
            # Get data from database
            df = pd.read_sql_query('SELECT * FROM scraped_data', self.conn)

            if format_type.lower() == 'csv':
                filepath = f"{filename}.csv"
                df.to_csv(filepath, index=False)
            elif format_type.lower() == 'excel':
                filepath = f"{filename}.xlsx"
                df.to_excel(filepath, index=False)
            elif format_type.lower() == 'json':
                filepath = f"{filename}.json"
                df.to_json(filepath, orient='records', indent=2)
            else:
                return f"Unsupported format: {format_type}"

            self.logger.info(f"Data exported to: {filepath}")
            return filepath

        except Exception as e:
            self.logger.error(f"Error exporting data: {e}")
            return f"Error: {e}"

    def schedule_scraping(self, urls: list, interval_hours: int = 24):
        """Schedule periodic scraping"""
        def job():
            self.logger.info("Running scheduled scraping...")
            self.bulk_scrape(urls)
            self.logger.info("Scheduled scraping completed")

        schedule.every(interval_hours).hours.do(job)

        self.logger.info(f"Scheduled scraping every {interval_hours} hours")

        # Run scheduler in background
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(60)

        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

    def close(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
        if self.conn:
            self.conn.close()

# Example usage and main interface
def main():
    harvester = WebDataHarvester()

    print("🕸️  Welcome to Web Data Harvester!")
    print("="*50)

    try:
        while True:
            print("\nOptions:")
            print("1. Scrape single URL")
            print("2. Bulk scrape from URL list")
            print("3. Crawl sitemap")
            print("4. Generate insights")
            print("5. Export data")
            print("6. Schedule periodic scraping")
            print("7. View scraped data summary")
            print("8. Exit")

            choice = input("\nEnter your choice (1-8): ").strip()

            if choice == "1":
                url = input("Enter URL to scrape: ").strip()
                scrape_type = input("Scraping type (simple/dynamic) [simple]: ").strip() or 'simple'

                if scrape_type == 'simple':
                    data = harvester.simple_scrape(url)
                else:
                    data = harvester.dynamic_scrape(url)

                if data:
                    data_id = harvester.store_data(data)
                    print(f"✅ Successfully scraped and stored with ID: {data_id}")

                    generate = input("Generate insights? (y/n) [y]: ").strip().lower()
                    if generate != 'n':
                        print("🔍 Generating insights...")
                        insights = harvester.generate_insights(data_id)
                        print("\n📊 INSIGHTS:")
                        print("="*40)
                        print(insights)
                        print("="*40)
                else:
                    print("❌ Failed to scrape URL")

            elif choice == "2":
                urls_input = input("Enter URLs (comma-separated): ").strip()
                urls = [url.strip() for url in urls_input.split(',')]

                scrape_type = input("Scraping type (simple/dynamic) [simple]: ").strip() or 'simple'

                print(f"🕸️  Starting bulk scrape of {len(urls)} URLs...")
                results = harvester.bulk_scrape(urls, scrape_type)
                print(f"✅ Completed! Scraped {len(results)} URLs successfully")

            elif choice == "3":
                sitemap_url = input("Enter sitemap URL: ").strip()
                urls = harvester.crawl_sitemap(sitemap_url)

                if urls:
                    print(f"Found {len(urls)} URLs in sitemap")
                    proceed = input("Proceed with scraping all URLs? (y/n) [y]: ").strip().lower()

                    if proceed != 'n':
                        scrape_type = input("Scraping type (simple/dynamic) [simple]: ").strip() or 'simple'
                        results = harvester.bulk_scrape(urls[:50], scrape_type)  # Limit to 50
                        print(f"✅ Scraped {len(results)} URLs from sitemap")
                else:
                    print("❌ No URLs found in sitemap")

            elif choice == "4":
                insights = harvester.generate_insights()
                print("\n📊 RECENT DATA INSIGHTS:")
                print("="*50)
                print(insights)
                print("="*50)

            elif choice == "5":
                format_type = input("Export format (csv/excel/json) [csv]: ").strip() or 'csv'
                filename = input("Filename (optional): ").strip() or None

                filepath = harvester.export_data(format_type, filename)
                print(f"📁 Data exported to: {filepath}")

            elif choice == "6":
                urls_input = input("Enter URLs to schedule (comma-separated): ").strip()
                urls = [url.strip() for url in urls_input.split(',')]

                hours = input("Interval in hours [24]: ").strip()
                hours = int(hours) if hours.isdigit() else 24

                harvester.schedule_scraping(urls, hours)
                print(f"⏰ Scheduled scraping every {hours} hours")

            elif choice == "7":
                # Show data summary
                harvester.cursor.execute('SELECT COUNT(*) FROM scraped_data')
                total_records = harvester.cursor.fetchone()[0]

                harvester.cursor.execute('''
                    SELECT source_type, COUNT(*)
                    FROM scraped_data
                    GROUP BY source_type
                ''')
                type_counts = harvester.cursor.fetchall()

                print(f"\n📈 Data Summary:")
                print(f"Total records: {total_records}")
                print("By scraping method:")
                for source_type, count in type_counts:
                    print(f"  - {source_type}: {count}")

            elif choice == "8":
                print("👋 Thanks for using Web Data Harvester!")
                break

            else:
                print("❌ Invalid choice. Please enter 1-8.")

    finally:
        harvester.close()


def streamlit_app():
    st.set_page_config(page_title="🕸️ Web Data Harvester", page_icon="🌐")

    st.title("🕸️ Web Data Harvester")
    st.markdown("Scrape websites, analyze content, and export results with AI-powered insights.")

    # Initialize harvester in session state
    if "harvester" not in st.session_state:
        st.session_state.harvester = WebDataHarvester()

    harvester = st.session_state.harvester

    # Sidebar for navigation
    st.sidebar.title("Navigation")
    option = st.sidebar.radio("Choose Action", [
        "Scrape Single URL",
        "Bulk Scrape",
        "Crawl Sitemap",
        "Generate Insights",
        "Export Data",
        "Data Summary"
    ])

    if option == "Scrape Single URL":
        url = st.text_input("Enter URL to scrape")
        scrape_type = st.radio("Scraping type", ["simple", "dynamic"], index=0)
        if st.button("Scrape URL"):
            with st.spinner("Scraping..."):
                if scrape_type == "simple":
                    data = harvester.simple_scrape(url)
                else:
                    data = harvester.dynamic_scrape(url)

                if data:
                    data_id = harvester.store_data(data)
                    st.success(f"✅ Scraped and stored with ID: {data_id}")
                    st.subheader("Scraped Content")
                    st.write(data["content"][:1000] + "...")
                    if st.checkbox("Generate Insights now?"):
                        insights = harvester.generate_insights(data_id)
                        st.subheader("📊 Insights")
                        st.write(insights)
                else:
                    st.error("❌ Failed to scrape URL")

    elif option == "Bulk Scrape":
        urls_input = st.text_area("Enter URLs (one per line)")
        scrape_type = st.radio("Scraping type", ["simple", "dynamic"], index=0)
        if st.button("Start Bulk Scraping"):
            urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
            with st.spinner("Scraping in progress..."):
                results = harvester.bulk_scrape(urls, scrape_type)
                st.success(f"✅ Completed scraping {len(results)} URLs")

    elif option == "Crawl Sitemap":
        sitemap_url = st.text_input("Enter sitemap URL")
        if st.button("Crawl Sitemap"):
            with st.spinner("Crawling sitemap..."):
                urls = harvester.crawl_sitemap(sitemap_url)
                if urls:
                    st.success(f"Found {len(urls)} URLs in sitemap")
                    st.write(urls[:20])
                else:
                    st.error("❌ No URLs found in sitemap")

    elif option == "Generate Insights":
        st.markdown("Generate AI insights on recent or specific scraped data.")
        data_id = st.text_input("Enter data ID (optional)")
        if st.button("Generate Insights"):
            with st.spinner("Analyzing scraped data..."):
                insights = harvester.generate_insights(int(data_id) if data_id else None)
                st.subheader("📊 Insights")
                st.write(insights)

    elif option == "Export Data":
        format_type = st.selectbox("Select export format", ["csv", "excel", "json"])
        filename = st.text_input("Custom filename (optional)")
        if st.button("Export"):
            with st.spinner("Exporting data..."):
                filepath = harvester.export_data(format_type, filename)
                if "Error" not in filepath:
                    st.success(f"📁 Data exported: {filepath}")
                else:
                    st.error(filepath)

    elif option == "Data Summary":
        st.markdown("### 📈 Scraped Data Summary")
        try:
            harvester.cursor.execute("SELECT COUNT(*) FROM scraped_data")
            total_records = harvester.cursor.fetchone()[0]

            harvester.cursor.execute('''
                SELECT source_type, COUNT(*) 
                FROM scraped_data 
                GROUP BY source_type
            ''')
            type_counts = harvester.cursor.fetchall()

            st.write(f"**Total Records:** {total_records}")
            for source_type, count in type_counts:
                st.write(f"- {source_type}: {count}")

        except Exception as e:
            st.error(f"Error fetching summary: {e}")

if __name__ == "__main__":
    streamlit_app()    
    
    
