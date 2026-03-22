import os
import shutil
from git import Repo
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
CLONE_DIR = "cloned_repo"
CHROMA_DIR = "chroma_db"
SUPPORTED_EXTENSIONS = {
    ".py", ".js", ".ts", ".java", ".cpp", ".c",
    ".go", ".rs", ".jsx", ".tsx", ".md", ".html", ".css", ".ipynb", ".json", ".yml", ".yaml",".csv",".txt"
}
IGNORED_DIRS = {".git", "node_modules", "__pycache__", "dist", "build", ".venv", "outputs"}
"""
Clones a public GitHub repository to a local directory.
"""
def clone_repo(repo_url):
    print("Cleaning up old data...")
    if os.path.exists(CLONE_DIR):
        shutil.rmtree(CLONE_DIR)
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
    print(f"Cloning repository: {repo_url}")
    Repo.clone_from(repo_url, CLONE_DIR)
    print("Repository cloned successfully!")
def load_files():
    print("Scanning for supported files...")
    documents = []
    file_count = 0
    for root, dirs, files in os.walk(CLONE_DIR):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            if ext in SUPPORTED_EXTENSIONS:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    rel_path = os.path.relpath(file_path, CLONE_DIR)
                    documents.append({
                        "content": content,
                        "metadata": {
                            "source": rel_path,
                            "filename": file, "indexed_at": "today"
                        }
                    })
                    file_count += 1
                except Exception as e:
                    print(f"Skipping {file_path}: {e}")
    print(f"Found {file_count} supported files")
    return documents
def chunk_documents(documents):
    print("Splitting documents into chunks...")
    code_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\nclass ", "\ndef ", "\n\n", "\n", " "]
    )
    notebook_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=100,
        separators=["\n\n", "\n", " "]
    )
    chunks = []
    for doc in documents:
        ext = os.path.splitext(doc["metadata"]["source"])[1]
        splitter = notebook_splitter if ext == ".ipynb" else code_splitter
        splits = splitter.create_documents(
            texts=[doc["content"]],
            metadatas=[doc["metadata"]]
        )
        chunks.extend(splits)
    print(f"Created {len(chunks)} chunks")
    return chunks
def create_embeddings():
    print("Loading embedding model (all-MiniLM-L6-v2)...")
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "mps"}
    )
    print("Embedding model loaded!")
    return embeddings
def store_in_chroma(chunks, embeddings, persist_directory):
    print(f"Storing embeddings in ChromaDB at {persist_directory}...")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_directory
    )
    print(f"Stored {len(chunks)} chunks in ChromaDB!")
    return vectorstore
def run_ingestion(repo_url, persist_directory=CHROMA_DIR):
    print("Starting ingestion pipeline...")
    print("=" * 50)
    clone_repo(repo_url)
    documents = load_files()
    if not documents:
        print("No supported files found in the repository!")
        return {"files": 0, "chunks": 0, "file_list": []}
    chunks = chunk_documents(documents)
    embeddings = create_embeddings()
    store_in_chroma(chunks, embeddings, persist_directory)
    print("=" * 50)
    print("Ingestion complete!")
    print(f"Files indexed: {len(documents)}")
    print(f"Chunks created: {len(chunks)}")
    file_list = [doc["metadata"]["source"] for doc in documents]
    return {"files": len(documents), "chunks": len(chunks), "file_list": file_list}
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ingest.py <github_repo_url>")
        sys.exit(1)
    run_ingestion(sys.argv[1])
