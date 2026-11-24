from flask import Blueprint, current_app, jsonify, request

from app.errors import TideError
from app.flow import STEPS, calculate, view
from app.modules.journal.service import record
from app.modules.proof.service import issue
from app.source import load_sources

api = Blueprint('api', __name__, url_prefix='/api')


def journal():
    return current_app.extensions['tide_journal']


@api.route('/stage/<stage>', methods=['GET', 'POST'])
def stage_result(stage):
    if stage not in STEPS:
        raise TideError('NO_STAGE', '找不到潮窗模块', 404)
    if 'run' in request.args and request.method == 'GET':
        _, _, reports = journal().get(request.args['run'])
        reports = view(reports)
        if stage not in reports:
            raise TideError('NO_STAGE_DATA', '该归档未含此阶段结果', 409)
    else:
        payload = request.get_json(silent=True) if request.method == 'POST' else {'sample': request.args.get('sample', 'dirty')}
        reports = calculate(load_sources(payload), stage)
    return jsonify(reports[stage])


@api.get('/journal')
def list_journal():
    return jsonify(runs=journal().list())


@api.post('/journal')
def publish_journal():
    result = record(journal(), load_sources(request.get_json(silent=True)))
    return jsonify(result), 200 if result['reused'] else 201


@api.get('/journal/<key>')
def inspect_journal(key):
    receipt, _, reports = journal().get(key)
    derived = view(reports)
    return jsonify(run_id=key, manifest=receipt, coverage=derived['coverage'],
                   plan=derived.get('plan'), windows=derived['windows'])


@api.post('/journal/<key>/rerun')
def repeat_journal(key):
    manifest, sources, _ = journal().get(key)
    amend = request.get_json(silent=True) or {}
    if not isinstance(amend, dict) or set(amend) not in (set(), {'sources'}, {'speeds'}):
        raise TideError('BAD_SOURCE', '复算只接受补充原件')
    if 'sources' in amend:
        updated = load_sources({'sources': amend['sources']})
    elif 'speeds' in amend:
        if not isinstance(amend['speeds'], str):
            raise TideError('BAD_SOURCE', '航速表应为 CSV 文本')
        updated = {**sources, 'speeds': amend['speeds']}
    else:
        updated = sources
    return jsonify(record(journal(), updated, manifest))


@api.get('/export/<key>')
def download(key):
    receipt, sources, reports = journal().get(key)
    response = jsonify(issue(receipt, sources, reports, view(reports)))
    response.headers['Content-Disposition'] = f'attachment; filename="tide-{key[:12]}.json"'
    return response
