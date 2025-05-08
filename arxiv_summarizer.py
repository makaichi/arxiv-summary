import datetime
import json
import logging
import os
import sys

import arxiv
import openai
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


class ArxivSummarizer:
    """
    A class to automatically summarize arXiv papers using LLMs.
    """

    def __init__(self):
        """
        Initializes the ArxivSummarizer class.
        Loads environment variables, sets up logging, and initializes the OpenAI client.
        """
        self._setup_logging()  # Initialize logging
        self._load_environment_variables()
        self.client = openai.OpenAI(api_key=self.openai_api_key, base_url=self.openai_base_url)

    def _setup_logging(self):
        """Configures logging."""
        logging.basicConfig(
            level=logging.ERROR,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],  # Output to console
        )

    def _load_environment_variables(self):
        """Loads environment variables from .env file."""
        load_dotenv()  # Load .env if it exists

        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL")
        self.openai_model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")  # Default model
        self.summary_language = os.getenv("SUMMARY_LANGUAGE", "English")  # Default language
        self.webhook_url = os.getenv("WEBHOOK_URL")

        if not self.openai_api_key:
            logging.error("OPENAI_API_KEY not found in environment variables.")
            raise ValueError("OPENAI_API_KEY is required.")

    def _handle_exception(self, e, message="An error occurred:"):
        """Logs and potentially re-raises an exception."""
        logging.exception(f"{message} {e}")
        raise  # Re-raise to stop execution (or handle differently if needed)

    def get_paper_links_from_arxiv_page(self, url: str) -> list[str]:
        """
        Fetches all paper links (starting with /abs/) from an arXiv page.
        """
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            soup = BeautifulSoup(response.content, "html.parser")
            links = [
                a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith("/abs/")
            ]
            return links
        except requests.exceptions.RequestException as e:
            raise  # Re-raise the exception to be handled upstream
        except Exception as e:
            raise self._handle_exception(e, "Error parsing arXiv page:")

    def get_paper_metadata(self, paper_id: str) -> dict:
        """
        Retrieves paper metadata (title, abstract) from arXiv using the arxiv library.
        """
        try:
            client = arxiv.Client()
            search = arxiv.Search(id_list=[paper_id])
            results = client.results(search)
            paper = next(results)  # Get the first result
            authors = [author.name for author in paper.authors]
            if len(authors) > 3:
                authors = authors[:2] + ["et al."]
            return {
                "title": paper.title,
                "authors": ", ".join(authors),
                "abstract": paper.summary,
                "url": paper.entry_id.replace("http://", "https://"),
            }

        except Exception as e:
            raise self._handle_exception(e, f"Error fetching metadata for paper ID {paper_id}:")

    def summarize_paper(self, title: str, abstract: str) -> str:
        """
        Summarizes the paper using the OpenAI API.
        """
        try:
            prompt = f"""Summarize the following research paper. Provide the most important information in up to 3 sentences. Respond in {self.summary_language}.

            Title: {title}
            Abstract: {abstract}
            """

            completion = self.client.chat.completions.create(
                model=self.openai_model_name, messages=[{"role": "user", "content": prompt}]
            )
            summary = completion.choices[0].message.content.strip()

            prompt = f"Translate the following title of article to {self.summary_language}, only respond with the translated title: {title}"
            completion = self.client.chat.completions.create(
                model=self.openai_model_name, messages=[{"role": "user", "content": prompt}]
            )
            translated_title = completion.choices[0].message.content.strip()

            return translated_title, summary

        except openai.APIConnectionError as e:
            logging.error(f"Failed to connect to OpenAI API: {e}")
            raise
        except openai.RateLimitError as e:
            logging.error(f"OpenAI API rate limit exceeded: {e}")
            raise
        except Exception as e:
            raise self._handle_exception(e, "Error during summarization:")

    def process_arxiv_url(self, category: str):
        """
        Main function to orchestrate the process.
        """
        arxiv_url = f"https://arxiv.org/list/{category}/new"
        papers = []
        try:
            paper_links = self.get_paper_links_from_arxiv_page(arxiv_url)

            for link in paper_links:
                paper_id = link.split("/")[-1]
                logging.info(f"Processing paper ID: {paper_id}")
                try:
                    metadata = self.get_paper_metadata(paper_id)
                    title = metadata["title"]
                    abstract = metadata["abstract"]
                    translated_title, summary = self.summarize_paper(title, abstract)
                    metadata["summary"] = summary
                    metadata["translated_title"] = translated_title
                    papers.append(metadata)
                except Exception as e:
                    logging.error(f"Failed to process paper ID {paper_id}.  See logs for details.")
            if not papers:
                raise ValueError("No papers were processed.")
            return papers

        except Exception as e:
            logging.error(f"An unhandled error occurred: {e}")
            return None

    def send_arxiv_data_via_webhook(self, data_list: list, category: str):
        """
        Sends Arxiv paper data in a single message to a webhook.

        Args:
            data_list: A list of dictionaries, where each dictionary represents an Arxiv paper
                    and contains keys like 'title', 'url', 'authors', 'abstract', 'summary'.
            webhook_url: The URL of the webhook.
            message_type: The type of message to send.  Defaults to "text".  Can be other types
                        supported by the webhook (e.g., "card" if your webhook supports rich cards).
                        You might need to adapt the content construction depending on the message type.

        Returns:
            The response object from the webhook for a successful send, or None if there's an error.
        """

        try:
            # Construct the message content by concatenating information from all papers.
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            message_text = f"{today} Arxiv papers summary for {category}:\n\n"
            for paper_data in data_list:
                message_text += f"Title: {paper_data['title']}\n"
                message_text += f"{paper_data['translated_title']}\n"
                message_text += f"Authors: {paper_data['authors']}\n"
                message_text += f"URL: {paper_data['url']}\n"
                message_text += f"Summary: {paper_data['summary']}\n\n"  # Limit summary length
            # Remove the trailing newline characters
            message_text = message_text.rstrip("\n")

            # Construct the message payload.
            content = {"text": message_text}

            payload = {"msg_type": "text", "content": content}

            # Convert the payload to JSON.
            json_payload = json.dumps(payload)

            # Send the request to the webhook.
            headers = {"Content-Type": "application/json"}
            response = requests.post(self.webhook_url, data=json_payload, headers=headers)

            # Check the response status code.
            if response.status_code == 200:
                logging.info("Successfully sent data for all papers.")
                return response
            else:
                logging.error(
                    f"Error sending data. Status code: {response.status_code}. Response text: {response.text}"
                )
                return None

        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return None

    def run(self, category: str, max_papers_split: int = 10):
        papers = self.process_arxiv_url(category)
        if not papers:
            raise ValueError("Processing failed.")

        if self.webhook_url:
            num_splits = (len(papers) + max_papers_split - 1) // max_papers_split
            split_size = (len(papers) + num_splits - 1) // num_splits
            papers_split = [papers[i : i + split_size] for i in range(0, len(papers), split_size)]
            for i, papers in enumerate(papers_split):
                if len(papers_split) == 1:
                    suffix = ""
                else:
                    suffix = f" ({i+1}/{len(papers_split)})"

                self.send_arxiv_data_via_webhook(papers, category + suffix)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Summarize Arxiv papers.")
    parser.add_argument(
        "category", nargs="?", default="eess.AS", help="Arxiv category (default: eess.AS)"
    )
    parser.add_argument(
        "--max_papers_split",
        type=int,
        default=10,
        help="Maximum number of papers to send in a single webhook request (default: 10)",
    )

    args = parser.parse_args()

    summarizer = ArxivSummarizer()

    summarizer.run(args.category, args.max_papers_split)
