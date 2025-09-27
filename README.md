# RAG Arabic PDF Chatbot

This project is a Retrieval-Augmented Generation (RAG) system designed to interact intelligently with Arabic PDF documents stored in AWS S3. It supports both scanned and digital PDFs and uses GPT-4o for OCR and language understanding, as well as a GPT-4.1-mini model for generating answers.

## System Overview

The process requires that a PDF file has already been uploaded to an AWS S3 bucket. Interaction with the document begins when the file path from the S3 bucket is provided to the RAG system. At that point, the system checks whether a local copy of the file already exists. If no local copy is found, the file is downloaded from the S3 bucket using the boto3 library and stored locally so that processing can continue efficiently.

## PDF Ingestion and OCR

Once the file is available, each page of the PDF is converted into an image and encoded in base64. These encoded images are then processed by GPT-4o, which performs OCR and produces clean markdown text. In addition to plain text, structural and visual details such as images, charts, and logos are described.

## Knowledge Base Construction

After all pages are processed, the extracted content is combined into a single markdown file as our knowledge base, divided into smaller chunks, and stored in ChromaDB. The paraphrase-multilingual-MiniLM-L12-v2 model from Hugging Face is used for generating Arabic text embeddings. This multilingual model provides high-quality semantic representations and supports Arabic exceptionally well. Each chunk is associated with metadata that links it back to the original S3 file path, ensuring that searches remain scoped to the correct document.

## Chat Interaction and Question Handling

When a request is sent, the question, file path, last k messages as history (user message and system message), and an evolving chat summary are passed from a backend service, which is responsible for retrieving this data from persistent storage and supplying it to the RAG pipeline. Before the question is submitted to the LLM, a refinement step is applied. Ambiguities are resolved by replacing pronouns with explicit references, and relevant details from the chat summary are added. The summary itself is continuously updated as the conversation progresses, maintaining awareness of important context by the user's provided information.

## Prompt Management and Safety

All prompts used in this pipeline are stored as separate files rather than being hardcoded. This ensures consistency and easier maintenance. The prompts are also written defensively to mitigate indirect prompt injection, explicitly instructing the model to ignore any instructions coming from document content or user text that attempt to alter system behavior.

## Running the Service

To launch the application, execute the following command:

```bash
docker compose up -d
```

Once the service is running, you can send a POST request to the following endpoint:

```
http://localhost:8000/generate-answer
```

### Request Schema

```json
{
  "question": "ما هي مدة سريان أو إنهاؤها؟",
  "fileUrl": "test/markaz_somum.pdf",
  "chatSummary": {
    "documentType": "عقد",
    "topic": "مدة سريان وتجديد وإنهاء الاتفاقية"
  },
  "history": [
    {
      "an": "يجب على الط ئج الإيجابية.",
      "qu": "ما هو التابية للفحوصات لعقلية؟"
    },
    ...
  ]
}
```

### Example Response

```json
{
  "answer": "ي مسبق بمهلة لا تتجاوز ثلاثين يوماً وجميع ذلك يدخل التنفيذ بناءً على خطاب رسمي يقدمه الطرف الراغب في الفسخ أو عدم التجديد.",
  "inputToken": 3120,
  "outputToken": 244,
  "totalToken": 3364,
  "chatSummary": {
    "documentType": "عقد",
    "topic": "مدة سريان وتجديد وإنهاء الاتفاقية"
  }
}
```

The token counts (`inputToken`, `outputToken`, and `totalToken`) are provided to facilitate cost computation.


# Dockerfile Overview

Dockerfile of the project defines a two‑stage build for the Arabic PDF chatbot application. It is structured to produce a slim, secure, and efficient container image.

## Structure

The build consists of two stages:

### Stage 1: `builder`

The first stage uses the `python:3.11-slim` base image to create a Python virtual environment and install all dependencies specified in `src/requirements.txt`. This stage is used only for building the environment and does not end up in the final image. Using a dedicated build stage keeps the final image smaller and cleaner.

Key points in this stage:
- Environment variables are set to disable Python bytecode creation and pip cache.
- A working directory `/opt/app` is defined.
- `requirements.txt` is copied into the container.
- A virtual environment is created in `/opt/venv` and dependencies are installed into it.

### Stage 2: `rag_server`

The second stage also uses `python:3.11-slim` as its base. It serves as the runtime environment for the application.

Key steps in this stage:
- Environment variables configure Python and add the virtual environment to the `PATH`.
- The working directory is set to `/app`.
- `poppler-utils` is installed to provide tools such as `pdftoppm` and `pdftocairo` for PDF processing.
- A non‑root user `appuser` is created to enhance security.
- The pre‑built virtual environment from the `builder` stage is copied into `/opt/venv` and the application source code is copied into `/app/src`, both owned by `appuser`.
- An entrypoint script `entrypoint.sh` is copied to `/app/entrypoint.sh` and marked as executable.
- The working directory is switched to `/app/src` where the application code resides.
- The container entrypoint is set to run `/app/entrypoint.sh` when the container starts.

## How It Works

When the container is built, the first stage (`builder`) installs Python dependencies into a virtual environment. The second stage (`rag_server`) copies only the built virtual environment and source code into a fresh, minimal image. This pattern reduces image size, improves security, and speeds up deployment.

At runtime, the container runs as the non‑root `appuser` in the `/app/src` directory and executes the `entrypoint.sh` script to start the application.
