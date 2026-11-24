def test_export_carries_plan(client, sources):
    key = client.post('/api/journal', json={'sources': sources}).json['run_id']
    evidence = client.get(f'/api/export/{key}').json
    ship = evidence['reports']['plan']['ships']['海棠17']
    assert ship['decision'] == 'slow' and ship['scheme']['下游浅滩']['slow_kn'] == '5'
    assert 'speeds' in evidence['originals']
    assert evidence['verified'] is True


def test_export_old_archive_keeps_speeds(client, sources):
    first = client.post('/api/journal', json={'sources': sources}).json['run_id']
    amended = sources['speeds'].replace('海棠17,下游浅滩,8,8,5,0.20', '海棠17,下游浅滩,8,8,5,0.60')
    client.post(f'/api/journal/{first}/rerun', json={'speeds': amended})
    evidence = client.get(f'/api/export/{first}').json
    assert evidence['originals']['speeds'] == sources['speeds']
    assert evidence['reports']['plan']['ships']['海棠17']['decision'] == 'slow'


def test_legacy_archive_derives_plan_without_changing_seal(client, sources):
    from app.flow import calculate
    from app.modules.journal.manifest import manifest
    journal = client.application.extensions['tide_journal']
    reports = calculate(sources)
    legacy = {key: value for key, value in reports.items() if key != 'plan'}
    receipt = manifest(sources, legacy, '2026-11-23T00:00:00Z', 1)
    journal.publish(receipt, sources, legacy)
    evidence = client.get(f"/api/export/{receipt['run_id']}").json
    assert evidence['verified'] is True and 'plan' not in evidence['reports']
    assert evidence['plan_view']['derived'] is True
    assert evidence['plan_view']['plan']['ships']['海棠17']['decision'] == 'slow'
