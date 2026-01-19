# Retrofitting a REST App for MCP + Chat UI

This walkthrough assumes you already understand REST, have MCP context, and build enterprise software for a living.

The goal is to highlight three things:
1. The starting point is a standard enterprise IT application (DB + service layer + REST controller + auth).
2. It can be retrofitted — cleanly and quickly — to support MCP tools.
3. Adding a chat UI makes the overall system *more capable* than the original REST UI, because it enables tool orchestration,
   intent-driven flows, and composable operations.

## Table of Contents

1. [Background and Scope](#background-and-scope)
2. [Baseline: A Standard Enterprise REST App](#baseline-a-standard-enterprise-rest-app)
3. [Retrofitting: Adding an MCP Surface Area](#retrofitting-adding-an-mcp-surface-area)
4. [Making It Useful: Chat UI + Tool Orchestration](#making-it-useful-chat-ui--tool-orchestration)
5. [Security and Enterprise Constraints](#security-and-enterprise-constraints)
6. [Appendix: Alternate Designs - Up for Consideration](#appendix-alternate-designs---up-for-consideration)
7. [Summary](#summary)

---

## Background and Scope

This is a practical walkthrough of a pattern I expect to show up often in enterprise IT over the next few years:

- Start with an ordinary REST-based business app (DB + service layer + controller + auth).
- Add an MCP “tool surface” on top of the existing service layer (not a rewrite).
- Put a chat UI in front of it so an LLM can orchestrate multi-step workflows on behalf of a user.

The concrete example here is a vacation management system:

- A standard web backend that manages employee profiles, vacation balances, and vacation requests.
- A traditional REST interface (what most apps already have).
- A second interface implemented as an MCP server exposing a small set of well-defined tools.
- A separate “HR Helper” chat app that authenticates users, discovers tools, and lets the model call those tools.

The point is not “chat instead of REST.” The point is that once the model can call tools, it can combine existing
operations (balance + business-day calculation + create request + explain policy) into a single intent-driven interaction.

### What This Is Not
This is not a REST primer, an MCP spec walkthrough, or an OIDC/Keycloak setup guide.

If you’re reading this, you should be comfortable looking at code and recognizing the pattern. The value here is the
*delta*: what had to change to make a conventional app work via MCP + chat, and why the resulting system can do more
than the original UI.

---

## Baseline: A Standard Enterprise REST App

### Baseline Architecture (Before MCP)
Before MCP shows up anywhere, the vacation system is intentionally boring in the best way:

- **Controller layer**: a Flask app exposes a REST API (request parsing, auth gate, response shaping).
- **Service layer**: business rules live in a separate module (validation, accrual rules, balance math).
- **Data access layer**: raw SQL behind a small database gateway (connection pool + CRUD).
- **Identity**: user context comes from OAuth/OIDC tokens (the employee is derived from claims).

That separation is the entire reason the retrofit works well: the “interesting” logic is already
isolated behind a service boundary, so we can add a second interface (MCP tools) without rewriting core behavior.

Concretely, the layers map like this:

- `vacay/backend/flask_main.py`: REST routes + authentication decorator
- `vacay/backend/vacation_service.py`: business logic (vacation rules, validations)
- `vacay/backend/db_service.py`: SQL + persistence (employees, vacations, holidays)
- `vacay/backend/utils.py`: pure calculations (business days, corporate holidays)

### Data Model and Persistence
The schema is what you’d expect from an internal HR-ish system: a small set of tables with clear ownership
and predictable queries.

- `employees`: maps an authenticated identity (OIDC user id / email) to an internal employee row.
- `vacation_requests`: stores vacation/optional-holiday requests, date range, computed business days, and status.
- `corporate_holidays`: a per-year set of holidays used by business-day calculations.

Two implementation choices are worth calling out because they mirror real enterprise tradeoffs:

1. **Accrual is calculated, not stored.** Vacation accrual is derived from `hire_date` and “today”. This avoids
   scheduled jobs and makes the balance calculation deterministic and explainable.
2. **Holidays are lazily synced.** Corporate holidays are computed and inserted for the current/next year when needed
   (on balance checks). This keeps operational complexity low while still giving consistent results.

### REST Surface Area (Controller Layer)
The REST API is conventional and intentionally small. The endpoints are basically a “my account” surface:

- `GET /employees/me`, `PUT /employees/me`: read/update profile (notably `hire_date`)
- `GET /employees/me/balance`: compute current-year balance (accrued/used/available)
- `GET /vacations`, `POST /vacations`, `DELETE /vacations/<id>`: manage vacation requests
- `GET /holidays`: sync + return corporate holidays for a given year
- `POST /vacations/calculate-days`: business day calculator for a date range

Authentication is handled the way many enterprise internal apps do it:

- Expect `Authorization: Bearer <token>`
- Validate and extract identity claims via `fit-jwt-py` 
- Derive an `employee` record (create on first login) and use that as the authorization anchor

The important takeaway for the MCP retrofit: REST is just one adapter over the service layer.

**Note:** `fit-jwt-py` is a dev/prototype implementation of OIDC; alternate libraries exist
for production-grade authentication and authorization.

### Business Rules Worth Noticing
This project includes “real enough” policy logic to be enterprise-relevant:

- **Accrual**: 1 vacation day per month, capped at 12 per year.
- **Optional holidays**: 3 per year, no carryover.
- **Carryover**: up to 5 vacation days can carry from the previous year.
- **Validation**: cannot request or delete vacation in the past; start date must be <= end date.
- **Day counting**: business days exclude weekends and corporate holidays.

From a retrofit perspective, these rules matter because they define the boundary of “safe tool calls.”
Whether invoked via REST or MCP, the same validation and calculation logic should run.

### “Enterprise Normal” Check
If you handed this codebase to an enterprise team, nobody would be surprised by the shape:

- Clear layering (controller/service/data access)
- Identity comes from the IdP (OIDC), not a local user table
- Explicit validation and error handling at the API boundary
- Predictable persistence model with a relational database

That “normalcy” is the point. This is about what happens when you take a baseline like this and add an
MCP tool surface plus a chat UI—without turning the system into a science project.

---

## Retrofitting: Adding an MCP Surface Area

### Design Goal: A Second Interface, Same System
The retrofit goal is intentionally conservative: **add MCP without changing what the system *is*.**

- REST remains a first-class interface.
- The database schema and business rules remain unchanged.
- MCP becomes a *second adapter* over the existing service layer.

In other words: we’re not “building an agent.” We’re exposing a small set of well-defined operations
as tools, the same way we exposed them as REST endpoints.

This is the key enterprise-friendly framing:

- REST = “a UI calls these endpoints”
- MCP tools = “a model can request these operations”

Same underlying code. Same permission boundaries. Same validations. Different caller.

**Note:** Please see the appendix for two alternative design approaches.

### MCP Server Entry Point
The MCP server lives in `vacay/backend/mcp_main.py` and is a thin wrapper around the existing vacation service.

The important bits:

- Uses `FastMCP` and runs with `transport="streamable-http"`.
- Exposes tools with `@mcp.tool()` decorators.
- Returns JSON-friendly structures (dates converted to ISO strings).

The MCP server is not where your business rules should live. In this repo, the MCP layer delegates to
`vacation_service.py`, which delegates to `db_service.py` / `utils.py`.

### MCP Authentication and Identity Threading
This is where the enterprise acceptability argument is won or lost.

In `vacay/backend/mcp_main.py`:

- The server is configured with a `token_verifier` (created from environment via `token_verifier.py`).
- Each tool call pulls the access token from the MCP auth context (`get_access_token()`).
- The token is decoded/validated and mapped into a normalized `current_user` object via `fit-jwt-py`.

That `current_user` structure (OIDC subject, email, names) is then passed to the same service methods used by REST.

Result: the model never supplies an employee identifier, and the system never trusts user input for identity.
Identity is derived from the token, just like a normal enterprise API.

---

## Making It Useful: Chat UI + Tool Orchestration

### What Changes When You Add Chat
Adding chat isn’t about swapping a form for a text box. It adds a new layer:
**an orchestrator that can chain operations**.

In the REST UI, the user is the orchestrator: click “balance,” then click “calculate days,” then submit a request,
then resolve errors.

In the chat UI, the model becomes the orchestrator *but only through tools you define*. That’s the capability jump:
one user intent can trigger a sequence like “fetch balance → compute business days → validate policy → create request → summarize result.”

### HR Helper Architecture
The HR Helper app is intentionally thin and looks like a typical enterprise “BFF” (backend-for-frontend), except its downstream is MCP.

- `hrhelper/server.py`: Flask app that handles auth, receives chat messages, calls the LLM, and brokers tool calls.
- `hrhelper/mcp_client.py`: MCP-over-HTTP client (Streamable HTTP transport) used to list tools and call tools.
- `hrhelper/static/*`: a simple web chat UI.

The important design decision: **HR Helper does not implement HR business logic.** It delegates to the Vacay MCP server
tools, which delegate to the existing service layer.

### Tool Discovery Per User
Tools are fetched with the user’s access token and treated as user-scoped capabilities.

In `hrhelper/server.py`, the chat handler forwards the user’s `Authorization` header to:

- `mcp_client.list_tools(access_token=...)`

This keeps the contract clean:

- The chat app doesn’t “decide” what a user can do.
- The MCP server can vary tool availability or behavior based on identity/claims if you want that later.

Implementation detail: tools are cached in the user session so you don’t re-fetch them on every message.

### Tool Calling and Delegation
When the model requests a tool call, HR Helper:

1. Parses the tool name + JSON arguments from the model.
2. Calls `mcp_client.call_tool(tool_name, args, access_token=...)`.
3. Sends the tool result back to the model as a tool response.

This is the enterprise-friendly split:

- The model chooses *which tool to call* and *with what parameters*.
- The server enforces authn/authz, validates inputs, and performs deterministic writes.

From an operational perspective, this is also where you’d add logging for tool calls (user, tool name, request id, outcome).

### Capability Gain: Why This Is Better Than the Original UI

#### Orchestrating Multiple Operations
The chat flow can combine multiple “screens worth” of actions into one:

- “Do I have enough vacation to take Dec 20 – Jan 3? If I do, submit it.”

Behind the scenes that becomes a chain of tool calls (balance + business-day calc + create), with the same validation you had in REST.

#### Contextual Follow-ups and Clarification
The model can ask for missing fields *before* calling a write tool:

- “Do you want vacation days or optional holidays?”
- “What dates should I use?”

This reduces “submit → error → retry” loops that are common in form-based flows.

#### Presenting the Right Shape of Answer
The response doesn’t have to match a fixed UI screen.

Example pattern:

- Summarize current balance (available/accrued/used + carryover).
- List upcoming vacations (if any).
- Recommend next action (“You have enough days; want me to create it?” or “You’re short by 2 days; here are options”).

---

## Security and Enterprise Constraints

### Auditing and Traceability (Practical Additions)
If you deploy a pattern like this internally, you’ll want to be able to answer: “Who did what, and why did the system allow it?”

Practical places to add traceability:

- In HR Helper (or any orchestrator): log the tool name + tool arguments (or a hash) + user identity + timestamp.
- In the MCP server: log tool execution + validation failures + write outcomes.

At minimum, capture:

- Correlation id (per chat request)
- User identifier (OIDC `sub` or equivalent)
- Tool name
- Success/failure + error reason

You don’t need perfect observability for a prototype, but you do need the *shape* of an audit trail if you want enterprise
teams to take it seriously.

### Data Minimization
Models are great at combining information. That’s also why you should be careful about what you feed them.

Guidelines that scale well:

- Keep tool outputs narrow and purposeful (return what the user asked for, not the whole record).
- Avoid returning sensitive identifiers unless needed.
- Normalize outputs (dates, enums) so the model doesn’t have to infer meaning.
- Treat tool results as “data leaving the system-of-record boundary,” even if it’s just to an internal LLM.

In this repo, the baseline is already good: tools return structured JSON and avoid exposing raw database details.

### The Basics Remain Critical

Even though the interface is “AI-shaped,” the safety story is still mostly traditional enterprise engineering:
isolate sessions so one user’s context can’t bleed into another’s; apply role-based access control so tool availability
(and tool behavior) matches job function; and add pragmatic controls for managing mischief (rate limits, input validation, 
tool-level allow/deny lists, and guardrails around write operations). A chat UI can make powerful actions easier to reach
 — which is exactly why your identity boundary, authorization checks, and abuse controls need to be as boring and reliable
 as they’ve always been.

In short: Keep doing the great things you're doing to keep your enterprise safe!

---

## Appendix: Alternate Designs - Up for Consideration

In this prototype, I chose a specific path: add an MCP surface area next to the existing REST controller, and reuse the same
service layer.

That’s not the only approach. Two common alternatives are worth calling out:

1. **External MCP adapter (thin pass-through layer).**
	- What it is: a separate service that speaks MCP on one side and calls the existing REST API on the other.
	- Why you’d do it: keeps the original app completely unmodified; great for early experiments, pilots, or when you can’t easily
	  change the system-of-record.
	- Tradeoff: you now have *two* places to think about auth, logging, throttling, and policy enforcement.

2. **API-to-MCP gateway tooling (automated exposure).**
	- What it is: emerging products that can ingest OpenAPI/Swagger (or similar) and expose endpoints as MCP tools automatically
	  (for example, Amazon’s Bedrock AgentCore Gateway).
	- Why you’d do it: reduces the manual work of writing tool schemas and wrappers; can standardize cross-cutting concerns
	  (auth, routing, observability) in one place.
	- Tradeoff: you still need to decide what should be callable, how to constrain inputs/outputs, and which operations are
	  safe to expose. Tooling can accelerate the “plumbing,” but it doesn’t replace governance.

---

## Summary

This walkthrough started with a deliberately normal enterprise app: a REST API backed by a relational database, a service layer
that owns the business rules, and token-based identity.

From there, the key move was to add a second interface — MCP — without rewriting the system. The MCP server is just another adapter
over the same deterministic code paths, which means policy and validation stay consistent whether the caller is a browser, a script,
or a chat-based assistant.

Finally, the chat UI is where the capability gain shows up. It doesn’t replace REST; it orchestrates it. Instead of forcing users
through a sequence of screens and retries, the assistant can chain safe tool calls (read balance, calculate business days, create request)
and present the result in the shape the user actually needs.

If you take only one lesson from this: keep the boundaries boring. Make tools explicit, thread identity through tokens, keep writes deterministic,
and invest in the basics (session isolation, RBAC, logging, and abuse controls). With those fundamentals in place, “agentic” behavior becomes
something you can adopt incrementally—and responsibly.
