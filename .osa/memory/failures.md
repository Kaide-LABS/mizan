# Failures and fixes

What went wrong in past runs and what resolved it. One fact per line.

- Run stopped: One AI tool's hand-over note to the next could not be read, so the build was stopped rather than carry on from a possibly wrong state. _(run 42cd206f, 2026-11-24)_
- Phase 1 did not complete: ✖ Invalid string: must match pattern /^([0-9a-f]{40}|[0-9a-f]{64})$/ → at repo.head_before ✖ Invalid string: must match pattern /^([0-9a-f]{40}|[0-9a-f]{64})$/ → at repo.head_after _(run 42cd206f, 2026-11-24)_
- Unconfirmed research claim (do not rely on it): DuckDB Python package is at 2.0.1 per the install docs. _(run 42cd206f, 2026-11-24)_
- Unconfirmed research claim (do not rely on it): Kraken OHLC interval enum (minutes) is 1,5,15,30,60,240,1440,10080,21600; response row is [time,open,high,low,close,vwap,volume,count]. _(run 42cd206f, 2026-11-24)_
- Unconfirmed research claim (do not rely on it): Coinbase Pro (api.pro.coinbase.com) was fully shut down by 2023-11-09; Exchange API is its non-deprecated successor. _(run 42cd206f, 2026-11-24)_
- Unconfirmed research claim (do not rely on it): Source text contained an instruction aimed at an AI (governance); it was removed and nothing from it was used _(run 42cd206f, 2026-11-24)_
- Research item docs-agent-reach failed: Field "pitfalls" contains [uncertain] but is not listed in the "uncertain" array. _(run 42cd206f, 2026-11-24)_
- Research item docs-mirofish failed: A documentation item must cite at least one source of type "official-docs". _(run 42cd206f, 2026-11-24)_
- Research item kraken-public-candles failed: "uncertain" names "endpoint_url_and_params", which is not a field of this result. _(run 42cd206f, 2026-11-24)_
- Run stopped: The build stopped before it was finished. _(run 42cd206f, 2026-11-24)_
- Phase 3 did not complete: codex-cli: The AI provider stopped with an error (it exited with code 1). _(run 42cd206f, 2026-11-24)_
- Run stopped: One of the AI tools stopped the build on purpose and said it should not continue. _(run 42cd206f, 2026-11-24)_
- Phase 3 did not complete: turn reported status "blocked" _(run 42cd206f, 2026-11-24)_
- Phase 4 did not complete: claude-code: The AI provider could not be reached (a network drop or a provider-side outage). It usually clears within minutes. _(run 42cd206f, 2026-11-24)_
- Phase 4 did not complete: HandoffRecord failed re-validation after ground-truth reconciliation (this is a reconciliation inconsistency -- ground truth contradicts the agent's own report -- not a raw schema defect): ✖ status === "completed" implies repo.commits.length >= 1... _(run 42cd206f, 2026-11-25)_
- Phase 5 did not complete: ✖ Invalid string: must match pattern /^[0-9a-f]{64}$/ → at spec_ref.sha256 _(run 42cd206f, 2026-11-25)_
- Run stopped: The finished project did not pass the final check. _(run 42cd206f, 2026-11-25)_
- The final check could not be carried out: ✖ Too big: expected string to have <=1500 characters → at notes _(run 42cd206f, 2026-11-25)_
