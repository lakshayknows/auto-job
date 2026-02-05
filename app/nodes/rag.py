"""RAG context retrieval node.

Retrieves relevant context from job description and resume for tailoring.
Implements retrieval logic as defined in rag_context.md.
"""

import hashlib

from app.config import RAG_INDEX_DIR, RESUME_DIR, get_config, get_logger
from app.state import JobState, RAGContext

logger = get_logger("rag")

# Try to import chromadb, fallback to simple mode if not available
try:
    from langchain_chroma import Chroma
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("chromadb not available - using simple RAG fallback")


def get_embeddings():
    """Get embedding model instance.

    Returns:
        GoogleGenerativeAIEmbeddings instance or None
    """
    if not CHROMA_AVAILABLE:
        return None

    config = get_config()
    return GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=config.llm.google_api_key,
    )


def load_base_resume() -> str:
    """Load base resume LaTeX content.

    Returns:
        Resume content as string
    """
    resume_path = RESUME_DIR / "base_resume.tex"
    if not resume_path.exists():
        raise FileNotFoundError(f"Base resume not found: {resume_path}")

    with open(resume_path, "r", encoding="utf-8") as f:
        return f.read()


def extract_skills_from_text(text: str) -> list[str]:
    """Extract skill keywords from text.

    Args:
        text: Text to extract skills from

    Returns:
        List of skill keywords
    """
    # Common tech keywords to look for
    tech_keywords = [
        "python",
        "rust",
        "javascript",
        "typescript",
        "java",
        "go",
        "c++",
        "react",
        "vue",
        "angular",
        "node",
        "django",
        "flask",
        "fastapi",
        "tensorflow",
        "pytorch",
        "scikit-learn",
        "pandas",
        "numpy",
        "docker",
        "kubernetes",
        "aws",
        "gcp",
        "azure",
        "sql",
        "postgresql",
        "mongodb",
        "redis",
        "git",
        "linux",
        "api",
        "rest",
        "graphql",
        "machine learning",
        "deep learning",
        "nlp",
        "llm",
        "rag",
        "langchain",
        "langgraph",
        "openai",
        "gemini",
    ]

    text_lower = text.lower()
    found_skills = []

    for skill in tech_keywords:
        if skill in text_lower:
            found_skills.append(skill)

    return found_skills


def simple_retrieve_context(state: JobState) -> JobState:
    """Simple RAG fallback without vector database.

    Uses keyword extraction instead of embeddings.
    """
    job_data = state.get("job_data", {})
    job_description = job_data.get("description", "")

    try:
        resume_content = load_base_resume()
    except FileNotFoundError:
        resume_content = ""

    # Extract skills from both
    job_skills = extract_skills_from_text(job_description)
    resume_skills = extract_skills_from_text(resume_content)

    # Build simple context
    rag_context: RAGContext = {
        "job_skills": job_skills,
        "job_responsibilities": [job_description[:500]],
        "job_tech_stack": job_skills[:10],
        "resume_experience": [resume_content[:500]] if resume_content else [],
        "resume_projects": [],
        "resume_skills": resume_skills,
    }

    logger.info(
        f"Simple RAG: {len(job_skills)} job skills, {len(resume_skills)} resume skills"
    )

    return {
        **state,
        "rag_context": rag_context,
    }


def retrieve_context(state: JobState) -> JobState:
    """LangGraph node: Retrieve relevant context for resume/email.

    Args:
        state: Current job state with job_data

    Returns:
        Updated state with rag_context
    """
    config = get_config()

    # Check CRON_MODE
    if config.cron_mode:
        logger.info("CRON_MODE active - skipping RAG retrieval")
        return {
            **state,
            "should_skip": True,
            "skip_reason": "CRON_MODE active",
        }

    # Check if already retrieved
    if state.get("rag_context"):
        logger.info("RAG context already exists - skipping")
        return state

    job_data = state.get("job_data", {})
    job_id = state.get("job_id", "unknown")
    job_description = job_data.get("description", "")

    if not job_description:
        logger.warning("No job description available")
        return {
            **state,
            "errors": state.get("errors", []) + ["No job description for RAG"],
        }

    # Use simple fallback if chromadb not available
    if not CHROMA_AVAILABLE:
        return simple_retrieve_context(state)

    try:
        # Get job index path
        index_path = RAG_INDEX_DIR / f"job_{job_id[:8]}"

        # Split job description
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
        )
        chunks = splitter.split_text(job_description)

        # Create job index
        logger.info(f"Creating job index with {len(chunks)} chunks")
        job_index = Chroma.from_texts(
            texts=chunks,
            embedding=get_embeddings(),
            persist_directory=str(index_path),
            metadatas=[
                {"source": "job_description", "chunk": i} for i in range(len(chunks))
            ],
        )

        # Load and create resume index
        resume_content = load_base_resume()
        content_hash = hashlib.sha256(resume_content.encode()).hexdigest()[:8]
        resume_path = RAG_INDEX_DIR / f"resume_{content_hash}"

        resume_chunks = splitter.split_text(resume_content)
        resume_index = Chroma.from_texts(
            texts=resume_chunks,
            embedding=get_embeddings(),
            persist_directory=str(resume_path),
            metadatas=[
                {"source": "resume", "chunk": i} for i in range(len(resume_chunks))
            ],
        )

        # Query for relevant job context
        job_results = job_index.similarity_search(
            "required skills responsibilities qualifications",
            k=3,
        )

        # Query for relevant resume context
        resume_query = (
            job_data.get("role", "")
            + " "
            + " ".join(extract_skills_from_text(job_description)[:5])
        )
        resume_results = resume_index.similarity_search(
            resume_query,
            k=3,
        )

        # Build context
        rag_context: RAGContext = {
            "job_skills": extract_skills_from_text(job_description),
            "job_responsibilities": [doc.page_content for doc in job_results],
            "job_tech_stack": extract_skills_from_text(
                " ".join(doc.page_content for doc in job_results)
            ),
            "resume_experience": [
                doc.page_content
                for doc in resume_results
                if "experience" in doc.page_content.lower()
            ],
            "resume_projects": [
                doc.page_content
                for doc in resume_results
                if "project" in doc.page_content.lower()
            ],
            "resume_skills": extract_skills_from_text(
                " ".join(doc.page_content for doc in resume_results)
            ),
        }

        logger.info(
            f"Retrieved RAG context: {len(rag_context['job_skills'])} job skills, "
            f"{len(rag_context['resume_skills'])} resume skills"
        )

        return {
            **state,
            "rag_context": rag_context,
        }

    except Exception:
        logger.exception("RAG retrieval failed, using fallback")
        return simple_retrieve_context(state)
