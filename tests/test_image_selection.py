import pytest
from aiwardrobe_core.schemas import UploadSelectionPayload
from pydantic import ValidationError


def test_rectangle_selection_accepts_normalized_bounds() -> None:
    selection = UploadSelectionPayload(
        kind="rectangle",
        source="user",
        x=0.2,
        y=0.1,
        width=0.6,
        height=0.8,
    )

    assert selection.x + selection.width == pytest.approx(0.8)
    assert selection.y + selection.height == pytest.approx(0.9)


@pytest.mark.parametrize(
    ("x", "y", "width", "height"),
    [
        (0.8, 0.1, 0.3, 0.5),
        (0.1, 0.8, 0.5, 0.3),
        (-0.1, 0.1, 0.5, 0.5),
        (0.1, 0.1, 0.0, 0.5),
    ],
)
def test_rectangle_selection_rejects_out_of_bounds_geometry(
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    with pytest.raises(ValidationError):
        UploadSelectionPayload(
            kind="rectangle",
            source="user",
            x=x,
            y=y,
            width=width,
            height=height,
        )
