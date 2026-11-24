from app.config import SAMPLE_ROOT, SOURCE_LIMIT
from app.errors import TideError
from app.modules.intake.contract import HEADERS, OPTIONAL_HEADERS

ALL_HEADERS = {**HEADERS, **OPTIONAL_HEADERS}


def load_sources(payload):
    if not isinstance(payload, dict):
        raise TideError('BAD_SOURCE', '请选择样例或提交潮汐资料')
    if set(payload) == {'sample'}:
        sample = payload['sample']
        if sample not in ('dirty', 'clean'):
            raise TideError('NO_SAMPLE', '找不到样例簿', 404)
        root = SAMPLE_ROOT / sample
        names = [name for name in ALL_HEADERS if (root / f'{name}.csv').exists()]
        return {name: (root / f'{name}.csv').read_bytes().decode() for name in names}
    sources = payload.get('sources')
    if (set(payload) != {'sources'} or not isinstance(sources, dict)
            or not set(HEADERS) <= set(sources) or not set(sources) <= set(ALL_HEADERS)):
        raise TideError('BAD_SOURCE', '请提交潮尺、站点及船期 CSV，航速表可选')
    if any(not isinstance(text, str) for text in sources.values()):
        raise TideError('BAD_SOURCE', 'CSV 内容应为字符串')
    try:
        if any(len(text.encode('utf-8')) > SOURCE_LIMIT for text in sources.values()):
            raise TideError('TOO_LARGE', '单份资料超过 256 KB', 413)
    except UnicodeEncodeError as exc:
        raise TideError('BAD_SOURCE', 'CSV 内容含非法字符') from exc
    return sources
