from pypdf import PdfReader
import chromadb
from google import genai
import os

pdf_path = "sample.pdf"

#Reading the PDF
reader = PdfReader(pdf_path)

text = ""

for page in reader.pages:
    page_text = page.extract_text()
    if page_text:
        text += page_text + "\n"
        
#print(text)


#Splitting into chunks
def split_text(text, chunk_size=1200):
    chunks = []
    
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        chunks.append(chunk)
        
    return chunks

chunks = split_text(text)

print("Total chunks: ", len(chunks))

#for i, chunk in enumerate(chunks):
#    print("\n--- Chunk", i + 1, "---")
#    print(chunk)
    

#Store chunks in ChromaDB
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection(name="pdf_chunks")

for i, chunk in enumerate(chunks):
    collection.add(
        documents=[chunk],
        ids=[f"chunk_{i}"]
    )
    
print("Chunks stored in Chromadb")


"""now until here, this code reads the PDF, 
splits it into chunks, stores chunks in ChromaDB. 
Next step is:
user will ask a question, then relevant chunks will be retrieved from ChromaDB.
After that, retrieved chunks + user question has to be sent to AI model.
Then AI model gonna send the final answer.
"""

"""now lets add the LLM answer part such that the code will stop printing only chunks and will start answering for the question."""


#Connect to Gemini
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


#Now asking questions continuously like a real chatbot
while True:
    
    #Asking the questionsss
    question = input("\nAsk a question about PDF: ")

    #If user types exit, the chatbot will stop
    if question.lower() == "exit":
        print("Chatbot stopped. Bye!")
        break

    #Now we retrieve the most relevant chunks from ChromaDB based on user question
    results = collection.query(
        query_texts=[question],
        n_results=6
    )

    #print("\nMost relevant chunks: ")

    #for doc in results["documents"][0]:
    #    print("\n--- Retrieved Chunk ---")
    #    print(doc)


    ##converting the retrieved chunks into one context
    context = "\n\n".join(results["documents"][0])

    #now the final prompt 
    prompt = f"""
You are a PDF question-answering assistant.
Use the context below to answer the question.
Give a clear, detailed answer in simple words. Include numbers, groups, methods, and important details when available in the context.
If the exact answer is not available, use the available context to give the best document-based answer.
Do not use outside knowledge.

Context: 
{context}

Question:
{question}
"""

    #now will send this prompt and question to Gemini AI model
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )

        print("\nFinal Answer:")
        print(response.text)

    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            print("\nGemini quota is over for now. Wait and try again later, or use another model/key.")
        else:
            print("\nError:", e)


"""so now this code is like, 
pdf to chunks to chromadb to retrieve chunks to gemini answers.
Now it works like a real chatbot because we can ask multiple questions continuously.
Type exit to stop the chatbot.
"""