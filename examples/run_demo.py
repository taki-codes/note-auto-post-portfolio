"""Exercise a fictional lifecycle in a temporary project; never access note.com."""
import argparse
import json
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from note_workflow import Project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='New directory for fictional records; must not exist')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='note-workflow-demo-') as temp:
        project = Project(Path(temp))
        row = project.register('fictional-demo', '架空の動作確認データ',
                               'https://note.com/fictional_demo/n/fictional_demo', '2024-01-31', 'free')
        due = project.due(date(2024, 2, 7))
        observed = project.observe('fictional-demo', '合成fixture（通信なし）', 'fictional fixture',
                                   likes=0, notes='実在の記事・実測値ではありません。',
                                   observed_at='2024-02-07T10:00:00+09:00')
        first = json.loads(observed.read_text(encoding='utf-8'))
        project.set_status('fictional-demo', 'paused', '架空の一時停止')
        assert project.due(date(2024, 3, 1)) == []
        deadline = project.due(date(2024, 4, 30))
        project.observe('fictional-demo', '合成fixture（通信なし）', 'fictional fixture',
                        notes='架空の期限処理。数値は未取得。',
                        observed_at='2024-04-30T10:00:00+09:00', final=True)
        summary = {'fictional': True, 'network_access': False,
                   'monitor_until': row['monitor_until'], 'day_7_action': due[0]['action'],
                   'likes': first['likes'], 'views': first['views'], 'purchases': first['purchases'],
                   'deadline_action': deadline[0]['action'],
                   'final_status': project.read()[0]['monitoring_status']}
        assert summary['monitor_until'] == '2024-04-30'
        assert summary['likes'] == 0 and summary['views'] is None
        assert summary['final_status'] == 'completed'
        if args.out:
            target = args.out.resolve()
            target.mkdir(parents=True, exist_ok=False)
            shutil.copyfile(project.ledger, target/'published_articles.csv')
            shutil.copytree(project.root/'monitoring', target/'monitoring')
            (target/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
