
import os
import json
import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy
import logging
from typing import Dict, Any, Optional

class DetailPageContentExtractor:
    def __init__(self, 
                 api_key: str, 
                 provider: str, 
                 instruction: str,
                 log_file: str = 'logs/DetailPage.log'):
        """
        Initialize the DetailPageContentExtractor.

        Args:
        - api_key (str): The API key for the LLM provider.
        - provider (str): The LLM provider.
        - instruction (str): The instruction for the LLM.
        - log_file (str, optional): Path to the log file. Defaults to 'DetailPage.log'.
        """
        # Validate input parameters
        if not all([api_key, provider, instruction]):
            raise ValueError("API key, provider, and instruction must be non-empty")

        self.api_key = api_key
        self.provider = provider
        self.instruction = instruction
        
        # Configure logging
        self._setup_logging(log_file)
    
    def _setup_logging(self, log_file: str):
        """
        Set up logging configuration.

        Args:
        - log_file (str): Path to the log file.
        """
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        # Create logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        
        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
        
    async def extract_detail_content(self, url: str):
        """
        Extract tech content from the crawled URL.

        Args:
        - url (str): The URL to crawl.

        Returns:
        - Optional[Dict[str, Any]]: The extracted detail content or None if extraction fails.
        """
        # Validate input URL
        if not url:
            self.logger.error("URL is not set. Cannot proceed with extraction.")
            return None

        try:
            # Create AsyncWebCrawler with logging context
            async with AsyncWebCrawler(verbose=True) as crawler:
                self.logger.info(f"Attempting to extract content from URL: {url}")
                
                # Perform crawling with extraction strategy
                result = await crawler.arun(
                    url=url,
                    extraction_strategy=LLMExtractionStrategy(
                        provider=self.provider,
                        api_token=self.api_key,
                        instruction=self.instruction
                    ),
                    bypass_cache=True,
                )

            # Validate crawling result
            if result is None:
                self.logger.error(f"Crawling failed for URL: {url}. Result is None.")
                return None

            # Validate extracted content
            if result.extracted_content is None:
                self.logger.error(f"No content extracted from URL: {url}")
                return None

            # Parse extracted content
            try:
                detail_content = json.loads(result.extracted_content)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse extracted content as JSON for URL {url}: {e}")
                return None

            # Log successful extraction
            self.logger.info(f"Successfully extracted {len(detail_content)} tech-related items from {url}")
            return detail_content

        except Exception as e:
            # Catch and log any unexpected errors
            self.logger.error(f"Unexpected error during content extraction from {url}: {e}", exc_info=True)
            return None
    
    def reset(self, api_key: str = None, provider: str = None, instruction: str = None):
        """
        Reset the extractor's configuration.

        Args:
        - api_key (str, optional): New API key.
        - provider (str, optional): New provider.
        - instruction (str, optional): New instruction.
        """
        if api_key is not None:
            self.api_key = api_key
        if provider is not None:
            self.provider = provider
        if instruction is not None:
            self.instruction = instruction
        
        self.logger.info("Extractor configuration updated")

def main():
    api_key = os.environ.get('GEMINI_API_KEY')
    url = "https://techcrunch.com/2024/11/28/linkup-connects-llms-with-premium-content-sources-legally/"
    provider = "gemini/gemini-pro"

    instruction = """ From the crawled content, Extract the following information:
        title: the title of the news article
        summary: a about-100-word summary of the news content
        key_words: top 3 relevant words separated by commas
        Output the extracted information in a single JSON object with the following format:
        [{ title: "", summary: "", key_words: ""}]"
    """
    
    extractor = DetailPageContentExtractor(api_key, provider, instruction)
    detail_content = asyncio.run(extractor.extract_detail_content(url))

    if detail_content is not None:
        print("Extracted detail content:")
        print(detail_content)
        # print(json.dumps(detail_content, indent=2, ensure_ascii=False))
    else:
        print("Failed to extract detail content.")

if __name__ == "__main__":
    main()