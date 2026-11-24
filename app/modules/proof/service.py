from app.errors import TideError

from .signature import seal, verifies


def issue(receipt, sources, reports, view=None):
    if not verifies(reports, receipt['result_sha256']):
        raise TideError('INVALID_PROOF', '归档结果校验未通过', 409)
    if set(sources) != set(receipt['inputs']):
        raise TideError('INVALID_PROOF', '归档原件清单不符', 409)
    from app.modules.journal.manifest import digest
    if any(digest(text) != receipt['inputs'][name] for name, text in sources.items()):
        raise TideError('INVALID_PROOF', '归档原件校验未通过', 409)
    evidence = {'manifest': receipt, 'originals': sources, 'reports': reports}
    result = {**evidence, 'seal_sha256': seal(evidence), 'verified': True}
    if view is not None and view.get('plan') is not None:
        result['plan_view'] = {'derived': 'plan' not in reports, 'plan': view['plan']}
    return result
