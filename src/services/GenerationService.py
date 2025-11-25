import json
import os
from pathlib import Path
import boto3
import base64
from dotenv import load_dotenv
from fastapi import HTTPException
from openai import OpenAI
from datetime import datetime
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain_community.vectorstores import Chroma
from pdf2image import convert_from_path
from langchain_community.embeddings import SentenceTransformerEmbeddings

class GenerationService:
    def __init__(self):
        self.extract_prompt = self.load_prompt_template("public/prompts/extract/extract_prompt.md")
        self.gen_user_prompt = self.load_prompt_template("public/prompts/generation/user_prompt.md")
        self.gen_system_prompt = self.load_prompt_template("public/prompts/generation/system_prompt.md")
        self.refine_user_prompt = self.load_prompt_template("public/prompts/refinement/user_prompt.md")
        self.refine_system_prompt = self.load_prompt_template("public/prompts/refinement/system_prompt.md")
        load_dotenv()
        
    def load_prompt_template(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            print(f"Error: {filename} not found.")
            return ""
        
        
    def generate_answer(self, question, fileUrl, history, chatSummary):
        ext_input_token = ext_output_token = ext_total_token = 0
        download_directory = "public/downloads/"
        filepath = os.path.join(download_directory, fileUrl)
        
        if os.path.isfile(filepath):
            print("File exists.")
        else:
            print("File does not exist.")
            self.download_s3_file(fileUrl)            
            ext_input_token, ext_output_token, ext_total_token, ext_text = self.extract_md_from_file(fileUrl)
            self.append_to_chroma(fileUrl)
            
        
        refine_input_token, refine_output_token, refine_total_token, refined=self.refine_query(question, history, chatSummary)
        try:
            refined = json.loads(refined)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
        
        gen_input_token, gen_output_token, gen_total_token, answer = self.generate_from_llm(refined.get("refinedQuery"), fileUrl, history, chatSummary)
        
        return gen_input_token + ext_input_token + refine_input_token, gen_output_token + ext_output_token + refine_output_token, gen_total_token + ext_total_token + refine_total_token, answer, refined.get("chatSummary")
   
   
   
    def refine_query(self, question, history, chatSummary):
        print("---------------->>>>>>> time:", datetime.now())
        print('Start refiing the question')
        
        gen_model = os.getenv("GEN_MODEL")
        openai_api_key = os.getenv("CHATBOT_API_KEY")
        base_url = os.getenv("BASE_URL")
        
        client = OpenAI(api_key=openai_api_key, base_url=base_url)

        user_prompt= self.refine_user_prompt.format(
            question=question,
            chatSummary=chatSummary,
            history=history
        )

        response = client.chat.completions.create(
            model= gen_model,
            response_format={ "type": "json_object" },
            messages=[
                { "role": "system", "content": self.refine_system_prompt },
                { "role": "user", "content": user_prompt },
            ],
            max_tokens=2000
        )
        
        print("---------------->>>>>>> time:", datetime.now())
        print('End of generating from LLM')

        return response.usage.prompt_tokens, response.usage.completion_tokens, response.usage.total_tokens, response.choices[0].message.content
    
    def generate_from_llm(self, question, fileUrl, history, chatSummary):
        print("---------------->>>>>>> time:", datetime.now())
        print('Start generating from LLM')
        
        ocr_model = os.getenv("OCR_MODEL")
        gen_model = os.getenv("GEN_MODEL")
        openai_api_key = os.getenv("CHATBOT_API_KEY")
        base_url = os.getenv("BASE_URL")
        
        retrieved_documents = self.retrieve_relevent_documents(question, fileUrl)
        
        client = OpenAI(api_key=openai_api_key, base_url=base_url)

        user_prompt= self.gen_user_prompt.format(
            question=question,
            retrieved_documents="\n".join(doc.page_content for doc in retrieved_documents) if retrieved_documents else "No relevant documents found.",
            history=history,
            chat_summary=chatSummary
        )

        response = client.chat.completions.create(
            model= gen_model,
            messages=[
                { "role": "system", "content": self.gen_system_prompt },
                { "role": "user", "content": user_prompt },
            ],
            max_tokens=2000
        )
        
        print("---------------->>>>>>> time:", datetime.now())
        print('End of generating from LLM')

        return response.usage.prompt_tokens, response.usage.completion_tokens, response.usage.total_tokens, response.choices[0].message.content
    
    def retrieve_relevent_documents(self, question, fileUrl):
        persis_dir = os.getenv("PERSIST_DIR")
        embedding_model = os.getenv("EMBEDDING_MODEL")
        embedding_function = SentenceTransformerEmbeddings(model_name=embedding_model)
        
        vectordb = Chroma(persist_directory=persis_dir,embedding_function=embedding_function)
    
        image_retriever = vectordb.as_retriever(
            search_kwargs={
                "k": 10,
                "filter": {
                    "fileUrl": {"$eq": fileUrl}
                }
            }
        )
        retrieved_docs = image_retriever.invoke(question)

        return retrieved_docs
    
    def append_to_chroma(self, fileUrl: str):
        print("---------------->>>>>>> time:", datetime.now())
        print('Start appending to chroma')
        
        persis_dir = os.getenv("PERSIST_DIR")
        embedding_model = os.getenv("EMBEDDING_MODEL")
        
        with open("public/knowledgeBase/" + fileUrl.split(".")[0] + ".md", "r", encoding="utf-8") as f:
            text = f.read()
        
        doc = Document(
            page_content=text,
            metadata={
                "fileUrl": fileUrl
            }
        )
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = splitter.split_documents([doc])
        embedding_fn = SentenceTransformerEmbeddings(model_name=embedding_model)
        db = Chroma(persist_directory=persis_dir, embedding_function=embedding_fn)
        db.add_documents(chunks)

        print("---------------->>>>>>> time:", datetime.now())
        print('End of appending to chroma')
   
    def _encode_image_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
   
    def download_s3_file(self, s3_path: str):
        print("---------------->>>>>>> time:", datetime.now())
        print('Start downloading file')
    
        AWS_KEY = os.getenv("AWS_KEY")
        AWS_SECRET = os.getenv("AWS_SECRET")
        AWS_REGION = os.getenv("AWS_REGION")
        AWS_BUCKET = os.getenv("AWS_BUCKET")

        # Construct local path
        local_path = Path("public/downloads") / s3_path
        local_path.parent.mkdir(parents=True, exist_ok=True)  # Create local folders

        # Create S3 client
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_KEY,
            aws_secret_access_key=AWS_SECRET,
            region_name=AWS_REGION,
        )

        try:
            s3.download_file(AWS_BUCKET, s3_path, str(local_path))
            print(f"✅ Downloaded {s3_path} to {local_path}")
        except Exception as e:
            print(f"❌ Failed to download {s3_path}: {e}")
        
        print("---------------->>>>>>> time:", datetime.now())
        print('End of downloading file')
        
    def extract_md_from_file(self, filePath: str):
        print("---------------->>>>>>> time:", datetime.now())
        print('Start extracting .md texts from multi-page PDF')

        # Load env vars
        ocr_model = os.getenv("OCR_MODEL")
        openai_api_key = os.getenv("CHATBOT_API_KEY")
        base_url = os.getenv("BASE_URL")
        input_token=0
        output_token=0
        total_token=0

        # Init client
        client = OpenAI(api_key=openai_api_key, base_url=base_url)

        # Convert all PDF pages to images
        pdf_path = "public/downloads/" + filePath
        pages = convert_from_path(pdf_path, dpi=300)

        markdown_result = ""

        for i, page in enumerate(pages):
            image_path = "public/downloads/" + filePath + f"_{i+1}.jpg"
            page.save(image_path, "JPEG")

            # Encode image
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")

            print(f"Processing page {i+1}/{len(pages)}")

            try:
                response = client.chat.completions.create(
                    model=ocr_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                { "type": "text", "text": self.extract_prompt },
                                { "type": "image_url", "image_url": { "url": f"data:image/jpeg;base64,{image_b64}" } }
                            ]
                        }
                    ],
                    max_tokens=3000
                )

                page_text = response.choices[0].message.content.strip()
                markdown_result += f"\n\n---\n\n##Page {i+1}\n\n{page_text}"
                input_token = input_token + response.usage.prompt_tokens
                output_token = output_token + response.usage.completion_tokens
                total_token = total_token + response.usage.total_tokens

            except Exception as e:
                print(f"Error processing page {i+1}: {e}")
                markdown_result += f"\n\n---\n\n##Page {i+1}\n\n*Failed to process this page.*"

            # Optional cleanup: os.remove(image_path)

        # Save to .md file
        output_md_path = "public/knowledgeBase/" + filePath.replace(".pdf", ".md")
        os.makedirs(os.path.dirname(output_md_path), exist_ok=True)

        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write(markdown_result)

        print("---------------->>>>>>> time:", datetime.now())
        print('End of extracting .md texts from multi-page PDF')

        return input_token, output_token, total_token, markdown_result