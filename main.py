import os
from dotenv import load_dotenv
load_dotenv()
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CHROMA_DIR = "chroma_db"
SYSTEM_TEMPLATE = """You must ONLY answer using the provided context.
If the answer is truly not present anywhere in the context, say exactly:
I could not find that in the codebase.
Never guess. Never use outside knowledge.
If multiple chunks together contain relevant information, combine them to give the best possible response.
If the answer is not explicitly stated but can be reasonably inferred from the context, provide the inferred answer and mention which file it came from.

You are a highly knowledgeable code assistant. Use the following pieces of context from the codebase to answer the question. Follow these rules strictly:
1. Answer ONLY based on the provided context. Do not make up information.
2. Do not assume features are implemented just because they are mentioned in a README or list. Only confirm features if the actual code or logic exists in the context.
3. If something is only mentioned as a future plan or option in documentation, do NOT say it is implemented. Only confirm things that exist in actual code files.
4. Always include the relevant file names in your answer using the format: `filename.ext`
5. Be concise and technical. Keep answers as short as possible.
6. When writing code in your answers, write it in compact continuous blocks with no comments and no blank lines.
7. When answering always follow this structure:
   - Plain English explanation first, maximum 3 sentences
   - Then show the relevant code snippet if applicable
   - Then one line explaining what that code does

Context from codebase:
{context}

Question: {question}"""
def load_vectorstore(persist_directory=CHROMA_DIR):
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={"device": "mps"}
    )
    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings
    )
    return vectorstore
def format_docs(docs):
    return "\n\n".join(
        f"File: {doc.metadata.get('source', 'Unknown')}\n{doc.page_content}"
        for doc in docs
    )
class ChatChain:
    def __init__(self, persist_directory=CHROMA_DIR):
        self.vectorstore = load_vectorstore(persist_directory)
        self.retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 18}
        )
        self.llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1, api_key=GROQ_API_KEY)
        self.chat_history = []
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_TEMPLATE),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}")
        ])
        self.chain = (
            {
                "context": lambda x: format_docs(self.retriever.invoke(x["question"])),
                "question": lambda x: x["question"],
                "chat_history": lambda x: x["chat_history"]
            }
            | self.prompt
            | self.llm
            | StrOutputParser()
        )
    def ask(self, question):
        try:
            retrieved_docs = self.retriever.invoke(question)
            result = self.chain.invoke({
                "question": question,
                "chat_history": self.chat_history
            })
            self.chat_history.append(HumanMessage(content=question))
            self.chat_history.append(AIMessage(content=result))
            sources = list(set([
                doc.metadata.get("source", "Unknown")
                for doc in retrieved_docs
            ]))
            sources.sort()
            return {
                "answer": result,
                "sources": sources
            }
        except Exception as e:
            return {
                "answer": f"Error generating response: {str(e)}",
                "sources": []
            }
def create_chain(persist_directory=CHROMA_DIR):
    return ChatChain(persist_directory)
def get_response(chain, question):
    return chain.ask(question)
