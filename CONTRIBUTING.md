# Contributing to CS2 Arbitrage Scanner

Thank you for your interest in contributing!

## Code Guidelines

1. **Zero Mock / Fake Data**: All scanner integrations must adhere strictly to verified, live API endpoints. Never fabricate placeholder numbers.
2. **Strict Matching**: Always respect item variants (`StatTrak™`, `Souvenir`, and wear conditions).
3. **Resilient HTTP**: Route external requests through the centralized rate-limited HTTP client.
4. **Automated Testing**: Any new features or calculations must include pytest tests in `tests/`.

## Development Workflow

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/my-feature`).
3. Install development dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run tests:
   ```bash
   pytest -v
   ```
5. Commit your changes with clear messages (`git commit -m "Add feature X"`).
6. Push to your branch and open a Pull Request.
