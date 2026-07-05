from aiwardrobe_core.llm_gateway import GarmentAnalysis, extract_json_object


def test_extract_json_object_strips_markdown_fences() -> None:
    content = '```json\n{"a": 1}\n```'
    assert extract_json_object(content) == '{"a": 1}'


def test_extract_json_object_returns_original_without_braces() -> None:
    assert extract_json_object("no json here") == "no json here"


def test_garment_analysis_accepts_scalar_season_and_percent_confidence() -> None:
    analysis = GarmentAnalysis.model_validate(
        {
            "image_type": "item",
            "title": "Синяя футболка",
            "category": "top",
            "description": "Хлопковая футболка.",
            "season": "summer",
            "main_color": "blue",
            "brand": "Adidas",
            "model_name": "Samba OG",
            "visual_identifiers": ["три полоски", "низкий силуэт"],
            "style_archetype": "casual",
            "designer_attributes": {"fit": "regular"},
            "confidence": 87,
            "designer_reasoning": "Базовая вещь.",
        }
    )

    assert analysis.season == ["summer"]
    assert analysis.style_archetype == ["casual"]
    assert analysis.confidence == 0.87
    assert analysis.brand == "Adidas"
    assert analysis.model_name == "Samba OG"


def test_garment_analysis_keeps_fraction_confidence() -> None:
    analysis = GarmentAnalysis.model_validate(
        {
            "image_type": "item",
            "title": "Jeans",
            "category": "bottom",
            "description": "Denim.",
            "season": ["all_season"],
            "main_color": "indigo",
            "style_archetype": ["casual"],
            "designer_attributes": {},
            "confidence": 0.95,
            "designer_reasoning": "Versatile.",
        }
    )

    assert analysis.confidence == 0.95
