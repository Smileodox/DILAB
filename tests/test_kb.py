from src.pipeline.kb import chunk_text


class TestChunkText:
    def test_packs_short_paragraphs_into_one_chunk(self):
        text = "\n\n".join([f"This is paragraph number {i} with enough length to keep." for i in range(3)])
        chunks = chunk_text(text, max_chunk=1000, min_chunk=10)
        assert len(chunks) == 1
        assert "paragraph number 0" in chunks[0] and "paragraph number 2" in chunks[0]

    def test_splits_when_exceeding_max_chunk(self):
        para = "word " * 40  # ~200 chars, well over a tiny max_chunk
        text = "\n\n".join([para.strip()] * 4)
        chunks = chunk_text(text, max_chunk=210, min_chunk=10)
        assert len(chunks) == 4  # each paragraph lands in its own chunk

    def test_skips_tiny_paragraphs(self):
        text = "12\n\n" + ("A real paragraph that is clearly long enough to be kept as content. " * 2)
        chunks = chunk_text(text, max_chunk=1000, min_chunk=10)
        assert all("12" != c.strip() for c in chunks)
        assert len(chunks) == 1

    def test_drops_trailing_buffer_below_min_chunk(self):
        # one long paragraph (kept) then a short tail that must be flushed but is < min_chunk
        long_para = "content " * 30
        chunks = chunk_text(long_para.strip() + "\n\n" + "tiny tail here now", max_chunk=120, min_chunk=80)
        assert chunks and all(len(c) >= 80 for c in chunks)

    def test_empty_text_yields_no_chunks(self):
        assert chunk_text("   \n\n  \n\n ") == []
