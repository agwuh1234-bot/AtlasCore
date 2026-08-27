from pathlib import Path


def test_studio_results_assets_are_loaded_and_functional():
    root = Path(__file__).resolve().parents[1]
    index = (root / "web" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "studio-results.js").read_text(encoding="utf-8")
    css = (root / "web" / "studio-results.css").read_text(encoding="utf-8")

    assert '/app/studio-results.js' in index
    assert '/app/studio-results.css' in index
    for token in (
        'studio-result-card',
        'Копировать',
        'Экспорт .md',
        'Claude review',
        'Продолжить код',
        'Shot list',
        'CRO review',
        'Проверить workflow',
        'atlas_studio_results:',
    ):
        assert token in js
    assert '.studio-result-card' in css
    assert '.studio-results-widget' in css
