# IBM-Workshop

Prototype of a Preferential Bidding System (PBS) schedule optimizer for airline flight attendants: a FastAPI + DataStax Astra DB backend with an OR-Tools CP-SAT ranking engine and pdfplumber bid-sheet parsing, plus a React/Vite frontend with Playwright e2e tests.
Scheduling and pay rules follow the 2024 AA/APFA collective bargaining agreement; see `requirements.md` and `design.md` for the full spec, and `backend/tests/` for the CBA rule and optimizer property tests.
