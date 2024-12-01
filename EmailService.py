import json
import os
import glob
import logging
from datetime import datetime
from openai import OpenAI
from zhipuai import ZhipuAI
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from pymongo import MongoClient
import time

class NewsEmailService:
    def __init__(self, mongodb_uri="mongodb://localhost:27017/", 
                 database_name="InfoFlow",
                 recipients=None):
        """初始化服务"""
        self.mongodb_uri = mongodb_uri
        self.database_name = database_name
        self.recipients = recipients or []
        self.setup_logging()
        self.api_key, self.folder_name = self.initialize_environment()
        self.client = ZhipuAI(api_key=self.api_key)

    def setup_logging(self):
        """设置日志配置"""
        logging.basicConfig(
            filename='logs/workflow.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def initialize_environment(self):
        """初始化环境变量"""
        logging.info("初始化环境")
        api_key = os.environ.get('zhipuai_api_key')
        if not api_key:
            logging.error("未找到API密钥")
            raise ValueError("API密钥未找到")
        
        folder_name = 'layout_output'
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            logging.info(f"创建输出文件夹: {folder_name}")
        
        return api_key, folder_name

    def process_and_send_news(self, recipients=None):
        """处理并发送新闻的主要方法"""
        try:
            recipients = recipients or self.recipients
            if not recipients:
                logging.warning("未配置收件人")
                return False

            # 获取并处理新闻
            news_data = self.get_latest_news_from_mongodb()
            translated_data = self.translate2ZH(news_data)
            email_html = self.generate_email_html(translated_data)

            # 发送邮件
            success_count, failed_recipients = self.send_email(email_html, recipients)
            
            # if failed_recipients:
            #     logging.warning(f"发送失败的收件人: {failed_recipients}")
            #     return False
            return True

        except Exception as e:
            logging.error(f"处理失败: {str(e)}")
            raise

    def get_latest_news_from_mongodb(self):
        """从MongoDB获取最新的10条新闻"""
        logging.info("Fetching latest news from MongoDB")
        client = MongoClient(self.mongodb_uri)
        db = client[self.database_name]
        collection = db['news']
        
        # 获取最新的10条有完整内容的新闻
        latest_news = list(collection.find(
            {
                'content': {'$ne': None},
                'keywords': {'$ne': []}
            },
            {
                '_id': 0,
                'title': 1,
                'content': 1,
                'keywords': 1,
                'published_date': 1,
                'url': 1
            }
        ).sort('published_date', -1).limit(10))
        
        # 转换为所需的格式
        formatted_news = []
        for news in latest_news:
            formatted_news.append({
                'title': news['title'],
                'summary': news['content'],
                'key_words': news['keywords'],
                'url': news['url']
            })
        
        return formatted_news

    def translate2ZH(self, data):
        """Translate content using AI"""
        logging.info("Starting translation")
        #TODO 不整10个放进LLM，而是一个一个放进去，顺便做一个 language = “en” 才做翻译的过滤
        # 将数据转换为JSON字符串
        json_str = json.dumps(data, ensure_ascii=False)
        
        content = (
            "你是一个英文翻译成中文的专家，请将以下JSON格式的内容翻成中文。要求：\n"
            "1. 如果原文就是中文，则保持内容不变\n"
            "2. 只翻译内容，不要修改JSON结构，保持JSON格式不变\n"
            "3. 确保输出是有效的JSON格式\n"
            "4. 中文要听起来自然流利\n"
            "5. 直接返回翻译后的JSON，不要添加任何额外的解释文字\n\n"
            "需要翻译的内容：\n"
        ) + json_str
        
        messages = [{"role": "user", "content": content}]
        try:
            response = self.client.chat.completions.create(
                model="glm-4-flash",
                messages=messages
            )
            translated_content = response.choices[0].message.content
            
            # 清理并验证JSON
            try:
                # 提取JSON部分
                start = translated_content.find('[')
                end = translated_content.rfind(']') + 1
                if start >= 0 and end > 0:
                    clean_json = translated_content[start:end]
                    return json.loads(clean_json)
                else:
                    raise ValueError("No JSON array found in response")
                
            except json.JSONDecodeError as e:
                logging.error(f"JSON validation failed: {e}")
                raise
                
        except Exception as e:
            logging.error(f"Translation failed: {str(e)}")
            raise

    def send_single_email(self, sender_email, sender_password, recipient, html_content, retry_count=1, retry_delay=5):
        """向单个收件人发送邮件，包含重试机制"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = Header(f'Tech News Daily Update - {datetime.now().strftime("%Y-%m-%d")}', 'utf-8')
        msg['From'] = sender_email
        msg['To'] = recipient
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        for attempt in range(retry_count):
            try:
                with smtplib.SMTP_SSL("smtp.163.com", 465) as server:
                    server.login(sender_email, sender_password)
                    server.send_message(msg)
                    logging.info(f"Email sent successfully to {recipient}")
                    return True
            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed for {recipient}: {str(e)}")
                if attempt < retry_count - 1:
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Failed to send email to {recipient} after {retry_count} attempts")
                    return False

    def send_email(self, html_content, recipients):
        """发送HTML格式的邮件给收件人列表"""
        logging.info("Preparing to send emails")
        
        # 从环境变量获取邮件配置
        sender_email = os.environ.get('EMAIL_USER_WY')
        sender_password = os.environ.get('EMAIL_PASSWORD_WY')
        
        if not all([sender_email, sender_password]):
            raise ValueError("Missing email configuration in environment variables")
        
        # 记录发送结果
        success_count = 0
        failed_recipients = []
        
        # 逐个发送邮件
        for recipient in recipients:
            try:
                # 每个收件人之间添加短暂延迟，避免发送过快
                time.sleep(2)
                
                if self.send_single_email(sender_email, sender_password, recipient, html_content):
                    success_count += 1
                else:
                    failed_recipients.append(recipient)
                    
            except Exception as e:
                logging.error(f"Unexpected error when sending to {recipient}: {str(e)}")
                failed_recipients.append(recipient)
        
        # 记录发送结果
        logging.info(f"Email sending completed: {success_count} successful, {len(failed_recipients)} failed")
        if failed_recipients:
            logging.warning(f"Failed recipients: {', '.join(failed_recipients)}")
        
        # 如果所有邮件都发送失败，抛出异常
        if success_count == 0:
            raise Exception("All email sending attempts failed")
        
        return success_count, failed_recipients

    def generate_email_html(self, data):
        """生成用于邮件的HTML内容，优化布局突出要闻速览"""
        email_template = '''<!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <title>Tech News Daily Update</title>
        </head>
        <body style="font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f6fa;">
            <div style="background: linear-gradient(135deg, #74b9ff, #0984e3); color: white; padding: 20px; border-radius: 15px 15px 0 0; margin-bottom: 0;">
                <h1 style="text-align: center; margin: 0; font-size: 1.8em;">📰 今日科技要闻</h1>
                <div style="text-align: right; font-size: 0.9em; margin-top: 10px; opacity: 0.9;">{date}</div>
            </div>
            
            <div style="background-color: white; padding: 25px; border-radius: 0 0 15px 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px;">
                {news_list}
            </div>
            
            <div style="text-align: center; margin: 40px 0;">
                <div style="color: #2c3e50; font-weight: bold; margin-bottom: 10px;">详细内容</div>
                <div style="height: 2px; background: linear-gradient(to right, transparent, #3498db, transparent);"></div>
            </div>
            
            <div style="background-color: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                {detailed_content}
            </div>
            
            <div style="text-align: center; margin-top: 30px; color: #666; font-size: 12px;">
                <p>此邮件由自动系统发送，请勿直接回复</p>
            </div>
        </body>
        </html>'''
        
        # 生成新闻标题列表
        news_items = []
        for i, article in enumerate(data, 1):
            news_item = f'''<div style="background-color: #fff; padding: 12px 15px; margin-bottom: 15px; border-radius: 8px; display: flex; align-items: baseline;">
                <span style="flex: 0 0 40px; font-weight: bold; color: #0984e3;">#{i:02d}</span>
                <span style="flex: 1;">
                    <a href="#{i}" style="color: #2c3e50; text-decoration: none;">{article['title']}</a>
                    <div style="margin-top: 4px; color: #7f8c8d; font-size: 0.85em;">{', '.join(article['key_words'][:3])}</div>
                </span>
            </div>'''
            news_items.append(news_item)
        
        # 生成详细新闻内容
        detailed_articles = []
        for i, article in enumerate(data, 1):
            article_html = f'''<div id="{i}" style="margin-bottom: 30px; background-color: #fff; padding: 20px; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <h3 style="color: #2c3e50; font-size: 1.2em; margin: 0 0 15px 0; padding-bottom: 10px; border-bottom: 1px solid #eee;">
                    📰 {article['title']}
                </h3>
                <div style="color: #34495e; margin: 15px 0; line-height: 1.6;">
                    📝 {article['summary']}
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 15px; font-size: 0.9em;">
                    <div style="color: #7f8c8d;">
                        🏷️ {', '.join(article['key_words'])}
                    </div>
                    <a href="{article['url']}" style="color: #0984e3; text-decoration: none; font-weight: 500;" target="_blank">
                        阅读原文 →
                    </a>
                </div>
            </div>'''
            detailed_articles.append(article_html)
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 使用字典进行格式化，确保所有占位符都有对应的值
        return email_template.format(
            date=current_time,
            news_list='\n'.join(news_items),
            detailed_content='\n'.join(detailed_articles)
        )

def main():
    """示例使用方法"""
    recipients = [

    ]

    service = NewsEmailService(recipients=recipients)
    service.process_and_send_news()

if __name__ == "__main__":
    main()