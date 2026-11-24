from app.modules.crossings.service import find_crossings
from app.modules.datum.service import normalize
from app.modules.intake.service import intake
from app.modules.passage.service import route_windows
from app.modules.plan.service import build as plan
from app.modules.plan.speeds import read_speeds
from app.modules.schedule.orders import orders
from app.modules.schedule.service import reconcile

STEPS = ('readings', 'datum', 'crossings', 'windows', 'coverage', 'plan')


def calculate(inputs, stop='plan'):
    reports = {'readings': intake(inputs)}
    if stop == 'readings':
        return reports
    reports['datum'] = normalize(reports['readings'])
    if stop == 'datum':
        return reports
    vessels = orders(reports['readings'])
    reports['crossings'] = find_crossings(reports['datum'], vessels)
    if stop == 'crossings':
        return reports
    reports['windows'] = route_windows(reports['crossings'])
    if stop == 'windows':
        return reports
    reports['coverage'] = reconcile(reports['windows'])
    if stop == 'coverage':
        return reports
    specs, rejected = read_speeds(reports['readings'], vessels, reports['datum']['sections'])
    intake_rejects = [row for row in reports['readings']['rejected'] if row['source'] == 'speeds']
    reports['plan'] = plan(reports['crossings'], specs, intake_rejects + rejected)
    return reports


def view(reports):
    """Read-only archive view: derive a plan for records stored before the plan stage existed.
    The archive's own ``reports`` and ``result_sha256`` are never altered, so proof still verifies."""
    if 'plan' in reports or 'crossings' not in reports:
        return reports
    specs, rejected = read_speeds(reports['readings'], {key: rec['order'] for key, rec in reports['crossings'].items()},
                                  reports['datum']['sections'])
    intake_rejects = [row for row in reports['readings']['rejected'] if row['source'] == 'speeds']
    return {**reports, 'plan': plan(reports['crossings'], specs, intake_rejects + rejected)}
