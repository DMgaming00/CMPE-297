# Security Policy

This is an educational project. Don't deploy it with real customer data without an
independent review.

## Reporting a vulnerability
Please report suspected vulnerabilities privately to the repository owner. Use GitHub's
private vulnerability reporting ("Security" tab → "Report a vulnerability") if it is
enabled, rather than opening a public issue. Include reproduction steps and the
affected agent.

## Secrets
* Never commit `.env`, service-account keys or tokens. `.gitignore` excludes them.
* `.env.example` contains placeholders only.
* Production database credentials and Toolbox configs belong in Secret Manager.

## Deliberately vulnerable code
`data/demo/code_review/vulnerable_app.py` and `buggy_inventory.py` contain **intentional**
vulnerabilities and bugs. They are test fixtures for the Code Review Assistant and must
never be imported, executed or deployed.

The threat model and red-team results are in [docs/SECURITY.md](docs/SECURITY.md).
