# InfoFlow4ai

---

## Installation

### Prerequisites

Make sure you have the following installed:

- Python 3.8 or later
- MongoDB (running locally or remotely)

### Python Dependencies

Install the required Python packages using `pip`:

```bash
pip install pymongo crawl4ai
```

---

## Configuration

### 1. API Key Setup

Set the API key for your AI model (e.g., OpenAI API) as an environment variable in your operating system:

```bash
export API_KEY="your_llm_api_key_here"
```

### 2. Parameter Configuration

#### Websites to Crawl

Specify the websites to crawl by editing the `urls` parameter in `ListPageExtractor.py`:

```python
async def extract_news_list(self): 
    urls = [
        # Add website URLs here
    ]
```

#### Email Recipients

Add the recipient email addresses in the `recipients` parameter in `EmailService.py`:

```python
recipients = [
    # Add email addresses here
]
```

---

## Usage

### 1. Start the Service

Use the `scheduler.py` script to manage the service:

- **Start the Scheduler**:

    ```bash
    python scheduler.py start
    ```

- **Stop the Scheduler**:

    ```bash
    python scheduler.py stop
    ```

### 2. Set Execution Times

- **Set Crawler Execution Time** (multiple times can be specified):

    ```bash
    python scheduler.py set_crawler_time 08:00 09:30
    ```

- **Set Email Sending Time** (multiple times can be specified):

    ```bash
    python scheduler.py set_email_time 16:00 17:30
    ```


---

## Contributing

Contributions are welcome! Feel free to fork this repository and submit a pull request.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

Let me know if you need additional sections like examples or FAQs!

