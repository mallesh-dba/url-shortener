# Brownfield Validation Evidence

- Manual alias creation returned 201 with the requested alias as `code`.
- Manual redirect returned 302 and the expected destination in `Location`.
- Uppercase, reserved `api`, and trailing-hyphen aliases returned 422.
- Request without `custom_alias` still generated a Base62 code.
- Corrected duplicate request via `Invoke-RestMethod` returned 409. An earlier
  `curl.exe` attempt returned 422 because its body was malformed JSON; it did
  not test duplicate handling.
- Focused tests:
  `python -m pytest -q tests\test_link_creation.py tests\test_redirects.py`
  — **42 passed**.
- Current regular suite: `python -m pytest -q` — **102 passed, 2 skipped** (opt-in
  integration tests).
- User-run live integration suite with PostgreSQL/Redis:
  `URL_SHORTENER_RUN_INTEGRATION=1 python -m pytest -q tests\test_service_integration.py`
  — **2 passed**, including alias persistence, duplicate conflict, and redirect.
- No migration was needed. Q-6/Q-7 are independent and remain unaccepted.
