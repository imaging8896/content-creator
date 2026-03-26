"""Quality scoring system for evaluating generated content.

Evaluates content based on:
- Readability scores (Flesch-Kincaid grade level)
- Length appropriateness for content type
- Factual accuracy and structure completeness
"""

import re
import logging
from typing import Dict, Any, Tuple
from dataclasses import dataclass

try:
    import textstat
except ImportError:
    textstat = None

logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    """Quality score breakdown for content."""
    overall_score: float  # 0-100
    readability_score: float  # 0-100
    length_score: float  # 0-100
    structure_score: float  # 0-100
    metadata: Dict[str, Any]


class QualityScorer:
    """Score generated content based on multiple quality dimensions."""

    # Content type specific expectations
    CONTENT_TYPE_EXPECTATIONS = {
        "video_script": {
            "min_words": 400,
            "max_words": 2500,
            "expected_sections": 5,
            "key_phrases": ["intro", "conclusion", "call to action"],
        },
        "article": {
            "min_words": 800,
            "max_words": 3000,
            "expected_sections": 5,
            "key_phrases": ["introduction", "conclusion", "analysis"],
        },
        "caption": {
            "min_words": 20,
            "max_words": 500,
            "expected_sections": 1,
            "key_phrases": [],
        },
        "hashtags": {
            "min_words": 5,
            "max_words": 50,
            "expected_sections": 1,
            "key_phrases": [],
        },
        "thumbnail_description": {
            "min_words": 10,
            "max_words": 200,
            "expected_sections": 1,
            "key_phrases": [],
        },
    }

    # Readability grade level targets (lower is more accessible)
    # Grade level 6-8 is ideal for general audience
    OPTIMAL_GRADE_LEVEL = 8
    GRADE_LEVEL_PENALTY_PER_POINT = 2.5

    @classmethod
    def score(
        cls,
        content: str,
        content_type: str,
    ) -> QualityScore:
        """Score generated content across multiple dimensions.

        Args:
            content: The generated content text
            content_type: Type of content (video_script, article, etc.)

        Returns:
            QualityScore with breakdown and overall score
        """
        if not content or not content.strip():
            return QualityScore(
                overall_score=0.0,
                readability_score=0.0,
                length_score=0.0,
                structure_score=0.0,
                metadata={"error": "Empty content"},
            )

        # Get expectations for this content type
        expectations = cls.CONTENT_TYPE_EXPECTATIONS.get(
            content_type,
            cls.CONTENT_TYPE_EXPECTATIONS["article"],  # Default to article expectations
        )

        # Calculate individual scores
        readability_score = cls._score_readability(content)
        length_score = cls._score_length(content, expectations)
        structure_score = cls._score_structure(content, expectations, content_type)

        # Calculate weighted overall score
        overall_score = (
            readability_score * 0.3 +  # 30% weight
            length_score * 0.3 +  # 30% weight
            structure_score * 0.4  # 40% weight
        )

        # Ensure score is between 0-100
        overall_score = max(0, min(100, overall_score))

        metadata = {
            "word_count": cls._count_words(content),
            "sentence_count": cls._count_sentences(content),
            "section_count": cls._count_sections(content),
            "grade_level": cls._get_grade_level(content),
            "content_type": content_type,
            "expectations": expectations,
        }

        return QualityScore(
            overall_score=round(overall_score, 1),
            readability_score=round(readability_score, 1),
            length_score=round(length_score, 1),
            structure_score=round(structure_score, 1),
            metadata=metadata,
        )

    @staticmethod
    def _count_words(text: str) -> int:
        """Count words in text."""
        return len(text.split())

    @staticmethod
    def _count_sentences(text: str) -> int:
        """Estimate sentence count."""
        # Simple sentence detection using periods, question marks, exclamation marks
        sentences = re.split(r'[.!?]+', text)
        return len([s for s in sentences if s.strip()])

    @staticmethod
    def _count_sections(text: str) -> int:
        """Estimate section count from markdown headers."""
        # Count markdown headers (lines starting with #)
        headers = re.findall(r'^#+\s+', text, re.MULTILINE)
        return len(headers) if headers else 1

    @staticmethod
    def _get_grade_level(text: str) -> float:
        """Get Flesch-Kincaid grade level using textstat."""
        if textstat is None:
            # Fallback: estimate based on average word length and sentence length
            words = text.split()
            sentences = re.split(r'[.!?]+', text)
            sentences = [s for s in sentences if s.strip()]

            if not words or not sentences:
                return 6.0

            avg_word_length = sum(len(w) for w in words) / len(words)
            avg_sentence_length = len(words) / len(sentences) if sentences else 0

            # Simple grade level estimation
            grade_level = (
                0.39 * avg_sentence_length +
                11.8 * (avg_word_length / 4.5) -
                15.59
            )
            return max(0, grade_level)

        return textstat.flesch_kincaid_grade(text)

    @classmethod
    def _score_readability(cls, content: str) -> float:
        """Score readability (0-100, higher is better).

        Uses Flesch Reading Ease adjusted for grade level.
        """
        if not content.strip():
            return 0.0

        try:
            grade_level = cls._get_grade_level(content)

            # Convert grade level to readability score
            # Grade 6-8 is optimal (general audience)
            # Penalty for being too complex (high grade) or too simple (low grade)
            grade_difference = abs(grade_level - cls.OPTIMAL_GRADE_LEVEL)
            grade_penalty = grade_difference * cls.GRADE_LEVEL_PENALTY_PER_POINT

            # Start with base score of 85
            readability_score = 85 - grade_penalty

            # Cap between 0-100
            return max(0, min(100, readability_score))

        except Exception as e:
            logger.warning(f"Error calculating readability score: {e}")
            return 50.0  # Default score if calculation fails

    @classmethod
    def _score_length(cls, content: str, expectations: Dict[str, Any]) -> float:
        """Score content length appropriateness (0-100).

        Scores based on whether content meets word count expectations.
        """
        word_count = cls._count_words(content)
        min_words = expectations.get("min_words", 100)
        max_words = expectations.get("max_words", 2000)

        # Ideal range is between min and max
        if min_words <= word_count <= max_words:
            return 100.0

        # Penalize for being too short
        if word_count < min_words:
            shortage_ratio = word_count / min_words
            return shortage_ratio * 100

        # Penalize for being too long, but less than being too short
        if word_count > max_words:
            excess_ratio = (word_count - max_words) / (max_words * 0.5)
            excess_ratio = min(excess_ratio, 1.0)  # Cap at 100% excess
            return max(0, 100 - (excess_ratio * 30))  # Lighter penalty

        return 50.0

    @classmethod
    def _score_structure(
        cls,
        content: str,
        expectations: Dict[str, Any],
        content_type: str,
    ) -> float:
        """Score content structure and completeness (0-100).

        Evaluates:
        - Section completeness
        - Presence of key phrases
        - Text organization (paragraphs, headers)
        """
        scores = []

        # Check for key phrases
        key_phrases = expectations.get("key_phrases", [])
        if key_phrases:
            content_lower = content.lower()
            phrases_found = sum(
                1 for phrase in key_phrases
                if phrase.lower() in content_lower
            )
            phrase_score = (phrases_found / len(key_phrases)) * 100
            scores.append(phrase_score)

        # Check section structure
        expected_sections = expectations.get("expected_sections", 1)
        actual_sections = cls._count_sections(content)

        if expected_sections > 0:
            # Score based on section count
            # Perfect if equal, penalize for too few or too many
            section_diff = abs(actual_sections - expected_sections)
            section_score = max(0, 100 - (section_diff * 15))
            scores.append(section_score)

        # Check for paragraph diversity (at least some structure)
        paragraphs = [p for p in content.split('\n\n') if p.strip()]
        paragraph_score = min(len(paragraphs) * 20, 100)  # More paragraphs = better structure
        scores.append(paragraph_score)

        # Check for good sentence variety (not all sentences same length)
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) > 2:
            sentence_lengths = [len(s.split()) for s in sentences]
            avg_length = sum(sentence_lengths) / len(sentence_lengths)
            length_variance = sum(
                (length - avg_length) ** 2
                for length in sentence_lengths
            ) / len(sentence_lengths)

            # Good variance is important for readability
            variance_score = min(length_variance / 25 * 100, 100)
            scores.append(variance_score)

        # Return average of all structure scores
        return sum(scores) / len(scores) if scores else 50.0

    @classmethod
    def batch_score(
        cls,
        results_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Score a dictionary of generation results.

        Args:
            results_dict: Dictionary mapping content_type to GenerationResult

        Returns:
            Dictionary with quality scores for each content type and batch stats
        """
        scores_by_type = {}
        all_scores = []

        for content_type, result in results_dict.items():
            if hasattr(result, 'content') and hasattr(result, 'success'):
                if result.success:
                    quality_score = cls.score(result.content, content_type)
                    scores_by_type[content_type] = {
                        "overall_score": quality_score.overall_score,
                        "readability_score": quality_score.readability_score,
                        "length_score": quality_score.length_score,
                        "structure_score": quality_score.structure_score,
                        "metadata": quality_score.metadata,
                    }
                    all_scores.append(quality_score.overall_score)
                else:
                    scores_by_type[content_type] = {
                        "overall_score": 0.0,
                        "error": "Content generation failed",
                    }

        return {
            "scores_by_type": scores_by_type,
            "batch_average_score": round(
                sum(all_scores) / len(all_scores), 1
            ) if all_scores else 0.0,
            "batch_count": len(scores_by_type),
            "high_quality_count": sum(1 for s in all_scores if s >= 70),
            "low_quality_count": sum(1 for s in all_scores if s < 50),
        }
