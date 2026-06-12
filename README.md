# PDF RAG Chatbot

This is a beginner-friendly RAG chatbot project built with Python.

The app reads a PDF file, splits the document into chunks, stores those chunks in ChromaDB, retrieves the most relevant chunks based on the user’s question, and sends the retrieved context to Gemini to generate a final answer.

## Tech Stack

* Python
* PyPDF
* ChromaDB
* Google Gemini API
* RAG: Retrieval-Augmented Generation

## How It Works

1. Read PDF using PyPDF
2. Split PDF text into chunks
3. Store chunks in ChromaDB
4. Ask a question about the PDF
5. Retrieve relevant chunks
6. Send question + context to Gemini
7. Print final answer

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Set your Gemini API key as an environment variable:

```bash
setx GEMINI_API_KEY "your_api_key_here"
```

Run the app:

```bash
python read_pdf.py
```

Type `exit` to stop the chatbot.

## Example Questions

* What is this document about?
* Who are the participants in this study?
* What methods were used in this research?
* What are the main findings?
* What are the limitations of this study?

## Project Status

Basic PDF RAG chatbot completed. Future improvements can include Streamlit UI, file upload support, better chunking, source citations, and deployment.
