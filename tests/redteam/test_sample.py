from pathlib import Path

import yaml

from redteam.sample import HEADER, main, sample


def _attack(plugin: str, strategy: str, language: str, prompt: str) -> dict:
    meta = {"pluginId": plugin, "strategyId": strategy, "language": language}
    return {"vars": {"prompt": prompt}, "metadata": meta}


def test_keeps_the_first_attack_of_each_triple_in_order() -> None:
    attacks = [
        _attack("pii", "base64", "French", "a"),
        _attack("pii", "base64", "French", "b"),
        _attack("pii", "base64", "English", "c"),
        _attack("pii", "rot13", "French", "d"),
        _attack("hijack", "base64", "French", "e"),
    ]
    assert [a["vars"]["prompt"] for a in sample(attacks)] == ["a", "c", "d", "e"]


def test_main_writes_a_reloadable_file(tmp_path: Path) -> None:
    source, target = tmp_path / "in.yaml", tmp_path / "out.yaml"
    attacks = [_attack("pii", "base64", "French", "é"), _attack("pii", "base64", "French", "x")]
    source.write_text(yaml.safe_dump(attacks, allow_unicode=True), encoding="utf-8")
    assert main([str(source), str(target)]) == 0
    text = target.read_text(encoding="utf-8")
    assert text.startswith(HEADER)
    assert yaml.safe_load(text) == attacks[:1]
