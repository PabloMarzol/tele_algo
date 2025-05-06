import requests
import json
import logging
import os
from datetime import datetime
import polars as pl

class FinancialNewsFetcher:
    """Class to fetch financial news from Financial Modeling Prep API."""
    
    def __init__(self, api_key=None, api_url=None):
        """
        Initialize the news fetcher with API credentials.
        
        Args:
            api_key (str): API key for Financial Modeling Prep
            api_url (str): API URL
        """
        self.api_key = api_key or os.getenv("NEWS_API_KEY")
        self.api_url = api_url or os.getenv("NEWS_API_URL", "https://financialmodelingprep.com/api/v3")
        self.logger = logging.getLogger('FinancialNewsFetcher')
        
        if not self.api_key:
            self.logger.warning("No API key provided. Set NEWS_API_KEY environment variable or pass as parameter.")
    
    def fetch_news(self, tickers=None, limit=5):
        """
        Fetch news for specific tickers or general market news.
        
        Args:
            tickers (list): List of tickers to fetch news for, or None for general news
            limit (int): Maximum number of news items to fetch
        
        Returns:
            list: List of news item dictionaries
        """
        try:
            # Prepare API request parameters
            params = {
                "apikey": self.api_key,
                "limit": limit
            }
            
            # Add tickers if provided
            if tickers:
                if isinstance(tickers, list):
                    params["tickers"] = ",".join(tickers)
                else:
                    params["tickers"] = tickers
            
            # Make API request
            self.logger.info(f"Fetching news from {self.api_url}")
            response = requests.get(self.api_url, params=params)
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Parse response
            news_data = response.json()
            
            # Check if response is a list of news items
            if not isinstance(news_data, list):
                self.logger.error(f"Unexpected response format: {news_data}")
                return []
            
            # Format the news items
            formatted_news = []
            for item in news_data:
                # Extract values from the API response
                title = item.get("title", "No title available")
                text = item.get("text", "No content available")
                url = item.get("url", "")
                source = item.get("site", "Unknown source")
                published_date = item.get("publishedDate", datetime.now().isoformat())
                symbol = item.get("symbol", "")
                image = item.get("image", "")
                
                # Create a formatted item
                formatted_item = {
                    "title": title,
                    "summary": text,
                    "url": url,
                    "source": source,
                    "published_at": published_date,
                    "symbols": symbol.split(",") if symbol else [],
                    "image": image
                }
                
                formatted_news.append(formatted_item)
            
            # Store in polars DataFrame for easier analysis
            if formatted_news:
                self.news_df = pl.DataFrame(formatted_news)
                self.logger.info(f"Fetched {len(formatted_news)} news items")
            else:
                self.logger.warning("No news items found")
                self.news_df = pl.DataFrame(schema={
                    "title": pl.Utf8,
                    "summary": pl.Utf8,
                    "url": pl.Utf8,
                    "source": pl.Utf8,
                    "published_at": pl.Utf8,
                    "symbols": pl.List(pl.Utf8),
                    "image": pl.Utf8
                })
            
            return formatted_news
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request error: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Error fetching news: {e}")
            return []
    
    def get_forex_news(self, limit=5):
        """
        Fetch forex-specific news.
        
        Args:
            limit (int): Maximum number of news items to fetch
        
        Returns:
            list: List of news item dictionaries
        """
        # Use forex-related tickers
        forex_tickers = "EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD"
        return self.fetch_news(forex_tickers, limit)
    
    def get_commodity_news(self, limit=5):
        """
        Fetch commodity-specific news.
        
        Args:
            limit (int): Maximum number of news items to fetch
        
        Returns:
            list: List of news item dictionaries
        """
        # Use commodity-related tickers
        commodity_tickers = "XAUUSD, XAGUSD, OIL, COPPER"
        return self.fetch_news(commodity_tickers, limit)
    
    def format_news_message(self, news_items, title="📰 MARKET NEWS", include_images=False):
        """
        Format news items into a readable message.
        
        Args:
            news_items (list): List of news item dictionaries
            title (str): Title for the news message
            include_images (bool): Whether to include image URLs
        
        Returns:
            str: Formatted message
        """
        if not news_items:
            return "No financial news available at the moment."
        
        message = f"<b>{title}</b>\n\n"
        
        for i, item in enumerate(news_items[:5], 1):  # Limit to 5 news items
            # Add the title with a link
            message += f"{i}. <b><a href='{item['url']}'>{item['title']}</a></b>\n"
            
            # Add source and date
            published_date = item['published_at']
            if isinstance(published_date, str) and len(published_date) > 10:
                published_date = published_date[:10]  # Just show the date part
            
            message += f"   <i>{item['source']} - {published_date}</i>\n"
            
            # Add a short summary
            summary = item['summary']
            if len(summary) > 150:
                summary = summary[:147] + "..."
            message += f"   {summary}\n\n"
            
            # Add image URL if requested and available
            if include_images and item.get('image'):
                message += f"   <a href='{item['image']}'>🖼️</a>\n\n"
        
        message += "Stay informed with the latest market updates from VFX Trading! 📈"
        
        return message
    
    def save_recent_news(self, file_path="./bot_data/recent_news.json"):
        """
        Save the most recent news to a file for later reference.
        
        Args:
            file_path (str): Path to save the news
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            news_to_save = []
            if hasattr(self, 'news_df') and self.news_df.height > 0:
                news_to_save = self.news_df.to_dicts()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(news_to_save, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Saved {len(news_to_save)} news items to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving news: {e}")
            return False


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test with environment variables or direct API key
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        print("No API key found in environment. Using default.")
    
    fetcher = FinancialNewsFetcher(api_key=api_key)
    
    # Test general news
    news = fetcher.fetch_news(limit=3)
    if news:
        print("\nGeneral Market News:")
        for item in news:
            print(f"- {item['title']} ({item['source']})")
    
    # Test forex news
    forex_news = fetcher.get_forex_news(limit=3)
    if forex_news:
        print("\nForex News:")
        for item in forex_news:
            print(f"- {item['title']} ({item['source']})")
    
    # Test formatted message
    message = fetcher.format_news_message(news)
    print("\nFormatted Message:")
    print(message)
    
    # Test saving news
    fetcher.save_recent_news()