import json
import socket
import urllib.request

import pytest
from faker import Faker

from pii_strip import nlp
from pii_strip.cli import main
from tests.support.pdf_factory import extract_text, make_hidden_pii_pdf, make_pdf

fake = Faker("da_DK")
Faker.seed(10)


class NetworkAttempt(Exception):
    pass


@pytest.fixture
def no_network(monkeypatch):
    """Block every way of opening a connection or resolving a host name. Each attempt is recorded and raises,
    so the test fails even if a library catches the error and carries on."""
    attempts: list[str] = []

    def blocked(name):
        def refuse(*args, **kwargs):
            attempts.append(f"{name}{args[1:] if name.startswith('socket.') else args}")

            raise NetworkAttempt(f"network access attempted: {name}")

        return refuse

    monkeypatch.setattr(socket.socket, "connect", blocked("socket.connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", blocked("socket.connect_ex"))
    monkeypatch.setattr(socket, "create_connection", blocked("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", blocked("getaddrinfo"))
    monkeypatch.setattr(socket, "gethostbyname", blocked("gethostbyname"))

    # The analyzer is cached across tests; clear it so the models are loaded again while the network is blocked.
    nlp.build_analyzer.cache_clear()

    yield attempts

    nlp.build_analyzer.cache_clear()


def test_the_network_block_catches_a_connection_attempt(no_network):
    with pytest.raises(Exception):
        urllib.request.urlopen("http://example.invalid", timeout=1)

    assert no_network != []


def test_the_full_pipeline_runs_with_the_network_blocked(tmp_path, no_network):
    # Fixed synthetic values: this test is about the network, so its outcome must not depend on which fake name is drawn.
    name, email, place = "Mette Jensen", "mette.jensen@example.com", "Aarhus"
    deny, allow = tmp_path / "deny.txt", tmp_path / "allow.txt"
    deny.write_text("Projekt Solsort\n")
    allow.write_text("Danmarks Radio\n")
    source = make_pdf(tmp_path / "in.pdf", [f"{name} bor i {place}. Skriv til {email} eller ring på 20 12 34 56. Hendes CPR-nummer er 010190-1234.", "Projekt Solsort hos Danmarks Radio."])
    output, report = tmp_path / "out.pdf", tmp_path / "report.json"

    exit_code = main([str(source), "-o", str(output), "--lang", "da,en", "--entities", ",".join(nlp.SUPPORTED_ENTITIES), "--deny", str(deny), "--allow", str(allow), "--report", str(report), "--quiet"])

    assert no_network == []
    assert exit_code == 0
    assert email not in extract_text(output)
    assert "Projekt Solsort" not in extract_text(output)
    assert json.loads(report.read_text())["exit_code"] == 0


def test_hidden_content_is_sanitized_with_the_network_blocked(tmp_path, no_network):
    source = make_hidden_pii_pdf(tmp_path / "hidden.pdf")
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output), "--quiet"])

    assert no_network == []
    assert exit_code == 0


def test_a_missing_model_exits_with_1_without_a_network_attempt(tmp_path, no_network, monkeypatch, capsys):
    monkeypatch.setattr("pii_strip.nlp.spacy.util.is_package", lambda name: False)
    source = make_pdf(tmp_path / "in.pdf", [f"Hej {fake.name()}"])

    exit_code = main([str(source), "-o", str(tmp_path / "out.pdf")])

    assert no_network == []
    assert exit_code == 1
    assert "pip install" in capsys.readouterr().err


def test_a_folder_runs_with_the_network_blocked(tmp_path, no_network):
    make_pdf(tmp_path / "a.pdf", ["Mette Jensen skrev rapporten. Skriv til mette.jensen@example.com."])
    make_hidden_pii_pdf(tmp_path / "b.pdf")

    exit_code = main([str(tmp_path), "--quiet"])

    assert no_network == []
    assert exit_code == 0
    assert all("mette.jensen@example.com" not in extract_text(output) for output in (tmp_path / "processed").glob("*.pdf"))
    assert len(list((tmp_path / "keys").glob("*.md"))) == 2
