from app import service
from scripts.master_runner import run


def test_master_runner_respects_the_policy(tmp_path):
    csv_file = tmp_path / "in.csv"
    csv_file.write_text(
        "title,description\n"
        "Excel freezing,spreadsheet application hangs when opening large workbook\n"
        "Account locked,my account got locked after several failed login attempts\n"
        "Ransomware message,files are encrypted and a ransom note appeared on the desktop\n")
    summary = run(str(csv_file))
    assert summary["failed"] == 0 and summary["processed"] == 3
    assert summary["auto_closed"] == 1 and summary["awaiting_approval"] == 1 and summary["manual_review"] == 1
    assert sum(t["status"] == "CLOSED" for t in service.list_tickets()) == 1
