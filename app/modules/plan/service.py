from fractions import Fraction

from app.modules.crossings.interpolate import interpolate
from app.modules.passage.service import analyze
from app.modules.passage.state import SectionClock, judgement

RULE = 'squat-1.0'
KEEP, SLOW = 'keep_kn', 'slow_kn'


def squat_m(spec, field):
    """Squat at the planned speed, scaled by (kn / design_kn) ** 2 from the design-speed coefficient."""
    design, kn = Fraction(spec['design_kn']), Fraction(spec[field])
    return kn, Fraction(spec['squat_coeff']) * (kn / design) ** 2


def _sections(order, base, specs, field):
    built = {}
    for name, section in base.items():
        kn, squat = squat_m(specs[name], field)
        required = Fraction(order['threshold_m']) + squat
        built[name] = dict(
            offset_s=Fraction(section['offset_s']) * Fraction(specs[name]['design_kn']) / kn,
            gap_s=section['gap_s'], points=section['points'],
            bands=interpolate(section['points'], section['gap_s'], required),
            threshold_m=str(required), kn=kn, squat_m=squat, required_m=required)
    return built


def _horizon(sections):
    ends = [Fraction(section['points'][-1]['time']) - section['offset_s']
            for section in sections.values() if section['points']]
    return min(ends) if ends else None


def _departure_points(windows, isolated, lower, upper):
    points = set()
    for row in windows:
        start, end = Fraction(row['start']), Fraction(row['end'])
        if end <= lower or start >= upper:
            continue
        point = max(start, lower)
        if not row['start_included'] and point == start:
            point += Fraction(1, 1000)
        if point < upper:
            points.add(point)
    points.update(Fraction(row['at']) for row in isolated if lower <= Fraction(row['at']) < upper)
    points.add(lower)
    return sorted(points)


def _first_open(clocks, points):
    for point in points:
        if judgement(clocks, point, None)['status'] == 'open':
            return point
    return None


def _option(order, base, specs, field):
    sections = _sections(order, base, specs, field)
    clocks = [SectionClock(name, section) for name, section in sections.items()]
    current = analyze(clocks, order['start'], order['end'], None, order['requested'])
    horizon = _horizon(sections)
    upcoming = analyze(clocks, order['end'], horizon, None) if horizon is not None and horizon > order['end'] else None
    option = dict(field=field, sections=sections, clocks=clocks, current=current,
                  upcoming=upcoming, horizon=horizon)
    option['now'] = _first_open(clocks, _departure_points(
        current['windows'], current['isolated_points'], order['requested'], order['end']))
    option['high'] = _first_open(clocks, _departure_points(
        upcoming['windows'], upcoming['isolated_points'], order['end'], horizon)) if upcoming else None
    return option


def _margins(option, when):
    when = Fraction(when)
    evidence = judgement(option['clocks'], when, None)
    rows = []
    for row in evidence['evidence']:
        section = option['sections'][row['section']]
        depth = row['depth_m']
        rows.append(dict(section=row['section'], departure=str(when), offset_s=str(section['offset_s']),
                         at=row['at'], lines=row['lines'], code=row['code'], status=row['status'],
                         depth_m=depth, kn=str(section['kn']), squat_m=str(section['squat_m']),
                         required_m=str(section['required_m']),
                         margin_m=str(Fraction(depth) - section['required_m']) if depth is not None else None))
    return dict(at=str(when), status=evidence['status'], sections=rows)


def _static(order, base):
    clocks = [SectionClock(name, section) for name, section in base.items()]
    current = analyze(clocks, order['start'], order['end'], Fraction(order['threshold_m']), order['requested'])
    rows = []
    for row in current['requested']['evidence']:
        depth = row['depth_m']
        rows.append(dict(section=row['section'], at=row['at'], lines=row['lines'], code=row['code'],
                         status=row['status'], depth_m=depth, kn=None, squat_m='0',
                         required_m=order['threshold_m'],
                         margin_m=str(Fraction(depth) - Fraction(order['threshold_m']))
                         if depth is not None else None))
    return dict(threshold_m=order['threshold_m'], windows=current['windows'],
                isolated_points=current['isolated_points'],
                anchor=dict(at=str(order['requested']), status=current['requested']['status'], sections=rows))


def _scheme(specs):
    return {name: dict(design_kn=str(spec['design_kn']), keep_kn=str(spec['keep_kn']),
                       slow_kn=str(spec['slow_kn']), squat_coeff=str(spec['squat_coeff']),
                       line=spec['line']) for name, spec in specs.items()}


def _option_report(option):
    sections = [dict(section=name, kn=str(section['kn']), squat_m=str(section['squat_m']),
                     required_m=str(section['required_m']), offset_s=str(section['offset_s']))
                for name, section in option['sections'].items()]
    kns = sorted({row['kn'] for row in sections})
    upcoming = option['upcoming']
    return dict(kn=kns[0] if len(kns) == 1 else kns, sections=sections,
                windows=option['current']['windows'], isolated_points=option['current']['isolated_points'],
                anchor=_margins(option, option['current']['requested']['at']) if option['current']['requested'] else None,
                first_departure=str(option['now']) if option['now'] is not None else None,
                next_windows=upcoming['windows'] if upcoming else [],
                next_isolated=upcoming['isolated_points'] if upcoming else [],
                next_departure=str(option['high']) if option['high'] is not None else None,
                next_known=upcoming is not None)


def _decide(order, keep, slow):
    end = order['end']

    def wait(option, mode, label):
        beyond = option['high'] >= end
        note = '该出发已越过船期时窗右端，须改签船期。' if beyond else '按该窗口出发，当前窗口放弃。'
        return dict(decision='wait', mode=mode, departure=option['high'],
                    headline=label + ('（超出船期）' if beyond else ''),
                    beyond_window=beyond, rationale=note)

    if keep['now'] is not None:
        return dict(decision='keep', mode='keep', departure=keep['now'], headline='保速赶当前潮窗',
                    beyond_window=False, rationale=['各断面余量已按保速的船体下沉逐段重核，当前窗口仍可放行。',
                                                    '减速只会让后续断面更晚到达，本趟无需让出时间。'])
    if slow['now'] is not None:
        rationale = ['申报吃水按设计航速计下沉，浅水时段会被写成可行。',
                     '保速在浅段下沉更多，申请时点并非所有断面都够深。',
                     '减速降低下沉量，可在同一水位多留余量，吃下当前窗口。',
                     '代价是后续断面更晚到达，余量已按减速后的到达时刻重核。']
        rationale.append('若坚持保速，只能等下一趟高水，出发更晚。' if keep['high'] is not None
                         else '潮尺未覆盖保速的下一趟高水，等潮方案仍缺证。')
        return dict(decision='slow', mode='slow', departure=slow['now'], headline='减速吃当前窗口',
                    beyond_window=False, rationale=rationale)
    if keep['high'] is not None:
        result = wait(keep, 'keep', '保速等下一趟高水')
        text = ('保速的下一趟高水仍可行，' + result['rationale']) if result['beyond_window'] \
            else ('保速的下一趟高水仍可行，按该窗口出发，当前窗口放弃。')
        return {**result, 'rationale': ['当前窗口内保速与减速都过不了浅段。', text]}
    if slow['high'] is not None:
        result = wait(slow, 'slow', '减速等下一趟高水')
        text = ('下一趟高水只有减速时可行，' + result['rationale']) if result['beyond_window'] \
            else '下一趟高水只有减速时可行，按该窗口出发。'
        return {**result, 'rationale': ['当前窗口内保速与减速都过不了浅段。', text]}
    return dict(decision='wait', mode=None, departure=None, headline='等下一趟高水（缺证）',
                beyond_window=False,
                rationale=['当前窗口内保速与减速都过不了浅段。',
                           '潮尺未覆盖下一个可行窗口，暂不能给出出发时点。'])


def _ship(key, rec, specs, missing):
    order, base = rec['order'], rec['sections']
    static = _static(order, base)
    ship = dict(vessel=key, order_line=order['line'], anchor=str(order['requested']),
                static_threshold_m=order['threshold_m'], static=static,
                missing_sections=missing, sections=[], options={}, scheme={})
    if missing:
        ship.update(decision='unknown', headline='航速表不全，暂不排速', departure=None,
                    beyond_window=False, rationale=[f'缺少断面航速：{"、".join(missing)}。'],
                    scheme=_scheme(specs))
        return ship
    keep = _option(order, base, specs, KEEP)
    slow = _option(order, base, specs, SLOW)
    choice = _decide(order, keep, slow)
    chosen = keep if choice['mode'] == 'keep' else slow if choice['mode'] == 'slow' else None
    ship.update(decision=choice['decision'], mode=choice['mode'], headline=choice['headline'],
                departure=str(choice['departure']) if choice['departure'] is not None else None,
                rationale=choice['rationale'], beyond_window=choice.get('beyond_window', False),
                scheme=_scheme(specs),
                sections=_margins(chosen, choice['departure'])['sections']
                if chosen and choice['departure'] is not None else [],
                options={'keep': _option_report(keep), 'slow': _option_report(slow)})
    return ship


def build(crossings, speeds, rejected=()):
    ships = {}
    for key, rec in crossings.items():
        specs = (speeds or {}).get(key) or {}
        missing = [name for name in rec['sections'] if name not in specs]
        ships[key] = _ship(key, rec, specs, missing)
    return dict(rule=RULE, available=speeds is not None, ships=ships,
                rejected=sorted(rejected, key=lambda row: (row.get('line', 0), row['code'])))
