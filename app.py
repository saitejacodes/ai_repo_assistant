import streamlit as st
from ingest import run_ingestion
from main import create_chain, get_response
import os
import re
st.set_page_config(
    page_title="Repo Chat Assistant",
    page_icon="GRC",
    layout="wide"
)
st.markdown("""
<style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .source-file {
        background-color: #f0f2f6;
        padding: 4px 8px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 0.85em;
        margin: 2px 0;
    }
    .chat-placeholder {
        text-align: center;
        padding: 60px 20px;
        color: #888;
    }
    .stats-box {
        background-color: #e8f4e8;
        padding: 10px 15px;
        border-radius: 8px;
        border-left: 4px solid #28a745;
        margin-top: 10px;
    }
    .stack-info {
        font-size: 0.75em;
        color: #888;
        padding: 10px 0;
        border-top: 1px solid #eee;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chain" not in st.session_state:
    st.session_state.chain = None
if "repo_loaded" not in st.session_state:
    st.session_state.repo_loaded = False
if "repo_url" not in st.session_state:
    st.session_state.repo_url = ""
if "ingestion_stats" not in st.session_state:
    st.session_state.ingestion_stats = None
def is_valid_github_url(url):
    pattern = r"^https?://github\.com/[\w.-]+/[\w.-]+(\.git)?/?$"
    return bool(re.match(pattern, url.strip()))
def handle_indexing(repo_url):
    if not repo_url or not repo_url.strip():
        st.sidebar.error("Please enter a GitHub repository URL.")
        return
    if not is_valid_github_url(repo_url):
        st.sidebar.error("Invalid GitHub URL. Please enter a valid public repository URL.")
        return
    try:
        with st.sidebar.status("Indexing repository...", expanded=True) as status:
            import time
            import glob
            import shutil
            new_path = f"chroma_db_{int(time.time())}"
            st.session_state.chain = None
            st.session_state.repo_loaded = False
            import gc
            gc.collect()
            st.write("Cloning repository...")
            stats = run_ingestion(repo_url.strip(), persist_directory=new_path)
            if stats["files"] == 0:
                st.sidebar.error("No supported files found in this repository.")
                return
            st.write("Building retrieval chain...")
            st.session_state.chain = create_chain(persist_directory=new_path)
            st.session_state.repo_loaded = True
            st.session_state.repo_url = repo_url.strip()
            st.session_state.messages = []
            st.session_state.ingestion_stats = stats
            for old_db in glob.glob("chroma_db_*"):
                if old_db != new_path:
                    try:
                        shutil.rmtree(old_db, ignore_errors=True)
                    except:
                        pass
            status.update(label="Indexing complete!", state="complete")
    except Exception as e:
        error_msg = str(e).lower()
        if "repository not found" in error_msg or "does not exist" in error_msg:
            st.sidebar.error("Repository not found. Make sure the URL is correct and the repo is public.")
        else:
            st.sidebar.error(f"Error: {str(e)}")
with st.sidebar:
    st.title("GitHub Repo Chat")
    st.markdown("---")
    repo_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/user/repo",
        value=st.session_state.repo_url
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Index Repo", use_container_width=True):
            handle_indexing(repo_url)
    with col2:
        if st.button("Re-index", use_container_width=True, disabled=not st.session_state.repo_loaded):
            handle_indexing(st.session_state.repo_url)
    if st.session_state.repo_loaded and st.session_state.ingestion_stats:
        stats = st.session_state.ingestion_stats
        st.markdown(f"""
        <div class="stats-box">
            <strong>Repository Indexed</strong><br>
            Files: {stats['files']}<br>
            Chunks: {stats['chunks']}
        </div>
        """, unsafe_allow_html=True)
        with st.expander("View Indexed Files"):
            for file_path in stats.get("file_list", []):
                st.markdown(f"<div class='source-file'>{file_path}</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class="stack-info">
        <strong>Tech Stack</strong><br>
        🌟 Intelligence: Llama 3.3 70B (Groq)<br>
        Embeddings: all-MiniLM-L6-v2<br>
        Vector DB: ChromaDB<br>
        Framework: LangChain<br>
        UI: Streamlit
    </div>
    """, unsafe_allow_html=True)
st.title("Repository Intelligence Dashboard")
if not st.session_state.repo_loaded:
    st.markdown("""
    <div class="chat-placeholder">
        <h3>Welcome to GitHub Repo Chat Assistant</h3>
        <p>Enter a public GitHub repository URL in the sidebar and click <strong>Index Repo</strong> to get started.</p>
        <p>Once indexed, you can ask questions about the codebase and get answers with file references.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("sources"):
                with st.expander("Sources"):
                    for source in message["sources"]:
                        st.markdown(f"- `{source}`")
    if prompt := st.chat_input("Ask a question about the codebase..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    result = get_response(st.session_state.chain, prompt)
                    answer = result["answer"]
                    sources = result["sources"]
                    st.markdown(answer)
                    if sources:
                        with st.expander("Sources"):
                            for source in sources:
                                st.markdown(f"- `{source}`")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources
                    })
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    



