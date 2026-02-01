"""
RAG module for LangChain-based retrieval-augmented generation.
Implements hash-based caching and incremental indexing for cost efficiency.
"""

import hashlib
import json
import pickle
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.config import Config


class RAGManager:
    """
    Manages RAG (Retrieval-Augmented Generation) for job automation.
    
    Features:
    - Separate vector stores for jobs and resume
    - Hash-based embedding cache to avoid re-embedding
    - Incremental indexing
    - Deterministic and explainable retrieval
    """

    def __init__(self):
        Config.ensure_directories()
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=Config.EMBEDDING_MODEL,
            google_api_key=Config.GOOGLE_API_KEY,
        )
        self.job_vectorstore: Optional[FAISS] = None
        self.resume_vectorstore: Optional[FAISS] = None
        self._load_existing_indices()

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cached_embedding(self, content_hash: str) -> Optional[list[float]]:
        """Retrieve cached embedding if it exists."""
        cache_path = Config.EMBEDDINGS_CACHE / f"{content_hash}.pkl"
        if cache_path.exists():
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        return None

    def _cache_embedding(self, content_hash: str, embedding: list[float]) -> None:
        """Cache an embedding to disk."""
        cache_path = Config.EMBEDDINGS_CACHE / f"{content_hash}.pkl"
        with open(cache_path, "wb") as f:
            pickle.dump(embedding, f)

    def _load_existing_indices(self) -> None:
        """Load existing FAISS indices if they exist."""
        job_index_path = Config.JOB_INDEX_DIR / "index.faiss"
        resume_index_path = Config.RESUME_INDEX_DIR / "index.faiss"

        if job_index_path.exists():
            try:
                self.job_vectorstore = FAISS.load_local(
                    str(Config.JOB_INDEX_DIR),
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
                print("Loaded existing job index.")
            except Exception as e:
                print(f"Could not load job index: {e}")

        if resume_index_path.exists():
            try:
                self.resume_vectorstore = FAISS.load_local(
                    str(Config.RESUME_INDEX_DIR),
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
                print("Loaded existing resume index.")
            except Exception as e:
                print(f"Could not load resume index: {e}")

    def _get_indexed_hashes(self, index_dir: Path) -> set[str]:
        """Get set of content hashes already indexed."""
        hash_file = index_dir / "indexed_hashes.json"
        if hash_file.exists():
            with open(hash_file, "r") as f:
                return set(json.load(f))
        return set()

    def _save_indexed_hashes(self, index_dir: Path, hashes: set[str]) -> None:
        """Save set of indexed content hashes."""
        hash_file = index_dir / "indexed_hashes.json"
        with open(hash_file, "w") as f:
            json.dump(list(hashes), f)

    def index_jobs(self) -> int:
        """
        Index job descriptions from jobs.json.
        Uses incremental indexing - only indexes new jobs.
        Returns number of new jobs indexed.
        """
        if not Config.JOBS_JSON.exists():
            print("No jobs.json found. Run scraper first.")
            return 0

        with open(Config.JOBS_JSON, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        if not jobs:
            print("No jobs to index.")
            return 0

        # Get already indexed hashes
        indexed_hashes = self._get_indexed_hashes(Config.JOB_INDEX_DIR)

        # Prepare new documents
        new_docs = []
        new_hashes = []

        for job in jobs:
            content = f"""
Company: {job.get('company', '')}
Role: {job.get('role', '')}
Description: {job.get('description', '')}
URL: {job.get('url', '')}
"""
            content_hash = self._compute_hash(content)

            if content_hash not in indexed_hashes:
                doc = Document(
                    page_content=content,
                    metadata={
                        "job_id": job.get("id", ""),
                        "company": job.get("company", ""),
                        "role": job.get("role", ""),
                        "hash": content_hash,
                    },
                )
                new_docs.append(doc)
                new_hashes.append(content_hash)

        if not new_docs:
            print("No new jobs to index.")
            return 0

        print(f"Indexing {len(new_docs)} new jobs...")

        # Create or update vector store
        if self.job_vectorstore is None:
            self.job_vectorstore = FAISS.from_documents(new_docs, self.embeddings)
        else:
            self.job_vectorstore.add_documents(new_docs)

        # Save index
        self.job_vectorstore.save_local(str(Config.JOB_INDEX_DIR))

        # Update indexed hashes
        indexed_hashes.update(new_hashes)
        self._save_indexed_hashes(Config.JOB_INDEX_DIR, indexed_hashes)

        print(f"Indexed {len(new_docs)} new jobs.")
        return len(new_docs)

    def index_resume(self) -> bool:
        """
        Index the base resume.
        Only re-indexes if resume content has changed.
        Returns True if indexed, False if skipped.
        """
        if not Config.BASE_RESUME_TEX.exists():
            print("No base_resume.tex found.")
            return False

        with open(Config.BASE_RESUME_TEX, "r", encoding="utf-8") as f:
            resume_content = f.read()

        content_hash = self._compute_hash(resume_content)
        indexed_hashes = self._get_indexed_hashes(Config.RESUME_INDEX_DIR)

        if content_hash in indexed_hashes:
            print("Resume already indexed (unchanged).")
            return False

        print("Indexing resume...")

        doc = Document(
            page_content=resume_content,
            metadata={"type": "base_resume", "hash": content_hash},
        )

        self.resume_vectorstore = FAISS.from_documents([doc], self.embeddings)
        self.resume_vectorstore.save_local(str(Config.RESUME_INDEX_DIR))

        self._save_indexed_hashes(Config.RESUME_INDEX_DIR, {content_hash})

        print("Resume indexed.")
        return True

    def build_index(self) -> dict:
        """
        Build or update both job and resume indices.
        Returns summary of indexing operations.
        """
        print("Building RAG index...")

        result = {
            "jobs_indexed": self.index_jobs(),
            "resume_indexed": self.index_resume(),
        }

        print("RAG index build complete.")
        return result

    def retrieve_job_context(self, job_id: str, k: int = 3) -> list[Document]:
        """
        Retrieve context for a specific job.
        Returns relevant job descriptions for comparison.
        """
        if self.job_vectorstore is None:
            print("Job index not loaded.")
            return []

        # Find the job by ID
        if not Config.JOBS_JSON.exists():
            return []

        with open(Config.JOBS_JSON, "r", encoding="utf-8") as f:
            jobs = json.load(f)

        target_job = None
        for job in jobs:
            if job.get("id") == job_id:
                target_job = job
                break

        if not target_job:
            return []

        # Use job description as query
        query = f"{target_job.get('role', '')} {target_job.get('description', '')[:500]}"
        return self.job_vectorstore.similarity_search(query, k=k)

    def retrieve_resume_context(self) -> Optional[Document]:
        """Retrieve the base resume document."""
        if self.resume_vectorstore is None:
            print("Resume index not loaded.")
            return None

        results = self.resume_vectorstore.similarity_search("resume experience skills", k=1)
        return results[0] if results else None

    def get_combined_context(self, job_id: str) -> str:
        """
        Get combined context for resume tailoring and email generation.
        Returns job description + base resume content.
        """
        context_parts = []

        # Get job context
        job_docs = self.retrieve_job_context(job_id, k=1)
        if job_docs:
            context_parts.append("=== TARGET JOB ===")
            context_parts.append(job_docs[0].page_content)

        # Get resume context
        resume_doc = self.retrieve_resume_context()
        if resume_doc:
            context_parts.append("\n=== BASE RESUME ===")
            context_parts.append(resume_doc.page_content)

        return "\n".join(context_parts)


def main():
    """Entry point for RAG module."""
    rag = RAGManager()
    rag.build_index()


if __name__ == "__main__":
    main()
