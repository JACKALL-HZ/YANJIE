import pytest

from app.services.input_intent import classify_input


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("怎么才能盈利？", "question"),
        ("好吧", "casual"),
        ("我再想想", "casual"),
        ("请明星代言", "business_decision"),
        ("说得更激进一点", "clarify"),
    ],
)
def test_classify_input(text: str, kind: str):
    assert classify_input(text).kind == kind


def test_blank_input_is_rejected():
    with pytest.raises(ValueError, match="请输入具体问题或经营决策"):
        classify_input("  ")


def test_declared_catalogue_keyword_is_a_business_decision():
    intent = classify_input("跟其他奶茶店联名", known_decision_keywords=("联名",))

    assert intent.kind == "business_decision"
