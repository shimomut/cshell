.PHONY: run install clean venv

run:
	.venv/bin/python3 main.py

install:
	.venv/bin/pip install cmd2 boto3 pexpect

venv:
	python3.14 -m venv .venv
	.venv/bin/pip install cmd2 boto3 pexpect

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
