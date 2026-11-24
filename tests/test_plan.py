from fractions import Fraction

from app.clock import moment
from app.flow import calculate
from app.source import load_sources


def test_slow_catches_current_window(case):
    ship = case['plan']['ships']['海棠17']
    assert ship['decision'] == 'slow'
    assert ship['departure'] == str(moment('2026-11-22T15:46:22Z') + Fraction(1, 32))
    upstream = next(row for row in ship['sections'] if row['section'] == '上游外闸')
    downstream = next(row for row in ship['sections'] if row['section'] == '下游浅滩')
    assert (upstream['kn'], upstream['required_m'], upstream['margin_m']) == ('5', '675/256', '0')
    assert downstream['required_m'] == '165/64' and downstream['margin_m'] == '7/320'


def test_static_draft_would_pass_but_keep_blocked(case):
    ship = case['plan']['ships']['海棠17']
    assert ship['static']['anchor']['status'] == 'open'
    assert ship['options']['keep']['anchor']['status'] == 'blocked'
    assert ship['options']['slow']['first_departure'] is not None
    assert ship['options']['keep']['first_departure'] is None


def test_keep_waits_for_next_high(case):
    ship = case['plan']['ships']['甬航05']
    assert (ship['decision'], ship['mode']) == ('wait', 'keep')
    assert ship['departure'] == str(moment('2026-11-23T00:20:00+08:00'))
    assert ship['options']['keep']['next_departure'] == ship['departure']
    assert ship['beyond_window'] is True


def test_slow_only_next_high(case):
    ship = case['plan']['ships']['江桐62']
    assert (ship['decision'], ship['mode']) == ('wait', 'slow')
    assert ship['options']['keep']['next_departure'] is None
    assert ship['options']['slow']['next_departure'] == ship['departure']
    assert ship['beyond_window'] is True


def test_clean_scene_keeps_speed():
    clean = calculate(load_sources({'sample': 'clean'}))
    assert {ship['decision'] for ship in clean['plan']['ships'].values()} == {'keep'}


def test_offsets_rescaled_by_speed(case):
    ship = case['plan']['ships']['海棠17']
    assert ship['options']['keep']['sections'][1]['offset_s'] == '600'
    assert ship['options']['slow']['sections'][1]['offset_s'] == '960'


def test_squat_squared_scaling(case):
    slow = case['plan']['ships']['海棠17']['options']['slow']['sections']
    upstream = next(row for row in slow if row['section'] == '上游外闸')
    assert upstream['squat_m'] == '35/256'


def test_missing_speeds_unknown(sources):
    del sources['speeds']
    plan = calculate(sources)['plan']
    assert plan['available'] is False
    assert {ship['decision'] for ship in plan['ships'].values()} == {'unknown'}
    assert all(ship['departure'] is None for ship in plan['ships'].values())


def test_incomplete_speed_sheet(tmp_path, sources):
    sources['speeds'] = 'vessel,section,design_kn,keep_kn,slow_kn,squat_coeff\n海棠17,上游外闸,8,8,5,0.35\n'
    plan = calculate(sources)['plan']
    assert plan['ships']['海棠17']['decision'] == 'unknown'
    assert plan['ships']['海棠17']['missing_sections'] == ['下游浅滩']


def test_bad_speed_rows(sources):
    sources['speeds'] += '幽灵船,上游外闸,8,8,5,0.3\n海棠17,上游外闸,8,8,5,0.3\n海棠17,火星断面,8,8,5,0.3\n'
    plan = calculate(sources)['plan']
    assert [row['code'] for row in plan['rejected']] == ['UNKNOWN_VESSEL', 'DUPLICATE_SPEED', 'UNKNOWN_SECTION']


def test_plan_stage_api(client):
    response = client.get('/api/stage/plan?sample=dirty')
    assert response.status_code == 200
    assert response.json['ships']['海棠17']['decision'] == 'slow'


def test_plan_page(client):
    body = client.get('/desk/plan?vessel=海棠17').get_data(as_text=True)
    assert '减速吃当前窗口' in body and '各断面余量（按方案重核）' in body


def test_late_speeds_recompute_keeps_old_archive(client, sources):
    first = client.post('/api/journal', json={'sources': sources}).json
    assert first['supersedes'] is None
    amended = {**sources, 'speeds': sources['speeds'].replace(
        '海棠17,下游浅滩,8,8,5,0.20', '海棠17,下游浅滩,8,8,5,0.60')}
    second = client.post(f"/api/journal/{first['run_id']}/rerun", json={'speeds': amended['speeds']}).json
    assert second['run_id'] != first['run_id'] and second['reused'] is False
    old = client.get(f"/api/journal/{first['run_id']}").json
    new = client.get(f"/api/journal/{second['run_id']}").json
    assert old['plan']['ships']['海棠17']['scheme']['下游浅滩']['squat_coeff'] == '1/5'
    assert new['plan']['ships']['海棠17']['scheme']['下游浅滩']['squat_coeff'] == '3/5'
    assert old['plan']['ships']['海棠17']['decision'] == 'slow'
    assert new['plan']['ships']['海棠17']['decision'] == 'wait'
    assert old['windows']['海棠17']['windows'][0]['end'] == '1795363200'
    assert new['manifest']['parent'] == first['run_id']


def test_same_speeds_retry_reuses_archive(client, sources):
    first = client.post('/api/journal', json={'sources': sources}).json
    second = client.post(f"/api/journal/{first['run_id']}/rerun", json={'speeds': sources['speeds']}).json
    assert second['reused'] is True and second['run_id'] == first['run_id']
    assert second['supersedes'] is None
    assert len(client.get('/api/journal').json['runs']) == 1


def test_old_archive_still_recomputes(client, sources):
    first = client.post('/api/journal', json={'sources': sources}).json
    amended = {**sources, 'speeds': sources['speeds'].replace(
        '海棠17,下游浅滩,8,8,5,0.20', '海棠17,下游浅滩,8,8,5,0.60')}
    client.post(f"/api/journal/{first['run_id']}/rerun", json={'speeds': amended['speeds']})
    replay = client.post(f"/api/journal/{first['run_id']}/rerun")
    assert replay.json['reused'] is True and replay.json['run_id'] == first['run_id']


def test_archive_stage_lookup(client, sources):
    key = client.post('/api/journal', json={'sources': sources}).json['run_id']
    assert client.get(f'/api/stage/plan?run={key}').json['ships']['海棠17']['decision'] == 'slow'


def test_reject_unknown_amend(client, sources):
    key = client.post('/api/journal', json={'sources': sources}).json['run_id']
    response = client.post(f'/api/journal/{key}/rerun', json={'bogus': 1})
    assert response.status_code == 422
