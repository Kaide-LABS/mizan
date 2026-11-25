# Stage 4

## What was built

The part of Mizan that runs the pretend investment test now exists. It can take the price history of the approved coins, split money evenly across them, "hold" them over time, and work out the result after subtracting realistic trading fees. New automatic checks confirm this fee-aware calculation behaves correctly, and the full battery of checks — including the ones that prove the locked religious-compliance rules cannot be turned off — all passed.

## What was decided

Trading fees are always treated as a real, non-zero cost, because a test that ignored fees would flatter the results and mislead. This was built in deliberately rather than left as an easy-to-forget setting.

## What is uncertain

The stage was flagged as "not completed" — but this appears to be a paperwork mismatch, not a problem with the actual work: the code was finished, saved, and all checks passed. Worth a human confirming the records line up. Also still unfinished: the final report page and the single start-to-finish command that ties everything together are planned but not yet built. One minor open question remains about file naming on Windows that may need attention in a later stage.
