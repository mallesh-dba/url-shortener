# Greenfield Validation Evidence

Validation is split between the scenario-processing workflow and the service
implementation. A passing regular suite does not establish Q-6/Q-7.

- Requirement processor: `python -m pytest -q tests\test_requirement_processor.py`
  passed **9 tests** after the non-object JSON validation case was added.
- Current regular suite: `python -m pytest -q` — **102 passed,
  2 skipped** (opt-in PostgreSQL/Redis integration tests).
- User-run integration command:
  `URL_SHORTENER_RUN_INTEGRATION=1 python -m pytest -q tests\test_service_integration.py`
  — **2 passed** against PostgreSQL and Redis.
- Local recorded capacity runs missed Q-6/Q-7; performance acceptance remains
  unverified/not accepted. Analytics persistence-versus-acknowledgement
  discrepancy remains open.
- CLI-generated JSON is not evidence of a live model call; see
  [the CLI evidence note](../README.md).
