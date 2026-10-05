from __future__ import annotations

import re


class RecursiveChunker:
    """
    Basic recursive text chunker.

    Designed as the first chunking strategy.
    More advanced strategies can be added later:
    semantic, parent-child, table-aware, etc.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size"
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str) -> list[str]:
        return self.split_text(text)

    def split_text(self, text: str) -> list[str]:
        text = self._clean_text(text)

        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        separators = [
            "\n\n",
            "\n",
            ". ",
            " ",
        ]

        chunks = self._recursive_split(
            text,
            separators,
        )

        return self._add_overlap(chunks)

    @staticmethod
    def _clean_text(text: str) -> str:
        text = text.replace("\r\n", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _recursive_split(
        self,
        text: str,
        separators: list[str],
    ) -> list[str]:

        if len(text) <= self.chunk_size:
            return [text]

        if not separators:
            return [
                text[i:i + self.chunk_size]
                for i in range(
                    0,
                    len(text),
                    self.chunk_size,
                )
            ]

        separator = separators[0]

        parts = text.split(separator)

        chunks = []
        current = ""

        for part in parts:

            candidate = (
                part
                if not current
                else current + separator + part
            )

            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)

                if len(part) > self.chunk_size:
                    chunks.extend(
                        self._recursive_split(
                            part,
                            separators[1:],
                        )
                    )
                    current = ""
                else:
                    current = part

        if current:
            chunks.append(current)

        return chunks

    def _add_overlap(
        self,
        chunks: list[str],
    ) -> list[str]:

        if not chunks:
            return []

        result = [chunks[0]]

        for i in range(1, len(chunks)):

            previous = result[-1]

            overlap = previous[
                max(0, len(previous) - self.chunk_overlap):
            ]

            combined = overlap + "\n" + chunks[i]

            if len(combined) > self.chunk_size:
                combined = chunks[i]

            result.append(combined)

        return result