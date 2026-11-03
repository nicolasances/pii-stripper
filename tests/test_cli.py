from faker import Faker

from pii_strip.cli import main
from tests.support.pdf_factory import extract_text, make_pdf

fake = Faker("da_DK")
Faker.seed(99)


def test_cli_redacts_the_input_into_the_output_file(tmp_path, capsys):
    email = fake.email()
    source = make_pdf(tmp_path / "in.pdf", [f"Write to {email} please"])
    output = tmp_path / "out.pdf"

    exit_code = main([str(source), "-o", str(output)])

    assert exit_code == 0
    assert email not in extract_text(output)
