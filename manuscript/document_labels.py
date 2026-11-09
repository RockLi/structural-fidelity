"""Stable evidence keys with sequential reader-facing labels after reorganization.

Internal markers identify evidence, not display order. Main figures/tables use
Arabic numbers; supplementary figures/tables use S-prefixed numbers. Equations
retain suffix groups but are numbered by their first appearance across the paper.
"""
import re

EQUATION_LABELS = {
    'neuron': ['1a', '1b'], 'raw': ['2'], 'history': ['3a', '3b', '3c'],
    'modulation': ['4a', '4b'], 'constraints': ['5'], 'residual': ['6a'],
    'redistribution': ['6b'], 'bound': ['7'], 'lowerbound': ['8'],
    'counterexample': ['9'], 'predictor': ['10'], 'response': ['11'],
    'fidelity': ['12'], 'finite_horizon': ['13'], 'composition': ['14a', '14b'],
    'composition_identity': ['15a', '15b'], 'smoothdistance': ['16a', '16b'],
    'branch_guard': ['18'], 'direction_weight': ['19'], 'direction_score': ['20a','20b'],
    'activity_score': ['17a', '17b'],
    'lif':['30a','30b'], 'lif_family':['31'], 'horizon_nested':['32'], 'lif_score':['33a','33b','33c'], 'lif_decay_bound':['34'], 'lif_voltage_bound':['35'],
}


class Labels:
    def __init__(self, paper):
        self.maps = {'FIG': {}, 'TABLE': {}, 'EQ': {}}
        self.marker_order = {'FIG': [], 'TABLE': [], 'EQ': []}
        base_numbers = {}
        for appendix, items in [(False, paper.SECTIONS), (True, paper.APPENDIX)]:
            counts = {'FIG': 0, 'TABLE': 0}
            for _, body in items:
                for kind, key in re.findall(r'\[\[(FIG|TABLE|EQ):([^]]+)\]\]', body):
                    assert key not in self.marker_order[kind], (kind, key)
                    self.marker_order[kind].append(key)
                    if kind == 'EQ':
                        for old in EQUATION_LABELS[key]:
                            base, suffix = re.fullmatch(r'(\d+)([abc]?)', old).groups()
                            if base not in base_numbers:
                                base_numbers[base] = str(len(base_numbers) + 1)
                            self.maps['EQ'][old] = base_numbers[base] + suffix
                            self.maps['EQ'].setdefault(base, base_numbers[base])
                    else:
                        counts[kind] += 1
                        self.maps[kind][key] = ('S' if appendix else '') + str(counts[kind])

    def equation(self, old):
        key = old.strip('()')
        return '(' + self.maps['EQ'][key] + ')'

    def rewrite(self, text):
        # Replace each reference sequence once; never reinterpret new labels as
        # old evidence keys. Ranges are expanded so moved evidence remains exact.
        specs = [
            ('FIG', r'\bFigures?|\bfigures?|(?<!原)图', r'S?\d+'),
            ('TABLE', r'\bTables?|\btables?|表', r'[ABS]?\d+'),
            ('EQ', r'\bEqs?\.|\bEquations?|\bequations?|式', r'[（(]\d+[abc]?[）)]'),
        ]
        for kind, prefix, token in specs:
            pattern = re.compile(r'(?P<prefix>' + prefix + r')(?P<space>\s*)'
                                 r'(?P<refs>' + token + r'(?:\s*(?:,\s*and|and|,|–|−|—|-|至|和|及|、)\s*' + token + r')*)')
            def replace(match):
                refs = match['refs']
                keys = re.findall(token, refs)
                bare = [k.strip('()（）') for k in keys]
                mapping = self.maps[kind]
                if any(k not in mapping for k in bare):
                    raise ValueError(f'Unknown {kind} reference: {match.group()}')
                # Expand integer ranges of the same internal label family.
                if len(bare) == 2 and re.search(r'[–−—-]|至', refs):
                    a = re.fullmatch(r'([A-Z]?)(\d+)([abc]?)', bare[0])
                    b = re.fullmatch(r'([A-Z]?)(\d+)([abc]?)', bare[1])
                    if a and b and a[1] == b[1] and not a[3] and not b[3]:
                        candidates = [a[1] + str(i) for i in range(int(a[2]), int(b[2]) + 1)]
                        if all(k in mapping for k in candidates):
                            bare = candidates
                output = [mapping[k] for k in bare]
                if kind == 'EQ':
                    output = ['(' + k + ')' for k in output]
                join = '、' if match['prefix'] in {'图', '表', '式'} else ', '
                return match['prefix'] + match['space'] + join.join(output)
            text = pattern.sub(replace, text)
        return text

    def report(self):
        return {'maps': self.maps, 'marker_order': self.marker_order}
