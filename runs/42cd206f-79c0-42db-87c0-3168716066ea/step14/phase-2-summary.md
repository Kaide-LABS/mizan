# Stage 2

## What was built

The groundwork for getting price history now exists. Mizan can reach out to a free public source to download daily coin prices, with a backup source if the first one is unavailable, and store them neatly without creating duplicates. It also now has a calendar that treats crypto as trading every day of the year, since coins never close for weekends or holidays. The programs that handle this were checked for quality and passed those checks.

## What was decided

Prices come from one main free provider, with a second as backup, so a single outage doesn't stop the research. An older, stable version of one storage tool was kept rather than upgraded, to avoid surprises. These choices favour reliability over novelty.

## What is uncertain

This stage did its building but did not finish its safety net. The specific tests meant to prove this stage's work behaves correctly were never written, and a required summary document for this stage was never created — both have been pushed into the next stage. The work also could not be saved properly at the time because the system blocked it. One minor reliability fix for saving prices is still outstanding. The next stage must close all of these gaps first.
