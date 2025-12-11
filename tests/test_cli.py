from __future__ import annotations

from pathlib import Path

from ha_export.main import run_export


def test_run_export_generates_expected_files(config_dir, tmp_path) -> None:
    output_dir = tmp_path / "export"
    result = run_export(
        ha_url=None,
        token=None,
        config_dir=str(config_dir),
        output_dir=str(output_dir),
        incremental=True,
        dry_run=False,
        include=["scripts", "scenes", "helpers", "entities"],
        exclude=None,
        verbose=False,
        quiet=True,
    )

    assert result.executed["scripts"] >= 1
    exported_scripts = sorted((output_dir / "scripts").glob("*.yaml"))
    assert exported_scripts, "scripts exporter should write files"

    entities_path = output_dir / "entities" / "entities.yaml"
    assert entities_path.exists()
    content = entities_path.read_text(encoding="utf-8")
    assert "sensor.outdoor_temperature" in content

    metadata_path = output_dir / "metadata.json"
    assert metadata_path.exists()
