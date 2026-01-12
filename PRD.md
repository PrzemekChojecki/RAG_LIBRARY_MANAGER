# PRD – Document Manager (Streamlit) v0.1  
_First step towards Knowledge Base_

---

## 1. Overview

Document Manager to prosty system do:
- organizacji dokumentów w strukturze katalogów,
- ingestu plików (PDF, DOCX),
- konwersji dokumentów do wysokiej jakości Markdown,
- dzielenia dokumentów na chunki przy użyciu wymiennych chunkerów,
- zapisu danych w sposób gotowy do dalszego przetwarzania (RAG, embeddingi).

System działa lokalnie (filesystem) i jest zaprojektowany jako **pipeline danych tekstowych**, a nie tylko UI do uploadu.

---

## 2. Cele Produktowe

### Cele główne
- Zapewnienie **wysokiej jakości Markdown** jako single source of truth
- Zapewnienie **powtarzalności i deterministyczności** przetwarzania
- Stworzenie **rozszerzalnej architektury chunkerów**
- Pełna audytowalność przez metadane

### Poza zakresem (na tym etapie)
- embeddingi
- wyszukiwanie
- wersjonowanie treści
- autoryzacja użytkowników

---

## 3. Struktura Katalogów

### 3.1 Katalogi logiczne

- Katalog główny
- Podkatalogi (1 poziom zagnieżdżenia)

Reguły:
- Dokument należy dokładnie do jednego podkatalogu
- Brak zagnieżdżeń > 1 poziom (na v0.1)

---

### 3.2 Struktura dokumentu

Dla dokumentu `X`:

```

X/
├── original/
│   └── X.pdf | X.docx
├── converted/
│   └── X.md
├── chunked/
│   └── X__<chunker_name>__<chunker_version>.md
└── metadata.json

````

---

## 4. Upload Dokumentów

### 4.1 Obsługiwane formaty
- PDF
- DOCX

### 4.2 Ograniczenia
- Maksymalny rozmiar pliku: **10 MB**
- Maksymalnie **15 dokumentów na podkatalog**

### 4.3 Walidacja
- MIME type
- Rozmiar pliku
- Unikalna nazwa dokumentu w obrębie podkatalogu

Upload kończy się **wyłącznie** zapisem do katalogu `original/`.

---

## 5. Konwersja do Markdown

### 5.1 Trigger
- Konwersja uruchamiana:
  - automatycznie po uploadzie **lub**
  - manualnie (retry / reprocess)

### 5.2 Wymagania jakościowe

Konwersja musi:
- zachować logiczną strukturę dokumentu
- priorytetyzować czytelność nad wierność wizualną
- produkować Markdown nadający się do chunkowania i embeddingów

### 5.3 Czyszczenie treści
- usuwanie:
  - nadmiarowych znaków specjalnych
  - artefaktów OCR
  - powtarzalnych nagłówków / stopek
- normalizacja:
  - nagłówków
  - list
  - odstępów

### 5.4 Tabele
- Zachowanie struktury tabel
- Preferowany format: pipe table
- Spójna liczba kolumn
- Brak łamania wierszy w komórkach

---

## 6. Chunkowanie

### 6.1 Zasady ogólne
- Chunkowanie działa **wyłącznie na Markdown**
- Każdy chunker:
  - jest niezależnym modułem
  - spełnia kontrakt wejścia/wyjścia
  - posiada nazwę i wersję

---

### 6.2 Kontrakt Chunkera

**Input**
```python
markdown_text: str
config: dict
````

**Output**

```python
{
  "chunks": [
    {
      "id": "chunk_001",
      "order": 1,
      "content": "..."
    }
  ],
  "stats": {
    "num_chunks": int
  }
}
```

---

### 6.3 Pliki chunked Markdown

* Jeden plik na dokument + chunker
* Nazwa pliku:

```
<doc_name>__<chunker_name>__<chunker_version>.md
```

**Format treści:**

```md
<!-- chunk_id: chunk_001 -->
Treść chunka

<!-- chunk_id: chunk_002 -->
Treść kolejnego chunka
```

---

## 7. Chunkery v1

### 7.1 Sentence Chunker

**Nazwa:** `sentence_v1`

**Zasada:**

* Podział po liczbie zdań (N)
* Brak dzielenia zdań
* Konfigurowalny parametr:

```json
{
  "sentences_per_chunk": 5
}
```

**Edge cases:**

* bardzo długie zdania → osobny chunk
* puste linie ignorowane

---

### 7.2 Paragraph Chunker

**Nazwa:** `paragraph_v1`

**Zasada podstawowa:**

* Akapit = jednostka bazowa

**Logika łączenia krótkich akapitów:**

* jeśli akapit:

  * < X znaków **lub**
  * zawiera tylko 1 zdanie
* to jest łączony z następnym
* aż do osiągnięcia minimalnej długości

Cel:

* eliminacja chunków niskiej wartości semantycznej

---

## 8. Metadane

### 8.1 metadata.json

Jeden plik na dokument.

```json
{
  "document_id": "uuid",
  "original_filename": "X.pdf",
  "file_size_mb": 2.3,
  "created_at": "ISO-8601",
  "converted_at": "ISO-8601",
  "conversion": {
    "tool": "pdf_to_md",
    "version": "1.0"
  },
  "chunking": [
    {
      "chunker": "sentence_v1",
      "chunker_version": "1.0",
      "variant": {
        "sentences_per_chunk": 5
      },
      "created_at": "ISO-8601",
      "num_chunks": 42
    }
  ]
}
```

---

## 9. UI (Streamlit – zakres minimalny)

### Sidebar

* Drzewo katalogów
* Dodawanie katalogów / podkatalogów

### Main View

* Lista dokumentów
* Upload plików
* Status:

  * uploaded
  * converted
  * chunked
* Wybór chunkera + konfiguracja
* Podgląd Markdown / chunków

---

## 10. Wymagania niefunkcjonalne

* Deterministyczność pipeline
* Idempotencja operacji
* Brak vendor lock-in
* Czysty Python
* Czytelna struktura filesystemu

---

## 11. Kryteria Akceptacji (MVP)

* Można wgrać dokument PDF/DOCX
* Dokument jest poprawnie konwertowany do Markdown
* Markdown jest dzielony przez co najmniej 2 chunkery
* Powstają pliki chunked z poprawnymi znacznikami
* Metadane odzwierciedlają realny stan przetwarzania

---

## 12. Następne iteracje

* embeddingi
* wersjonowanie treści
* wyszukiwanie semantyczne
* adnotacje
* integracja z vector store