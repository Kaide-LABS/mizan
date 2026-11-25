# Stage 4

## What was built

The part of Mizan that runs the pretend investment test now works. It takes the approved coins, spreads money evenly across them, holds them over time, and applies realistic trading fees — all on paper, with no real money. It can also figure out which coins passed the religious-compliance screen and work out the test's rebalancing dates. A full set of automated checks for this piece now exists and all of them pass.

## What was decided

Trading fees are permanently switched on and can never be set to zero, so every test reflects real-world costs — this was chosen to keep results honest. The coin list is always read fresh each run rather than remembered from before, to avoid stale results.

## What is uncertain

This stage is finished, but the project is not. The report that a grant judge would read, and the single command that runs everything start-to-finish, are still not built. One open point: whether a future stage should allow a zero-fee check for testing. Also, one reviewer ended up checking their own earlier work rather than a second person doing it.
