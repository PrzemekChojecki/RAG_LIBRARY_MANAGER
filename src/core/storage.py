import json
from pathlib import Path
from typing import Optional, Dict, Any
from .config import DATA_ROOT, ARCHIVE_ROOT

class StorageManager:
    def __init__(self, root_path: Path = DATA_ROOT):
        self.root_path = root_path
        self.root_path.mkdir(exist_ok=True)
        ARCHIVE_ROOT.mkdir(exist_ok=True)

    def get_document_dir(self, category: str, doc_name: str) -> Path:
        return self.root_path / category / doc_name

    def ensure_document_structure(self, category: str, doc_name: str) -> Dict[str, Path]:
        doc_dir = self.get_document_dir(category, doc_name)
        paths = {
            "root": doc_dir,
            "original": doc_dir / "original",
            "converted": doc_dir / "converted",
            "chunked": doc_dir / "chunked"
        }
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
        return paths

    def get_metadata_path(self, category: str, doc_name: str) -> Path:
        return self.get_document_dir(category, doc_name) / "metadata.json"

    def save_metadata(self, category: str, doc_name: str, metadata: Dict[str, Any]):
        path = self.get_metadata_path(category, doc_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def load_metadata(self, category: str, doc_name: str) -> Optional[Dict[str, Any]]:
        path = self.get_metadata_path(category, doc_name)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def list_categories(self) -> list[str]:
        return [d.name for d in self.root_path.iterdir() if d.is_dir()]

    def list_documents(self, category: str) -> list[str]:
        cat_dir = self.root_path / category
        if not cat_dir.exists():
            return []
        return [d.name for d in cat_dir.iterdir() if d.is_dir()]

    def delete_file(self, file_path: Path):
        if file_path.exists():
            file_path.unlink()

    def delete_document(self, category: str, doc_name: str):
        import shutil
        doc_dir = self.get_document_dir(category, doc_name)
        if doc_dir.exists():
            shutil.rmtree(doc_dir)

    def archive_document(self, category: str, doc_name: str) -> str:
        import shutil
        from datetime import datetime
        doc_dir = self.get_document_dir(category, doc_name)
        if not doc_dir.exists():
            return ""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use double underscore for safer parsing
        archive_name = f"{category}__{doc_name}__{timestamp}"
        archive_path = ARCHIVE_ROOT / archive_name
        
        shutil.make_archive(str(archive_path), 'zip', str(doc_dir))
        return f"{archive_name}.zip"

    def list_archives(self) -> list[str]:
        """List all zip files in archive/."""
        archives = []
        if ARCHIVE_ROOT.exists():
            for f in ARCHIVE_ROOT.glob("*.zip"):
                archives.append(f.name)
        return sorted(archives, reverse=True)

    def restore_archive(self, archive_filename: str, current_cat: str, current_doc: str) -> tuple[str, str]:
        """
        Restore an archive. 
        1. Archives the CURRENT state of the selected document.
        2. Deletes the current state.
        3. Parses the original identity from the archive and restores it there.
        """
        import shutil
        archive_path = ARCHIVE_ROOT / archive_filename
        if not archive_path.exists():
            return current_cat, current_doc
        
        # Try to parse original identity from archive filename
        clean_name = archive_filename.replace(".zip", "")
        if "__" in clean_name:
            parts = clean_name.split("__")
            res_cat = parts[0]
            res_doc = parts[1]
        else:
            # Fallback for old format: category_docname_timestamp
            parts = clean_name.split("_")
            if len(parts) >= 3:
                res_cat = parts[0]
                res_doc = "_".join(parts[1:-1])
            else:
                res_cat, res_doc = current_cat, current_doc

        # 1. Archive the CURRENT state to prevent data loss
        self.archive_document(current_cat, current_doc)
        
        # 2. Delete the CURRENT state
        curr_dir = self.get_document_dir(current_cat, current_doc)
        if curr_dir.exists():
            shutil.rmtree(curr_dir)

        # 3. Restore chosen archive into its ORIGINAL identity
        doc_dir = self.get_document_dir(res_cat, res_doc)
        if doc_dir.exists():
            shutil.rmtree(doc_dir) # Ensure clean slate at target
        
        doc_dir.mkdir(parents=True, exist_ok=True)
        shutil.unpack_archive(str(archive_path), str(doc_dir), 'zip')
        
        return res_cat, res_doc
