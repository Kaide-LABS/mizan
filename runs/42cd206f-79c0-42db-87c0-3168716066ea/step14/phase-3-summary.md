# Stage 3

## What was built

The coin-screening part of the tool now works. It can take each of the named coins and sort it into a religious-compliance category with a clear accept-or-reject verdict, covering all the coins on the list plus a set of coins that are always turned down. A safety fix was also made so that saving price data either fully succeeds or fully undoes itself, never leaving half-saved data. New automated checks were added to prove the screening behaves correctly, and all current checks — 452 of them — pass.

## What was decided

The work built on an earlier unfinished draft rather than starting over, to save time. Reusing it was double-checked first by confirming every existing check still passed before anything was touched.

## What is uncertain

This stage did not finish. A large batch of planned safety checks — especially around pulling in the daily price data and confirming the locked rules truly cannot be switched off — was not written, because there wasn't enough time. By the project's own standard, this stage cannot count as done until those checks exist and pass. That work still needs to be completed and re-verified before moving on.
