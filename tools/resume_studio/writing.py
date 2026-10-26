"""Limited writing diagnostics; not an STE validator or AI authorship detector."""
import re
from collections import Counter


WRITING_GUIDE = """## Plain-language writing target

Write about 80% of the way toward ASD-STE100: apply its useful plain-language
principles with resume-specific exceptions. This is a practical writing goal,
not a claim of formal compliance or a measured percentage of the standard.

- Use short, direct sentences. Aim for 15–20 words; review sentences over 25.
- Express one main idea per sentence. Prefer active verbs and clear ownership.
- Use familiar words: use, build, lead, test, improve. Remove empty modifiers,
  promotional claims, stock openings, and repeated claims.
- Keep terminology consistent. Preserve accurate JD keywords, technical names,
  acronyms, historical titles, and product names. Explain an acronym when useful.
- State concrete scope, actions, and supported results. Never invent a metric
  or strengthen a claim just to make the sentence sound more impressive.
- Preserve meaning and readable grammar. Do not cut necessary words or replace
  precise technical terms just to meet a word limit or dictionary restriction.
- Allow normal resume fragments and implied first-person subjects in bullets.
  Keep the original tense where accurate. Do not force maintenance-instruction
  grammar, a restricted general vocabulary, or unnatural wording onto a resume.

Read writing-review.json for local cues. A flag calls for judgment, not an
automatic replacement. The checker does not implement the STE dictionary,
official word-count rules, full grammar rules, or AI-origin detection.
"""

STYLE_CUES = {
    "results-driven": "Show the actual result instead of this label.",
    "results driven": "Show the actual result instead of this label.",
    "dynamic professional": "State the role and relevant scope.",
    "seasoned professional": "State the relevant experience.",
    "proven track record": "Give a specific supported example.",
    "passionate about": "Use the space for relevant evidence.",
    "cutting-edge": "Name the technology or concrete change.",
    "game-changing": "State the supported outcome.",
    "synergy": "Name what the teams or systems did together.",
    "seamlessly": "Describe the actual operational result, if supported.",
    "leveraged": "Consider 'used' or a more specific action verb.",
    "utilized": "Consider 'used'.",
    "spearheaded": "Consider 'led' and make the scope explicit.",
    "world-class": "Replace the rating with evidence, if available.",
}


def writing_review(profile):
    """Report inspectable cues on prose only; never mutate the resume."""
    prose = [(f"summary:{i + 1}", text) for i, text in enumerate(profile.get("summary", []))]
    prose += [(b["id"], b["text"]) for r in profile["experience"] for b in r["bullets"]]
    prose += [(f"projects:{i + 1}", text) for i, text in enumerate(profile.get("projects", []))]
    findings = []
    sentence_counts = []
    openings = Counter()
    for ref, text in prose:
        # Approximate only: decimal points, acronyms and technical tokens can
        # differ from formal STE counting. No compliance claim is made.
        sentences = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip()) if s]
        for sentence in sentences:
            count = len(sentence.split())
            sentence_counts.append(count)
            if count > 25:
                findings.append({"id": ref, "kind": "long_sentence", "text": sentence,
                                 "word_count": count, "suggestion": "Split at a natural boundary; preserve the facts."})
        for phrase, suggestion in STYLE_CUES.items():
            if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.I):
                findings.append({"id": ref, "kind": "formulaic_wording", "text": phrase,
                                 "suggestion": suggestion})
        passive = re.search(r"\b(?:was|were|is|are|been|being)\s+(?:\w+ly\s+)?\w+ed\b", text, re.I)
        if passive:
            findings.append({"id": ref, "kind": "possible_passive", "text": passive.group(),
                             "suggestion": "Check whether an active verb would clarify ownership; do not change the actor."})
        if not ref.startswith(("summary:", "projects:")):
            words = re.findall(r"\b[\w'-]+\b", text)
            if words:
                openings[words[0].lower()] += 1
    return {"policy": "ASD-STE100-inspired resume writing; approximate 80% intent, not certified compliance",
            "scope": "Summary, work bullets, and projects only; approximate whitespace word counts",
            "limitations": "Heuristic cues only. No STE dictionary validation, semantic review, or AI-authorship detection. Absence of flags is not a quality pass.",
            "sentence_count": len(sentence_counts),
            "sentences_over_25_words": sum(n > 25 for n in sentence_counts),
            "longest_sentence_words": max(sentence_counts, default=0),
            "repeated_bullet_openings": {word: count for word, count in openings.items() if count >= 3},
            "findings": findings,
            "independent_review_status": "pending",
            "success_probability": None,
            "success_probability_note": "Not estimable without a defined outcome and relevant, calibrated outcome data."}


def writing_summary(review):
    lines = ["", "## Writing review", "",
             "Target: approximately 80% of the way toward ASD-STE100 principles, adapted for resumes.",
             "This is not a formal STE compliance score or an AI detector.", "",
             f"- {review['sentences_over_25_words']} of {review['sentence_count']} prose sentences exceed the approximate 25-word guide.",
             f"- {len(review['findings'])} style cues need review. No flags does not mean the writing passes.",
             "- Independent quality scores: pending. Ask a subagent to follow reviewer-prompt.md.",
             "- Hiring-success probability: not estimable from resume text alone."]
    for finding in review["findings"]:
        lines.append(f"- {finding['id']} / {finding['kind']}: {finding['suggestion']}")
    for word, count in review["repeated_bullet_openings"].items():
        lines.append(f"- {count} bullets start with '{word}'. Check repetition; do not force decorative synonyms.")
    return "\n".join(lines) + "\n"
