import os
import pandas as pd
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from pydantic import BaseModel, Field

# Define Pydantic Schema for structured AI response
class DiagnosisOutput(BaseModel):
    root_cause: str = Field(description="The primary identified root cause of the network issue.")
    osi_layer: str = Field(description="The OSI layer where the problem occurs.")
    confidence: str = Field(description="Confidence level: High, Medium, or Low.")
    evidence: str = Field(description="Quoted evidence supporting this conclusion.")
    next_command: str = Field(description="The next recommended Cisco CLI command.")
    fix_steps: list[str] = Field(description="Step-by-step configuration commands to resolve the issue.")

class NetSageAIClient:
    def __init__(self, csv_path: str = "cases.csv"):
        self.csv_path = csv_path
        self.vector_store = None
        self._initialize_rag()
        
        # Initialize Groq LLM using the current active model identifier
        self.llm = ChatGroq(
            temperature=0.1,
            model_name="openai/gpt-oss-120b"  # Fallback to current standard model
        )
        self.parser = JsonOutputParser(pydantic_object=DiagnosisOutput)

    def _initialize_rag(self):
        """Loads cases.csv and builds a local FAISS vector store using Hugging Face embeddings."""
        if not os.path.exists(self.csv_path):
            print(f"[Warning] Dataset not found at {self.csv_path}. RAG search will be skipped.")
            return

        df = pd.read_csv(self.csv_path)
        # Combine relevant columns into a single text block for semantic searching
        documents = []
        for _, row in df.iterrows():
            doc_text = f"Title: {row.get('title', '')} | Symptom: {row.get('symptom', '')} | Fault: {row.get('expected_fault', '')} | Outputs: {row.get('show_outputs', '')}"
            documents.append(doc_text)

        # Initialize Hugging Face embeddings
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # Create Vector Store
        self.vector_store = FAISS.from_texts(documents, embeddings)
        print("[+] Hugging Face RAG Vector Store initialized successfully.")

    def get_similar_cases(self, query: str, k: int = 2) -> str:
        """Retrieves top-k similar historical cases from cases.csv via semantic search."""
        if not self.vector_store:
            return "No historical cases available."
        
        docs = self.vector_store.similarity_search(query, k=k)
        return "\n---\n".join([d.page_content for d in docs])

    def diagnose(self, symptom: str, show_outputs: str, rule_issues: list) -> dict:
        """Performs RAG-backed LLM diagnosis combining rules, logs, and historical cases."""
        
        # Retrieve relevant semantic examples from cases.csv
        semantic_context = self.get_similar_cases(symptom)
        
        system_prompt = (
            "You are NetSage AI, an expert Cisco network troubleshooting assistant. "
            "Analyze the user's symptom, raw CLI outputs, deterministic rule findings, "
            "and similar historical cases to provide a precise diagnosis.\n"
            "{format_instructions}"
        )
        
        human_prompt = (
            "User Symptom: {symptom}\n\n"
            "CLI Show Outputs:\n{show_outputs}\n\n"
            "Deterministic Rule Findings:\n{rule_issues}\n\n"
            "Similar Historical Cases (RAG Context):\n{semantic_context}"
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt)
        ])
        
        chain = prompt | self.llm | self.parser
        
        result = chain.invoke({
            "symptom": symptom,
            "show_outputs": show_outputs,
            "rule_issues": "\n".join(rule_issues) if rule_issues else "None found.",
            "semantic_context": semantic_context,
            "format_instructions": self.parser.get_format_instructions()
        })
        
        return result