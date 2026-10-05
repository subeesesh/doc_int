from app.services.chunking import RecursiveChunker


def main():

    text = """
    NovaTech Solutions is a fictional software company.

    Full-time employees receive 20 days of annual leave per
    calendar year.

    Employees may work remotely for up to three days per week
    with manager approval.

    Employees receive an annual learning budget of INR 25,000.
    """

    chunker = RecursiveChunker(
        chunk_size=200,
        chunk_overlap=40,
    )

    chunks = chunker.split_text(text)

    print("=" * 60)
    print("CHUNKING TEST")
    print("=" * 60)

    for i, chunk in enumerate(chunks):
        print(f"\n--- CHUNK {i} ---")
        print(chunk)

    print("\nTotal chunks:", len(chunks))


if __name__ == "__main__":
    main()