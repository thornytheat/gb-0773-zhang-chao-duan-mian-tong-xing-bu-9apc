OBSERVATION = ('station', 'observed_at', 'level', 'unit', 'quality')
STATION = ('station', 'section', 'datum_m', 'bed_m', 'priority', 'offset_s', 'gap_s')
VESSEL = ('vessel', 'draft_m', 'clearance_m', 'start', 'end', 'requested')
SPEED = ('vessel', 'section', 'design_kn', 'keep_kn', 'slow_kn', 'squat_coeff')
HEADERS = {'observations': OBSERVATION, 'stations': STATION, 'vessels': VESSEL}
OPTIONAL_HEADERS = {'speeds': SPEED}
SENTINELS = frozenset({'', '-', 'N/A', 'NULL', '未知'})
