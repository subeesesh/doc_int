from pathlib import Path

from app.services.document_processor import DocumentProcessor


def main():
    processor = DocumentProcessor()

    # Temporary test file.
    # Replace this with an actual document path.
    file_path = Path("test_document.pdf")

    result = processor.process_file(str(file_path))

    document = result["document"]

    print("=" * 60)
    print("DOCLING PROCESSING SUCCESSFUL")
    print("=" * 60)

    markdown = document.export_to_markdown()

    print(markdown[:5000])

    print("\n" + "=" * 60)
    print("DOCUMENT TYPE:", type(document).__name__)
    print("MARKDOWN CHARACTERS:", len(markdown))
    print("=" * 60)


if __name__ == "__main__":
    main()