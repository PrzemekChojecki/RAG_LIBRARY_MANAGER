import streamlit as st
import os
import time
from pathlib import Path
from src.core.storage import StorageManager
from src.core.ingest import IngestManager
from src.core.converter import ConverterManager
from src.core.chunker_manager import ChunkerManager
from src.core.config import (
    CHUNK_HIGHLIGHT_COLOR, 
    DEFAULT_SENTENCES_PER_CHUNK, 
    DEFAULT_MIN_CHUNK_LENGTH,
    ALLOWED_EXTENSIONS
)
from src.chunkers.sentence import SentenceChunker
from src.chunkers.paragraph import ParagraphChunker


# Session State Init
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# Initialize Managers
storage = StorageManager()
ingest = IngestManager(storage)
converter = ConverterManager(storage)
chunker_mgr = ChunkerManager(storage)
chunker_mgr.register_chunker(SentenceChunker())
chunker_mgr.register_chunker(ParagraphChunker())

def render_tree(path: Path, prefix: str = "") -> str:
    """Helper to render a filesystem tree as a string."""
    tree = ""
    # Get sorted list of files/dirs
    items = sorted(list(path.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
    for i, item in enumerate(items):
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "
        tree += f"{prefix}{connector}{item.name}\n"
        if item.is_dir():
            extension = "    " if is_last else "│   "
            tree += render_tree(item, prefix + extension)
    return tree

st.set_page_config(page_title="RAG Library Manager", layout="wide")

st.title("📚 RAG Library Manager")
st.markdown("Automated Document Ingestion & Chunking Pipeline")

# Top-level Navigation
main_tab1, main_tab_batch, main_tab2 = st.tabs(["🚀 Pipeline", "⚙️ Batch Process", "📁 Global Explorer"])

# --- SIDEBAR ---
with st.sidebar:
    st.image("src/resources/sokrates.transparent.png", width="stretch")
    st.header("Storage")
    categories = storage.list_categories()
    
    selected_cat = st.selectbox("Select Catalog", ["(New Catalog)"] + categories)
    if selected_cat == "(New Catalog)":
        new_cat = st.text_input("New Catalog Name")
        if st.button("Create Catalog"):
            if new_cat:
                (storage.root_path / new_cat).mkdir(exist_ok=True)
                st.rerun()
            else:
                st.error("Enter a name")
        category = new_cat
    else:
        category = selected_cat

with main_tab1:
    # --- MAIN PIPELINE VIEW ---
    if category:
        st.subheader(f"Catalog: {category}")
        
        # Upload
        with st.expander("⬆️ Upload Document"):
            max_mb = st.config.get_option("server.maxUploadSize")
            allowed_types = [ext.replace(".", "") for ext in ALLOWED_EXTENSIONS]
            uploaded_files = st.file_uploader(
                f"Choose files (max {max_mb}MB each)", 
                type=allowed_types, 
                accept_multiple_files=True,
                key=f"uploader_{st.session_state.uploader_key}"
            )

            # Clear previous results if new files are picked or if uploader is empty
            if "ingest_results" in st.session_state and not uploaded_files:
                del st.session_state.ingest_results

            if uploaded_files:
                if st.button("Ingest Files"):
                    st.session_state.ingest_results = []
                    any_exists = False
                    for up_file in uploaded_files:
                        content = up_file.getvalue()
                        success, msg = ingest.process_upload(category, up_file.name, content)
                        
                        if success:
                            st.session_state.last_uploaded_doc = Path(up_file.name).stem
                        if not success and msg.startswith("EXISTS:"):
                            any_exists = True
                        
                        st.session_state.ingest_results.append({
                            "name": up_file.name,
                            "content": content,
                            "success": success,
                            "msg": msg
                        })
                    
                    if not any_exists:
                        time.sleep(1)
                        st.session_state.uploader_key += 1
                        st.rerun()

                if "ingest_results" in st.session_state:
                    for res in st.session_state.ingest_results:
                        if not res["success"] and res["msg"].startswith("EXISTS:"):
                            doc_name = res["msg"].split(":")[1]
                            st.warning(f"Document '{doc_name}' already exists in this catalog.")
                            if st.button(f"Update & Archive '{doc_name}'", key=f"upd_{doc_name}"):
                                with st.spinner("Updating..."):
                                    up_success, up_msg = ingest.update_document(category, res["name"], res["content"], target_doc_name=doc_name)
                                    if up_success:
                                        st.success(up_msg)
                                        # Set as last uploaded for selection
                                        st.session_state.last_uploaded_doc = Path(res["name"]).stem
                                        # Clear results and reset uploader
                                        st.session_state.uploader_key += 1
                                        st.rerun()
                                    else:
                                        st.error(up_msg)
                        elif res["success"]:
                            st.success(f"Done: {res['name']} - {res['msg']}")
                        else:
                            st.error(f"Error {res['name']}: {res['msg']}")

        # Document List
        docs = storage.list_documents(category)
        allowed_types = [ext.replace(".", "") for ext in ALLOWED_EXTENSIONS]
        
        if docs:
            # Determine index for newly uploaded doc
            default_idx = 0
            if "last_uploaded_doc" in st.session_state and st.session_state.last_uploaded_doc in docs:
                default_idx = docs.index(st.session_state.last_uploaded_doc)

            col_doc_sel, col_doc_upd, col_doc_ret, col_doc_del = st.columns([3, 1, 1, 1], vertical_alignment="bottom")
            with col_doc_sel:
                selected_doc = st.selectbox("Select Document", docs, key="doc_selector", index=default_idx)
            
            with col_doc_upd:
                with st.popover("🔄 Update", width="stretch"):
                    st.write(f"Replace **{selected_doc}**")
                    st.info("Current version will be archived.")
                    new_ver_file = st.file_uploader("Upload new version", type=allowed_types, key="new_ver_up")
                    if new_ver_file:
                        if st.button("Confirm Update", width="stretch", type="primary"):
                            with st.spinner("Updating..."):
                                success, msg = ingest.update_document(category, new_ver_file.name, new_ver_file.getvalue(), target_doc_name=selected_doc)
                                if success:
                                    st.session_state.last_uploaded_doc = Path(new_ver_file.name).stem
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

            with col_doc_ret:
                with st.popover("⏪ Retrieve", width="stretch"):
                    st.write("Restore from any archive:")
                    archives = storage.list_archives()
                    if archives:
                        selected_archive = st.selectbox("Select Version", archives)
                        st.warning("Restoring will overwrite current files!")
                        if st.button("Restore Selected", width="stretch", type="primary"):
                            with st.spinner("Restoring..."):
                                r_cat, r_doc = storage.restore_archive(selected_archive, category, selected_doc)
                                st.session_state.last_uploaded_doc = r_doc
                                st.success(f"Restored to {r_cat}/{r_doc}")
                                st.rerun()
                    else:
                        st.info("No archives found.")
            
            with col_doc_del:
                if st.button("🗑️ Delete", type="secondary", width="stretch"):
                    storage.delete_document(category, selected_doc)
                    st.rerun()
            
            if selected_doc:
                metadata = storage.load_metadata(category, selected_doc)
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.info(f"**ID:** {metadata['document_id']}\n\n**Size:** {metadata['file_size_mb']} MB")
                    
                    # ... (Conversion and Chunking buttons)
                    st.write("---")
                    st.write("⚙️ Markdown Conversion")
                    tool = st.radio('Select a conversion tool:', options=["markitdown", "pymupdf4llm"], horizontal=True)
                    if st.button("Convert to Markdown"):
                        with st.spinner("Converting..."):
                            success, msg = converter.convert_to_markdown(category, selected_doc, tool)
                            if success: st.success(msg)
                            else: st.error(msg)
                    
                    # Chunking Section
                    st.write("---")
                    st.write("### ✂️ Chunking")
                    
                    # List available conversions for chunking
                    converted_dir = storage.get_document_dir(category, selected_doc) / "converted"
                    if converted_dir.exists():
                        conv_files = [f.name for f in converted_dir.glob("*.md")]
                        if conv_files:
                            selected_conv_to_chunk = st.selectbox("Select Conversion for Chunking", conv_files)
                            chunker_type = st.selectbox("Select Chunker", ["sentence_v1", "paragraph_v1"])
                            
                            config = {}
                            if chunker_type == "sentence_v1":
                                config["sentences_per_chunk"] = st.number_input("Sentences per chunk", 1, 100, DEFAULT_SENTENCES_PER_CHUNK)
                            elif chunker_type == "paragraph_v1":
                                config["min_length"] = st.number_input("Min chunk length (chars)", 10, 5000, DEFAULT_MIN_CHUNK_LENGTH)
                            
                            if st.button("Run Chunking"):
                                with st.spinner("Chunking..."):
                                    success, msg = chunker_mgr.run_chunking(category, selected_doc, selected_conv_to_chunk, chunker_type, config)
                                    if success: st.success(msg)
                                    else: st.error(msg)
                        else:
                            st.warning("No converted files available for chunking.")
                    else:
                        st.warning("No conversion folder found.")

                with col2:
                    # Previews
                    tab1, tab2, tab3 = st.tabs(["Original", "Markdown", "Chunks"])
                    
                    with tab1:
                        st.write(f"Original file stored in `original/` folder.")
                        
                    with tab2:
                        converted_dir = storage.get_document_dir(category, selected_doc) / "converted"
                        if converted_dir.exists():
                            conv_files = [f.name for f in converted_dir.glob("*.md")]
                            if conv_files:
                                c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
                                with c1:
                                    selected_conv_preview = st.selectbox("Select Conversion Preview", conv_files)
                                with c2:
                                    if st.button("🗑️ Delete", key="del_conv", width="stretch"):
                                        storage.delete_file(converted_dir / selected_conv_preview)
                                        st.rerun()
                                
                                with open(converted_dir / selected_conv_preview, "r", encoding="utf-8") as f:
                                    st.markdown(f.read())
                            else:
                                st.warning("No converted files found.")
                        else:
                            st.warning("Not converted yet.")
                            
                    # Chunks Preview Tab
                    with tab3:
                        chunked_dir = storage.get_document_dir(category, selected_doc) / "chunked"
                        if chunked_dir.exists():
                            chunk_files = list(chunked_dir.glob("*.md"))
                            if chunk_files:
                                # Settings for preview
                                st.write("#### Preview Settings")
                                highlight_color = CHUNK_HIGHLIGHT_COLOR
                                
                                c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
                                with c1:
                                    selected_chunk_file = st.selectbox("View Chunk Run", [f.name for f in chunk_files])
                                with c2:
                                    if st.button("🗑️ Delete", key="del_chunk", width="stretch"):
                                        storage.delete_file(chunked_dir / selected_chunk_file)
                                        # Sync metadata after deletion
                                        metadata = storage.load_metadata(category, selected_doc)
                                        if metadata:
                                            existing_files = {f.name for f in chunked_dir.glob("*.md")}
                                            metadata["chunking"] = [e for e in metadata.get("chunking", []) if e.get("filename") in existing_files]
                                            storage.save_metadata(category, selected_doc, metadata)
                                        st.rerun()

                                with open(chunked_dir / selected_chunk_file, "r", encoding="utf-8") as f:
                                    content = f.read()
                                    
                                # Highlighting logic
                                import re
                                styled_content = content
                                # Replace start marker
                                styled_content = re.sub(
                                    r'<!-- chunk_id_start: (.*?) -->', 
                                    f'<div style="color: {highlight_color}; font-weight: bold; border-top: 2px solid {highlight_color}; margin-top: 10px; padding-top: 5px;">[START CHUNK: \\1]</div>', 
                                    styled_content
                                )
                                # Replace end marker
                                styled_content = re.sub(
                                    r'<!-- chunk_id_end: (.*?) -->', 
                                    f'<div style="color: {highlight_color}; font-weight: bold; border-bottom: 2px dashed {highlight_color}; margin-bottom: 20px; padding-bottom: 5px;">[END CHUNK: \\1]</div>', 
                                    styled_content
                                )
                                
                                st.markdown(styled_content, unsafe_allow_html=True)
                            else:
                                st.warning("No chunk runs found.")
                        else:
                            st.warning("Not chunked yet.")

        else:
            st.info("No documents in this category.")
    else:
        st.info("Select or create a category in the sidebar to begin.")

with main_tab_batch:
    st.write("### ⚙️ Catalog Batch Processing")

    if category:
        st.info(f"Applying actions to all documents in: **{category}**")
        
        col_b1, col_b2 = st.columns(2)
        
        with col_b1:
            st.write("#### 📝 Batch Markdown Conversion")
            b_tool = st.radio('Conversion tool:', options=["markitdown", "pymupdf4llm"], horizontal=True, key="batch_conv_tool")
            if st.button("🚀 Convert All to Markdown", width="stretch"):
                docs = storage.list_documents(category)
                if not docs:
                    st.warning("No documents to convert.")
                else:
                    progress_bar = st.progress(0)
                    for i, d in enumerate(docs):
                        with st.spinner(f"Converting {d}..."):
                            success, msg = converter.convert_to_markdown(category, d, b_tool)
                        progress_bar.progress((i + 1) / len(docs))
                    
                    st.success(f"Batch conversion completed for {len(docs)} documents.")
                    time.sleep(1)
                    st.rerun()

        with col_b2:
            st.write("#### ✂️ Batch Chunking")
            b_chunker_type = st.selectbox("Chunker:", ["sentence_v1", "paragraph_v1"], key="batch_chunk_type")
            
            b_config = {}
            if b_chunker_type == "sentence_v1":
                b_config["sentences_per_chunk"] = st.number_input("Sentences per chunk", 1, 100, DEFAULT_SENTENCES_PER_CHUNK, key="b_sent")
            elif b_chunker_type == "paragraph_v1":
                b_config["min_length"] = st.number_input("Min chunk length (chars)", 10, 5000, DEFAULT_MIN_CHUNK_LENGTH, key="b_para")
            
            if st.button("🚀 Chunk All Conversions", width="stretch"):
                docs = storage.list_documents(category)
                count = 0
                if not docs:
                    st.warning("No documents to chunk.")
                else:
                    progress_bar = st.progress(0)
                    for i, d in enumerate(docs):
                        # Find most recent/any conversion
                        conv_dir = storage.get_document_dir(category, d) / "converted"
                        if conv_dir.exists():
                            conv_files = sorted(list(conv_dir.glob("*.md")), reverse=True)
                            if conv_files:
                                selected_conv = conv_files[0].name
                                with st.spinner(f"Chunking {d} ({selected_conv})..."):
                                    success, msg = chunker_mgr.run_chunking(category, d, selected_conv, b_chunker_type, b_config)
                                    if success: count += 1
                        progress_bar.progress((i + 1) / len(docs))
                    
                    st.success(f"Batch chunking completed. Processed {count} documents.")
                    time.sleep(1)
                    st.rerun()
    else:
        st.info("Select a catalog in the sidebar to use batch processing.")

with main_tab2:
    st.write("### 📁 Global Status Explorer")
    
    # Filter options
    col_scope, _ = st.columns([1, 2])
    with col_scope:
        scope = st.radio("View Scope", ["All Catalogs", "Selected Catalog"], horizontal=True)
    
    st.markdown("---")
    
    all_data = []
    
    # Determine categories to show
    if scope == "Selected Catalog" and category:
        categories_to_show = [category]
    else:
        categories_to_show = storage.list_categories()
    
    for cat in categories_to_show:
        docs = storage.list_documents(cat)
        for doc in docs:
            doc_dir = storage.get_document_dir(cat, doc)
            metadata = storage.load_metadata(cat, doc)
            
            # Check Converted
            conv_dir = doc_dir / "converted"
            conv_files = []
            if conv_dir.exists():
                conv_files = [f.name for f in conv_dir.glob("*.md")]
            
            # Check Chunked
            chunk_dir = doc_dir / "chunked"
            chunk_files = []
            if chunk_dir.exists():
                chunk_files = [f.name for f in chunk_dir.glob("*.md")]
            
            all_data.append({
                "Catalog": cat,
                "Document": doc,
                "Size (MB)": metadata.get("file_size_mb", 0) if metadata else 0,
                "Converted": "✅" if conv_files else "❌",
                "Conv Files": ", ".join(conv_files),
                "Chunked": "✅" if chunk_files else "❌",
                "Chunk Files": ", ".join(chunk_files),
                "Created": metadata.get("created_at", "").split("T")[0] if metadata else "N/A"
            })
    
    if all_data:
        # Group by catalog for better organization
        cat_groups = {}
        for row in all_data:
            cat = row["Catalog"]
            if cat not in cat_groups:
                cat_groups[cat] = []
            cat_groups[cat].append(row)
        
        for cat, docs in cat_groups.items():
            st.markdown(f"#### 📁 Catalog: {cat}")
            for doc in docs:
                status_icons = f"{doc['Converted']} MD | {doc['Chunked']} CH"
                with st.expander(f"{status_icons} 📄 {doc['Document']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Metadata**")
                        st.write(f"- Size: {doc['Size (MB)']} MB")
                        st.write(f"- Created: {doc['Created']}")
                    with col2:
                        st.write("**Generated Files**")
                        if doc['Conv Files']:
                            st.write(f"- 📝 Markdown: `{doc['Conv Files']}`")
                        else:
                            st.write("- 📝 Markdown: _None_")
                        
                        if doc['Chunk Files']:
                            st.write(f"- ✂️ Chunks: `{doc['Chunk Files']}`")
                        else:
                            st.write("- ✂️ Chunks: _None_")
            st.write("---")
    else:
        st.info("No documents found in any catalog.")
