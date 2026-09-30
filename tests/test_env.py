from pathlib import Path

from zendt.utils.env import get_env_var, load_env


def test_load_env_reads_dotenv_without_overriding(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('ZENDT_KEEP', 'already')
    monkeypatch.delenv('ZENDT_FROM_FILE', raising=False)
    (tmp_path / '.env').write_text(
        'ZENDT_KEEP=from-file\nZENDT_FROM_FILE=secret\n',
        encoding='utf-8',
    )

    load_env()

    assert get_env_var('ZENDT_KEEP') == 'already'
    assert get_env_var('ZENDT_FROM_FILE') == 'secret'
    assert get_env_var('ZENDT_MISSING') is None


def test_load_env_missing_file_is_a_no_op(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('GH_TOKEN', raising=False)
    load_env()
    assert get_env_var('GH_TOKEN') is None
