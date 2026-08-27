"""Unit tests for PyFlare CLI commands."""
import pytest
from pyflare.cli import build_parser, main


@pytest.mark.unit
def test_cli_parser_commands():
    """Verify CLI parser registers all required commands."""
    parser = build_parser()
    
    # doctor
    args = parser.parse_args(["doctor"])
    assert args.command == "doctor"
    
    # plan
    args = parser.parse_args(["plan", "Create a castle"])
    assert args.command == "plan"
    assert args.prompt == "Create a castle"
    
    # serve
    args = parser.parse_args(["serve", "--port", "8080"])
    assert args.command == "serve"
    assert args.port == 8080
    assert args.host == "127.0.0.1"


@pytest.mark.unit
def test_cli_doctor_execution():
    """Verify doctor command runs successfully without throwing."""
    exit_code = main(["doctor"])
    assert exit_code == 0
