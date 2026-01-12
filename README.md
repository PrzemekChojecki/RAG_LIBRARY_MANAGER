# 📚 RAG Library Manager

A professional document management system designed to streamline the ingestion, conversion, and chunking of documents for RAG (Retrieval-Augmented Generation) pipelines.

## 🚀 Features

- **Multi-format Ingestion**: Support for `PDF`, `DOCX`, and `TXT` files.
- **Hierarchical Storage**: Organize documents into organized **Catalogs**.
- **Version Control & Archiving**: 
  - Automatic ZIP-based archiving upon document updates.
  - **⏪ Retrieve**: Restore any archived version back into your active pipeline.
- **Markdown Conversion**: Choice between `MarkItDown` (Microsoft) and `PyMuPDF4LLM` for high-quality Markdown extraction.
- **Advanced Chunking**:
  - **Sentence-based**: Configurable sentence sliding windows.
  - **Paragraph-based**: Structural chunking respecting document boundaries.
- **Interactive Previews**: 
  - Real-time Markdown preview.
  - Visual chunk boundary highlighting within the text.
- **Batch Processing**: Mass conversion and chunking for entire catalogs with one click and progress tracking.
- **Global Status Explorer**: Detailed, collapsible overview of all artifacts and processing states across the entire repository.

## 🛠️ Tech Stack

- **Frontend**: [Streamlit](https://streamlit.io/)
- **Document Conversion**: [MarkItDown](https://github.com/microsoft/markitdown), `PyMuPDF4LLM`
- **Logic**: Python 3.13+, Pathlib, Shutil
- **Storage**: Local Filesystem with JSON metadata tracking

## 📦 Installation & Setup

### Prerequisites
- Python 3.13
- [uv](https://github.com/astral-sh/uv) (recommended for dependency management)

### Quick Start
1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd RAG_LIBRARY_MANAGER
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Launch the application**:
   ```bash
   streamlit run app.py
   ```

## 📁 Project Structure

- `app.py`: The heart of the application (Streamlit UI).
- `src/core/`:
  - `storage.py`: Core filesystem management, metadata, and archival logic.
  - `ingest.py`: Validation and secure document intake.
  - `converter.py`: Management of conversion engines.
  - `chunker_manager.py`: Registry and execution of chunking strategies.
- `src/chunkers/`: Individual chunking algorithm implementations.
- `data/`: Local storage for documents (Git ignored).
- `archive/`: Storage for versioned ZIP archives (Git ignored).

## 🛡️ Data Safety
The system prioritizes your data. Every manual update or restoration triggers an automatic archive of the current state, ensuring you can always roll back to any point in time using the **Retrieve** feature.

---
*Developed with ❤️ as part of the RAG pipeline ecosystem.*
