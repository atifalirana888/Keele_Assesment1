## Preparation

1. Extract the ZIP, open the **PennyPilot** folder in VS Code, and open its terminal.
2. Run `python -m unittest discover -s tests -v` first and show the successful summary briefly.
3. Run `python cli.py --demo`, then `python gui.py --demo` **sequentially**, so both demonstrate the same `data/demo_workspace.json` file. (Use `py` instead of `python` on Windows if necessary.)

## Suggested spoken walkthrough

| Approx. segment | What to show | What to explain |
| --- | --- | --- |
| Opening | Project folder, files, `.vscode/launch.json` | “PennyPilot is an offline personal budget tracker developed in two interfaces, sharing one core logic layer.” |
| CLI features | `python cli.py --demo`, menu option **1** | “The monthly summary computes income, spending and net balance, with category grouping and budget alerts.” |
| CLI add | Option **3**, expense / `2026-11-20` / category `Groceries` / description `Demo fruit bowl` / amount `8.75` / note `Demo` | “Records are validated, have unique IDs and save automatically.” |
| CLI search | Option **2**, month `2026-11`, search `fruit`, sort `newest` | “Text searching and filters locate a matching transaction.” |
| CLI budget | Option **6** to show progress; optionally **7** to update | “Each category can have an independently configured limit per month.” |
| Switch interface | Exit CLI with **0**, start `python gui.py --demo` | “The GUI reads the same saved records, not duplicated logic.” |
| GUI overview | Main dashboard, spending breakdown, budget health | “This visual front end presents the same totals and overspending information.” |
| GUI transactions | Transactions tab; search `fruit`; select row; edit or delete it | “The table supports search, sorting, editing and deletion, including confirmation.” |
| GUI budget | Budgets tab; use **Create budget** or **Edit limit** | “Progress indicators update immediately when a budget is changed.” |
| GUI export + code | Transactions → **Export CSV**, then show `service.py` / `models.py` / `storage.py` in VS Code | “Filtered CSV export is available in both versions, and the core modules manage validation and persistence.” |
| Closing | Test results and README | “The project includes automated normal, boundary and invalid-input tests, plus installation instructions.” |


