from app.clock import depth

COLUMNS = ('design_kn', 'keep_kn', 'slow_kn', 'squat_coeff')
MAX_KN = 40
MAX_COEFF = 2


def read_speeds(intake, vessels, sections):
    """Return (specs, rejected). specs is None when the optional speed sheet is absent."""
    if 'speeds' not in intake['tables']:
        return None, []
    specs, rejected, seen = {}, [], set()
    for record in intake['tables']['speeds']:
        raw = record['raw']
        vessel, section = raw['vessel'].strip(), raw['section'].strip()
        code = None
        try:
            design, keep, slow, coeff = (depth(raw[name]) for name in COLUMNS)
        except (ValueError, OverflowError):
            code = 'BAD_SPEED'
        if code is None and vessel not in vessels:
            code = 'UNKNOWN_VESSEL'
        elif code is None and section not in sections:
            code = 'UNKNOWN_SECTION'
        elif code is None and not (0 < slow <= keep <= design <= MAX_KN and 0 <= coeff <= MAX_COEFF):
            code = 'BAD_SPEED'
        elif code is None and (vessel, section) in seen:
            code = 'DUPLICATE_SPEED'
        if code:
            rejected.append(dict(source='speeds', line=record['line'], code=code, raw=raw))
            continue
        seen.add((vessel, section))
        specs.setdefault(vessel, {})[section] = dict(
            design_kn=design, keep_kn=keep, slow_kn=slow, squat_coeff=coeff, line=record['line'])
    return specs, rejected
