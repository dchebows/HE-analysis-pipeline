Summary of Changes:
ETL Pipeline:
✅ Schedule: 6am → 8am EST (13:00 UTC)
✅ Concurrency: daily-pipeline → etl-portfolio-chain
CRR Analysis:
✅ Schedule: 7pm → 6pm EST (22:00 UTC)
✅ Concurrency: daily-pipeline → crr-pipeline
Portfolio Daily:
✅ Added ETL as trigger (watches both CRR and ETL completions)
✅ Added schedule: 6:15pm EST (22:15 UTC)
✅ Concurrency: daily-pipeline → etl-portfolio-chain
✅ Updated condition to include schedule trigger
How it works now:
Daily Scheduled Flow:
8am: ETL runs → Portfolio auto-triggers
6pm: CRR runs → Portfolio auto-triggers
6:15pm: Portfolio scheduled run (backup)
Ad-hoc HTML Addition (your main request!):
Anytime you push HTML → ETL triggers → Portfolio auto-triggers ✅
The etl-portfolio-chain concurrency ensures Portfolio always waits for ETL to complete!
