# Personalized Yearly Advice Design

## Goal

Make the four yearly agents give one clear, personalized recommendation each.
The personal agent must use the user's actual profile and current simulation
state rather than mechanically echoing the yearly strategy preference.

## Constraints

- Keep decision-source actions, scoring, endings, SSE event names, historical
  sessions, and existing scenario JSON compatible.
- Agents may only select declared action IDs. The LLM explains and recommends;
  the deterministic engine remains responsible for state transitions.
- Every agent attempts a scene-filtered RAG lookup every year.
- A missing, empty, or failed lookup must not stop the simulation. The agent
  falls back to the user profile, decision variables, current world state, and
  scenario rules without inventing external facts.

## Advice Contract

Each AgentAction gains optional presentation fields:

- `recommendation`: one concrete annual recommendation.
- `key_factors`: two or three readable, user-specific reasons.
- `next_actions`: one to three actions with an observable completion result.
- `stop_condition`: the signal that requires a pause or plan change.
- `uncertainty`: the most important missing fact or assumption.
- `evidence_status`: `hit`, `empty`, `error`, or `disabled`.
- `evidence_sources`: source labels only when retrieval found usable material.

Older actions lacking these fields remain valid and receive readable fallback
presentation in the existing narration layer.

## Agent Behavior

All four agents return the same compact user-facing structure while retaining
their role boundaries. Market focuses on demand and competition; environment
on external conditions; personal on funds, time, skills, commitments, family
burden, risk preference, prior progress, and the current state; risk on
runway, irreversible cost, downside, and exit conditions.

`yearly_strategy` is a user preference. It must be considered by the personal
agent but is never a command that overrides infeasible personal conditions.
When the profile is too incomplete for a personalized conclusion, the personal
agent must identify the single highest-impact missing fact in `uncertainty`.

## Retrieval Behavior

RoleToolRouter constructs four different queries using scenario ID, year,
decision variables, current state, and the current user decision. It invokes
the knowledge search for every role, then retains the personal execution or
risk stress-test evidence as supplementary local evidence where available.

RAG results are sanitized before the LLM sees them. A hit carries source
labels; an empty result states that no directly relevant external material was
found; an error states that retrieval was unavailable. Only a hit may support
claims described as external evidence.

## Presentation

AgentPanel presents each role as: annual judgment, why it fits the current
case, next steps, stop condition, uncertainty, and evidence status. It must
not expose action IDs, raw prompt data, or implementation field names. Four
role cards remain comparable and do not render empty decorative sections.

## Verification

- Unit tests prove all four roles make role-specific knowledge lookups.
- LLM-agent tests prove personal advice includes provided profile constraints
  and treats the yearly strategy as a preference.
- Empty/error retrieval tests prove advice still returns without fabricated
  sources.
- Coordinator and API regression tests protect existing action validation,
  event payloads, scenario routing, and paused yearly flow.
- Frontend build completes after the AgentPanel update.
