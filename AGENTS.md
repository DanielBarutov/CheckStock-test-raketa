# CheckStock

## Scope

- Implement the CheckStock warehouse prototype for one store. Include warehouse management, receipts, inter-warehouse transfers, FBS reservations and shipments, FBO shipments and receipt, balances, and operation history.
- Read [the implementation plan](plans/IMPLEMENTATION.md) for delivery order, [the architecture](plans/ARCHITECTURE.md) for layer boundaries, and [the PostgreSQL design](plans/POSTGRESQL.md) before editing persistence or inventory operations.
- Consult the original requirements and acceptance scenarios in local `docs/` when available. Use `tests/fixtures/demo_inventory.json` for demo data.
- Keep each implementation plan in its own folder under `plans/`. Aim for 200 handwritten changed lines and split plans that would exceed 300. The owner commits each completed plan.

## Architecture and Python

- Put code in `src/{presentation,application,domain,infrastructure}`. Assemble dependencies in `src/main.py`.
- Keep warehouse rules in domain, use-case orchestration and ports in application, HTTP and templates in presentation, and SQL and adapters in infrastructure. Domain depends on the standard library. Application depends inward on domain and its own ports.
- Declare ports with `typing.Protocol`. Adapters satisfy them structurally.
- Import modules and qualify references. For example, use `import typing` with `typing.Protocol` and `import domain.inventory` with `domain.inventory.Balance`. Use implicit namespace packages so fresh checkouts work without ignored `__init__.py` files.
- Use integer quantities. If money enters scope, use `decimal.Decimal` and PostgreSQL `numeric` with an explicit scale and rounding rule.
- Use one PostgreSQL database. Keep read queries and write use cases explicit within the same application.

## Data integrity and tests

- Apply each successful mutation, audit entry, and idempotency receipt in a single transaction. Follow the locking order and state transitions in the PostgreSQL design.
- Preserve balances and warehouse identifiers when archiving warehouses. Include archived stock and open operations in relevant views.
- Test every use case and its failure paths. Use real PostgreSQL for migrations, transaction boundaries, idempotency, and concurrent mutations.
- Enforce at least 95% combined line and branch coverage across `src` with `pytest-cov`. Once test tooling is configured, run `uv run pytest --cov=src --cov-branch --cov-fail-under=95` before declaring implementation complete.
- Keep local specifications, Graphify output, caches, and credentials outside version control.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
