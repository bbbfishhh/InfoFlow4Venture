import os
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from DetailPageExtractor import DetailPageContentExtractor
from pymongo import MongoClient

class TechFinancingNews(BaseModel):
    title: str = Field(..., description="The title of the News.")
    tag: str = Field(..., description="The tag which shows the type of the news")
    further_url: str = Field(..., description="The further url of the title which leads to the detailed page")
    post_time: str = Field(..., description="The time when the news was posted")
    summary: str = Field(..., description="keep it to None")
    key_words: str = Field(..., description="keep it to None")

class TechFinancingNewsExtractor:
    def __init__(self, 
                 mongodb_uri: str = "mongodb://localhost:27017/",
                 database_name: str = "InfoFlow",
                 api_key: str = None, 
                 provider: str = 'gemini/gemini-pro', 
                 detail_instruction: str = None,
                 log_file: str = 'logs/DetailPage.log'):
        
        # 设置 UTC+8 时区
        self.timezone_utc8 = timezone(timedelta(hours=8))
        # MongoDB 设置
        self.client = MongoClient(mongodb_uri)
        self.db = self.client[database_name]
        self.news_collection = self.db['news']
        
        # 创建索引确保 URL 唯一性
        self.news_collection.create_index("url", unique=True)
        
        # 创建 TTL 索引，设置一周后过期
        self.news_collection.create_index(
            "created_at", 
            expireAfterSeconds=7 * 24 * 60 * 60  # 7天的秒数
        )
        
        self.api_key = api_key
        self.provider = provider
        self.detail_instruction = detail_instruction
        self.detail_page_extractor = DetailPageContentExtractor(self.api_key, self.provider, self.detail_instruction)
        
        # Configure logging
        self._setup_logging(log_file)
        
        # Logging initialization
        self.logger.info(f"ListPageExtractor initialized with detail_instruction: {self.detail_instruction}")
    
        
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
    
    def _get_current_time_utc8(self):
        """获取 UTC+8 时间"""
        return datetime.now(self.timezone_utc8)
    
    def _format_news_document(self, news_data, detail_content=None):
        """将爬取的数据转换为MongoDB文档格式"""
        try:
            published_date = datetime.strptime(
                news_data['post_time'], 
                '%Y-%m-%d'  # 根据实际日期格式调整
            ).replace(tzinfo=self.timezone_utc8)
        except ValueError:
            published_date = self._get_current_time_utc8()

        document = {
            "title": news_data['title'],
            "url": news_data['further_url'],
            "published_date": published_date,
            "created_at": self._get_current_time_utc8(),  # 添加用于 TTL 的字段
            "tags": [news_data['tag']] if news_data['tag'] else [],
            "language": "en",
            "content": None,  # 将在详情页提取时更新
            "keywords": None # 将在详情页提取时更新
        }
        
        # 详情页提取时，添加summary && keywords
        if detail_content:
            key_words = detail_content[0].get('key_words', '')
            
            # If key_words is a string, split by commas. If it's a list, use it as-is.
            if isinstance(key_words, str):
                keywords = key_words.split(',') if key_words else []
            elif isinstance(key_words, list):
                keywords = key_words
            else:
                keywords = []

            # Update the MongoDB document
            document.update({
                "content": detail_content[0].get('summary'),
                "keywords": keywords  # This will store as a list in MongoDB
            })
        
        return document

    async def extract_news_list(self):
        urls = [

        ]
        
        all_processed_news = []
        async with AsyncWebCrawler() as crawler:
            for url in urls:
                try:
                    result = await crawler.arun(
                        url=url,
                        extraction_strategy=LLMExtractionStrategy(
                            provider=self.provider,
                            api_token=self.api_key,
                            schema=TechFinancingNews.schema(),
                            extraction_type="schema",
                            instruction="""
                            You are an HTML parsing expert. Your task is to:
                            
                            1. Parse a list page containing high-tech and startup company news
                            2. Extract only items related to AI, Venture, Startups, Technology or similar topics
                            3. Extract the following elements for each news item:
                            - Title
                            - Tag
                            - Further URL (link to detailed page)
                            - Publication date
                            4. Format the results in JSON
                            5. Leave 'summary' and 'key_words' fields as None
                            6. Only extract the first 10 news items
                            
                            Expected output format:
                            {
                                "title": "...",
                                "tag": "...",
                                "further_url": "...",
                                "post_time": "...",
                                "summary": null,
                                "key_words": null
                            }
                            """
                        ),
                        bypass_cache=True
                    )

                    # Check if result and extracted_content exist
                    if not result or not result.extracted_content:
                        print(f"No content extracted for {url}")
                        continue
                    
                    try:
                        news_data = json.loads(result.extracted_content)
                        # Debug by printing the first news if exists
                        if news_data:
                            print(news_data[0])
                    except (TypeError, json.JSONDecodeError) as e:
                        print(f"Error parsing content for {url}: {e}")
                        continue

                    # 存储到 MongoDB
                    for news in news_data:
                        all_processed_news.append(news)
                        # 检查URL是否已存在
                        existing_doc = self.news_collection.find_one({'url': news['further_url']})
                        if existing_doc:
                            print(f"Skipping existing news: {news['further_url']}")
                            continue

                        document = self._format_news_document(news)
                        try:
                            self.news_collection.update_one(
                                {'url': document['url']},
                                {'$set': document},
                                upsert=True
                            )
                            
                        except Exception as e:
                            print(f"Error saving news: {e}")
                            
                except Exception as e:
                    print(f"Error processing URL {url}: {e}")
        return all_processed_news

    def extract_detailPage(self, news_data):
        for news_block in news_data:
            detail_page_url = news_block.get("further_url")
            if not detail_page_url:
                continue
            
            # 检查文档是否存在且是否需要更新
            existing_doc = self.news_collection.find_one({'url': detail_page_url})
            if existing_doc and existing_doc.get('keywords') and existing_doc.get('content'):
                print(f"Skipping detail page with complete content: {detail_page_url}")
                continue

            while True:
                try:
                    detail_page_result = asyncio.run(
                        self.detail_page_extractor.extract_detail_content(detail_page_url)
                    )
                    break
                except litellm.RateLimitError:
                    print("Rate limit error. Waiting for 30 seconds...")
                    time.sleep(30)
                
            if detail_page_result is not None:
                print("Extracted detail content:")
                print(detail_page_result)
                
                # 更新 MongoDB 文档
                document = self._format_news_document(news_block, detail_page_result)
                self.logger.info(f"Already _format_news_document and ready to insert into mongo.")
                
                try:
                    self.news_collection.update_one(
                        {'url': detail_page_url},
                        {
                            '$set': {
                                'content': document['content'],
                                'keywords': document['keywords'],
                                'last_updated': datetime.now(timezone.utc)
                            }
                        }
                    )
                    
                    self.logger.info(f"Successfully inserted detailed contents into mongo!")
                    print(f"Successfully inserted detailed contents")
                except Exception as e:
                    print(f"Error updating news detail: {e}")

if __name__ == "__main__":
    detail_instruction = """ From the crawled content, Extract the following information:
        title: the title of the news article
        summary: a about-100-word summary of the news content
        key_words: top 3 relevant words separated by commas
        Output the extracted information in a single JSON object with the following format:
        [{ title: "", summary: "", key_words: ""}]"
    """

    extractor = TechFinancingNewsExtractor(
        mongodb_uri="mongodb://localhost:27017/",
        database_name="InfoFlow",
        api_key=os.getenv('GEMINI_API_KEY'),
        detail_instruction=detail_instruction
    )
    news_data = asyncio.run(extractor.extract_news_list())
    extractor.extract_detailPage(news_data)