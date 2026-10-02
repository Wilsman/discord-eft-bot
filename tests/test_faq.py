from __future__ import annotations

import pytest

from nerdbot.circle import faq

QUESTIONS = {
    "what do i need for 6h": "thresholds",
    "how much value for the 6 hour ritual?": "thresholds",
    "does going over 400k increase the chance": "thresholds",
    "what are the odds at 400k": "thresholds",
    "how is base value calculated": "base-value",
    "whats the formula for base value": "base-value",
    "why is my gun worth so much in the circle": "weapon-base-values",
    "why are weapons hidden by default": "weapons-hidden",
    "what does 14h give": "durations",
    "how do ritual timers work": "durations",
    "what are hot sacrifices": "hot-sacrifices",
    "why is the price red": "red-price",
    "does this work on pve": "game-modes",
    "is there a discord": "discord",
    "how do i pin items": "how-to-use",
    "how do i use the calculator": "how-to-use",
    "will ledx ever come back from a 6h": "6h-exclusions",
    "any tips to save money": "optimization",
    "what do figurines give": "recipes",
    "why cant i use some items": "incompatible",
    "item hints?": "item-hints",
    "can i share my setup": "share",
}


@pytest.mark.parametrize(("question", "expected"), sorted(QUESTIONS.items()))
def test_questions_route_to_the_right_answer(question, expected):
    answer = faq.ask(question)
    assert answer.entry is not None, f"no answer for {question!r} (score {answer.score:.1f})"
    assert answer.entry.id == expected, (
        f"{question!r} -> {answer.entry.id} ({answer.score:.1f}); "
        f"top: {[(e.id, round(s)) for e, s in faq.score_entries(question)[:3]]}"
    )


@pytest.mark.parametrize("question", ["what is the weather", "lol", "who won the football"])
def test_unrelated_questions_get_no_confident_answer(question):
    assert faq.ask(question).entry is None


def test_sacrifice_subject_extraction():
    assert faq.sacrifice_subject("can I sacrifice a Pilgrim backpack?") == "Pilgrim backpack"
    assert faq.sacrifice_subject("could we put roubles in the circle") == "roubles"
    assert faq.sacrifice_subject("what is base value") is None


def test_incompatible_lookup():
    assert faq.incompatible_match("pilgrim") == "Pilgrim"
    assert faq.incompatible_match("GP coin") == "GP coin"
    assert faq.incompatible_match("Graphics card") is None


def test_six_hour_exclusions():
    assert faq.six_hour_excluded("LEDX Skin Transilluminator") == "LEDX Skin Transilluminator"
    assert faq.six_hour_excluded("Bottle of Fierce Hatchling moonshine") is None
    assert faq.six_hour_mentioned("can a 6h give me a ledx?") == "LEDX Skin Transilluminator"
    assert faq.six_hour_mentioned("will the gps amplifier come from 6h") == "Far-forward GPS Signal Amplifier Unit"
    assert faq.six_hour_mentioned("what does the current 6h give") is None
    assert faq.mentions_six_hour_reward("can a 6h give me a ledx?")
