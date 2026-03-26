"""Tests for the quality scoring system."""

import pytest
from quality_scorer import QualityScorer, QualityScore


class TestQualityScorer:
    """Test suite for QualityScorer."""

    def test_score_empty_content(self):
        """Test scoring empty content."""
        score = QualityScorer.score("", "article")
        assert score.overall_score == 0.0
        assert score.readability_score == 0.0
        assert score.length_score == 0.0

    def test_score_good_article(self):
        """Test scoring a well-written article."""
        good_article = """
        # Introduction
        This is a comprehensive introduction to AI technology.

        ## Background
        Artificial intelligence has revolutionized many industries. The development started
        decades ago with early machine learning algorithms. Today, we see AI everywhere.

        ## Current Applications
        AI is used in healthcare for diagnosis. It helps in transportation and autonomous vehicles.
        Machine learning powers recommendation systems. Natural language processing enables chatbots.

        ## Future Prospects
        The future looks promising for AI development. We will see more advanced systems.
        However, we must address ethical concerns about privacy and bias.

        ## Conclusion
        Artificial intelligence is transforming our world. Understanding its impact is crucial
        for all stakeholders. We need thoughtful development and deployment of AI systems.
        """

        score = QualityScorer.score(good_article, "article")
        assert score.overall_score > 50  # Should be reasonably good
        assert score.overall_score <= 100
        assert score.length_score > 0
        assert score.structure_score > 0

    def test_score_short_content(self):
        """Test scoring content that's too short."""
        short_content = "This is too short."
        score = QualityScorer.score(short_content, "article")
        # Should have low length score
        assert score.length_score < 50

    def test_score_very_long_content(self):
        """Test scoring content that's too long."""
        very_long = " ".join(["word"] * 5000)
        score = QualityScorer.score(very_long, "article")
        # Should penalize for being too long, but not as harshly as being too short
        assert score.length_score < 100

    def test_score_caption(self):
        """Test scoring a social media caption."""
        caption = "Amazing new feature released today! Check it out and let us know what you think. #tech #innovation"
        score = QualityScorer.score(caption, "caption")
        assert score.overall_score >= 0
        assert score.overall_score <= 100
        # Caption is within word limit
        assert score.length_score > 50

    def test_score_video_script(self):
        """Test scoring a video script."""
        video_script = """
        # Intro (0:00-0:30)
        Hey everyone, welcome to today's video about artificial intelligence.

        # Body (0:30-9:00)
        Let's dive into the fascinating world of AI. First, we'll explore what AI actually is.
        Artificial intelligence refers to computer systems designed to perform tasks that normally
        require human intelligence. This includes learning, reasoning, and problem-solving.

        ## History
        The concept of AI started in the 1950s. Early pioneers like Alan Turing proposed the
        famous Turing test. Over decades, we've seen exponential progress in the field.

        ## Applications
        Today, AI powers many applications. Self-driving cars use AI for navigation. Virtual
        assistants understand our voice commands. Recommendation systems suggest movies we like.

        # Outro (9:00-10:00)
        That wraps up our exploration of AI. Thanks for watching, and don't forget to subscribe!
        """

        score = QualityScorer.score(video_script, "video_script")
        assert score.overall_score > 30  # Should be reasonably good
        assert score.structure_score > 0  # Should have decent structure

    def test_batch_score(self):
        """Test batch scoring multiple results."""
        from content_generator import GenerationResult

        results = {
            "article": GenerationResult(
                success=True,
                content="This is a test article. " * 100,
                content_type="article",
                model="claude",
                metadata={},
                errors=[],
                quality_score=None,
            ),
            "caption": GenerationResult(
                success=True,
                content="Great content!",
                content_type="caption",
                model="gpt",
                metadata={},
                errors=[],
                quality_score=None,
            ),
        }

        batch_result = QualityScorer.batch_score(results)
        assert "scores_by_type" in batch_result
        assert "batch_average_score" in batch_result
        assert "batch_count" in batch_result
        assert batch_result["batch_count"] == 2
        assert batch_result["batch_average_score"] >= 0

    def test_word_count(self):
        """Test word counting."""
        text = "This is a test sentence with ten words in it exactly."
        count = QualityScorer._count_words(text)
        assert count == 11

    def test_sentence_count(self):
        """Test sentence counting."""
        text = "First sentence. Second sentence! Third sentence? Fourth."
        count = QualityScorer._count_sentences(text)
        assert count >= 3  # At least three sentences

    def test_section_count(self):
        """Test section counting from headers."""
        text = """
        # Main Title
        Content here.

        ## Section 1
        More content.

        ## Section 2
        Even more content.

        ### Subsection
        Sub-content.
        """
        count = QualityScorer._count_sections(text)
        assert count >= 3  # Should count at least 3 header sections

    def test_readability_score_extreme_cases(self):
        """Test readability scoring with extreme complexity."""
        # Very simple text
        simple_text = "Cat sat. Dog ran. Bird flew."
        score_simple = QualityScorer._score_readability(simple_text)
        assert score_simple >= 0
        assert score_simple <= 100

        # Very complex text with long words and sentences
        complex_text = """
        The multidimensional implementation of sophisticated computational paradigms
        necessitates comprehensive understanding of intricate algorithmic methodologies.
        Notwithstanding the aforementioned complexities, contemporary advancements
        in machine learning facilitate unprecedented opportunities for optimization.
        """
        score_complex = QualityScorer._score_readability(complex_text)
        assert score_complex >= 0
        assert score_complex <= 100

    def test_length_score_boundaries(self):
        """Test length scoring at boundary conditions."""
        # At minimum
        min_words = " ".join(["word"] * 100)
        score_min = QualityScorer._score_length(
            min_words,
            {"min_words": 100, "max_words": 1000}
        )
        assert score_min == 100.0

        # At maximum
        max_words = " ".join(["word"] * 1000)
        score_max = QualityScorer._score_length(
            max_words,
            {"min_words": 100, "max_words": 1000}
        )
        assert score_max == 100.0

        # Below minimum
        below_min = " ".join(["word"] * 50)
        score_below = QualityScorer._score_length(
            below_min,
            {"min_words": 100, "max_words": 1000}
        )
        assert 0 <= score_below < 100

        # Above maximum
        above_max = " ".join(["word"] * 2000)
        score_above = QualityScorer._score_length(
            above_max,
            {"min_words": 100, "max_words": 1000}
        )
        assert 0 <= score_above < 100

    def test_structure_score_with_sections(self):
        """Test structure scoring with proper sections."""
        structured_text = """
        # Introduction

        ## Section 1
        This introduces the first topic. The analysis is thorough and well-reasoned.

        ## Section 2
        Here we conclude. The information builds logically.
        """
        score = QualityScorer._score_structure(
            structured_text,
            {"expected_sections": 2, "key_phrases": ["introduction", "conclusion"]},
            "article"
        )
        assert score > 0

    def test_quality_score_dataclass(self):
        """Test QualityScore dataclass."""
        score = QualityScore(
            overall_score=75.5,
            readability_score=80.0,
            length_score=70.0,
            structure_score=75.0,
            metadata={"test": "data"},
        )
        assert score.overall_score == 75.5
        assert score.readability_score == 80.0
        assert score.metadata["test"] == "data"

    def test_content_type_expectations_coverage(self):
        """Test that all content types have expectations."""
        expected_types = [
            "video_script",
            "article",
            "caption",
            "hashtags",
            "thumbnail_description",
        ]
        for content_type in expected_types:
            expectations = QualityScorer.CONTENT_TYPE_EXPECTATIONS.get(
                content_type
            )
            assert expectations is not None
            assert "min_words" in expectations
            assert "max_words" in expectations


class TestQualityScorerIntegration:
    """Integration tests with actual generation results."""

    def test_score_realistic_article(self):
        """Test scoring a realistic article."""
        realistic_article = """
        # The Rise of Artificial Intelligence in 2024

        ## Introduction
        Artificial intelligence has become a transformative force in technology and society.
        From healthcare to finance, AI applications are reshaping industries and creating
        new opportunities for innovation and growth.

        ## Current Landscape
        The AI market has grown significantly in recent years. Companies like OpenAI,
        Google, and Meta are investing billions in AI research. The competition is driving
        rapid innovation and breakthroughs in multiple domains.

        ### Healthcare Applications
        In healthcare, AI is being used for disease diagnosis, drug discovery, and patient
        management. Machine learning models can now detect certain cancers better than humans.
        This has profound implications for early treatment and patient outcomes.

        ### Business Applications
        Businesses are using AI for customer service, content creation, and process automation.
        Chatbots handle customer inquiries 24/7. AI systems optimize supply chains and predict
        market trends. The productivity gains are substantial.

        ## Challenges and Concerns
        Despite the benefits, AI raises important questions about privacy, bias, and job
        displacement. We need robust governance frameworks. Ethical considerations are paramount.

        ## Conclusion
        AI is here to stay and will continue evolving. Success depends on responsible development
        and thoughtful deployment. We must balance innovation with caution.
        """

        score = QualityScorer.score(realistic_article, "article")
        # Realistic article should score reasonably well
        assert score.overall_score > 60
        assert score.length_score > 70
        assert score.structure_score > 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
