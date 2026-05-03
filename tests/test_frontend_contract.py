from pathlib import Path


def test_miniapp_has_expected_entrypoints_and_tabs() -> None:
    app_file = Path("apps/miniapp/src/App.tsx").read_text(encoding="utf-8")
    package_file = Path("apps/miniapp/package.json").read_text(encoding="utf-8")

    for label in ("Сегодня", "Гардероб", "Добавить", "Дизайнер", "Избранное"):
        assert label in app_file or label in Path("apps/miniapp/src/components.tsx").read_text(encoding="utf-8")

    assert '"build": "tsc -b && vite build"' in package_file


def test_miniapp_upload_and_buttons_are_wired_to_actions() -> None:
    app_file = Path("apps/miniapp/src/App.tsx").read_text(encoding="utf-8")
    api_file = Path("apps/miniapp/src/api.ts").read_text(encoding="utf-8")

    for expected in (
        'type="file"',
        "uploadPhoto(file, mode)",
        "getUploadStatus(upload.id)",
        "retryUpload",
        "deleteUpload",
    ):
        assert expected in app_file

    for expected in (
        "onClick={chooseOutfit}",
        "onClick={makeWarmer}",
        "onClick={anotherOutfit}",
        "onChange={setActiveTab}",
    ):
        assert expected in app_file

    assert "/uploads/file" in api_file
    assert "FormData" in api_file


def test_design_tokens_are_mapped_to_css_variables() -> None:
    styles = Path("apps/miniapp/src/styles.css").read_text(encoding="utf-8")

    for token_value in ("#f8f6f1", "#ffffff", "#171717", "#2f7d4a"):
        assert token_value in styles
