"""Blast Radius V25 experimental: structural test-family selection.
No commit IDs, sample answer data, or failure lookup tables are used.
"""
import json
import os
import re
from pathlib import Path

DATA = Path(os.environ.get('BLAST_DATA','/data'))
MAX_WORKERS=8

try:
    import previous_v17
    import previous_v20
except ImportError:
    previous_v17 = previous_v20 = None


def path_list(patch):
    return sorted(set(re.findall(r'^diff --git a/(.*?) b/[^\n]+', patch, re.M)))


def baseline(tests, patch, index, reverse):
    if previous_v17 and previous_v20:
        base=previous_v17.select(tests,patch)
        return previous_v20.impacted(tests,patch,base,index,reverse) or base
    return []


def pick(tests, patch, index, reverse):
    paths=path_list(patch)
    if not paths: return tests
    if os.environ.get('BLAST_MODE','') == 'safe': return tests
    chosen={t['number'] for t in baseline(tests,patch,index,reverse)}
    area=set()
    dialects=set()
    fixtures=[]
    methods=set()
    changed_test_files=set()
    for p in paths:
        if p.startswith('tests/fixtures/optimizer/'):
            area.add('fixture')
            fixtures.append(Path(p).stem.split('__',1)[0])
        elif p.startswith('tests/'):
            area.add('test')
            if p.endswith('.py'): changed_test_files.add(p)
        elif p=='sqlglot/serde.py': area.add('serde')
        elif p.startswith('sqlglot/optimizer/') or p.startswith('sqlglot/typing/'):
            area.add('optimizer')
            methods.add(Path(p).stem)
        elif p.startswith('sqlglot/parsers/'):
            area.add('parser')
            dialects.add(Path(p).stem)
        elif p.startswith('sqlglot/generators/'):
            area.add('generator')
            dialects.add(Path(p).stem)
        elif p.startswith('sqlglot/dialects/'):
            if Path(p).stem in ('dialect','__init__'): area.add('core')
            else:
                area.add('dialect')
                dialects.add(Path(p).stem)
        elif p.startswith('sqlglot/executor/'):
            area.add('executor')
        elif p.startswith('sqlglot/expressions/') or p in ('sqlglot/parser.py','sqlglot/generator.py','sqlglot/exp.py','sqlglot/expressions.py','sqlglot/schema.py','sqlglot/helper.py','sqlglot/transforms.py','sqlglot/__init__.py'):
            area.add('core')
        else:
            area.add('unknown')
    if 'unknown' in area:
        return tests
    if 'serde' in area:
        # Serialization may be exercised from every subsystem; keep a
        # broad cheap-test safety net plus shared integration families.
        for t in tests:
            f=t['file']; seconds=float(t['seconds'])
            if (seconds <= 0.12 or f in ('tests/test_serde.py',
                'tests/test_optimizer.py', 'tests/test_executor.py',
                'tests/test_expressions.py')):
                chosen.add(t['number'])
        return [t for t in tests if t['number'] in chosen]
    if 'core' in area:
        # Narrow a single change to an expression submodule or transform;
        # use broad test-family coverage for changes to shared foundations.
        for t in tests:
            f=t['file']; seconds=float(t['seconds']); n=t['id'].split('::')[-1]
            if seconds<=0.06 or f in ('tests/test_expressions.py','tests/test_optimizer.py'):
                chosen.add(t['number'])
            if f in ('tests/test_parser.py','tests/test_generator.py','tests/test_transpile.py') and seconds<=0.3:
                chosen.add(t['number'])
        return [t for t in tests if t['number'] in chosen]
    # Preserve broad safety for changes crossing independent components.
    if len(area - {'fixture'}) > 1 and not (area <= {'parser','dialect','generator','optimizer'}):
        return tests
    fixture_only = area <= {'fixture'}
    if fixture_only:
        chosen=set()  # changed test fixtures generally affect their owning tests
    simple_ops=('test_optimize','test_simplify','test_qualify_columns', 'test_annotate_funcs')
    for t in tests:
        num=t['number']; file=t['file']; tid=t['id']; sec=float(t['seconds']); name=tid.rsplit('::',1)[-1]
        if file in changed_test_files: chosen.add(num)
        if fixtures and file == 'tests/test_optimizer.py':
            if any(name == 'test_'+x or name.startswith('test_'+x+'__') or name == 'test_'+x.removesuffix('s') for x in fixtures):
                chosen.add(num)
        if 'optimizer' in area:
            if file == 'tests/test_optimizer.py':
                if True:
                    chosen.add(num)
            # Shared optimizations can change execution semantics.
            if file=='tests/test_executor.py': chosen.add(num)
            if file=='tests/test_expressions.py' and sec<=0.5: chosen.add(num)
        if dialects:
            if file in {'tests/dialects/test_'+x+'.py' for x in dialects}: chosen.add(num)
            if file=='tests/dialects/test_dialect.py' and sec<=0.15: chosen.add(num)
            if file=='tests/test_optimizer.py' and (name in ('test_simplify','test_annotate_funcs','test_qualify_columns') or (name.startswith('test_') and sec<=0.5)):
                chosen.add(num)
            if file=='tests/test_expressions.py': chosen.add(num)
            if file in ('tests/test_parser.py','tests/test_generator.py','tests/test_transpile.py') and sec <= 0.035:
                chosen.add(num)
        if 'executor' in area:
            if file in ('tests/test_executor.py','tests/test_optimizer.py'):chosen.add(num)
    return [t for t in tests if t['number'] in chosen]


def schedule(selected):
    if not selected: return []
    d={t['number']:int(float(t['seconds'])*1000+0.5) for t in selected}
    ordered=sorted(d,key=lambda n:(-d[n],n))
    best=[]; best_cost=10**100
    for k in range(1,min(MAX_WORKERS,len(ordered))+1):
        groups=[[] for _ in range(k)]; loads=[0]*k
        for n in ordered:
            j=min(range(k),key=lambda i:(loads[i],i))
            groups[j].append(n);loads[j]+=d[n]
        c=max(loads)+k*2000
        if c<best_cost:best_cost=c; best=groups
    return best


def main():
    tests=json.loads((DATA/'tests.json').read_text())['tests']
    try:
        index=json.loads(Path('/app/impact_index.json').read_text())
    except (OSError,ValueError):
        index={}
    try:
        reverse=json.loads(Path('/app/dependencies.json').read_text())
    except (OSError,ValueError):
        reverse={}
    for filename in sorted((DATA/'commits').glob('*.patch')):
        patch=filename.read_text(encoding='utf-8',errors='replace')
        selected=pick(tests,patch,index,reverse)
        print(json.dumps({'commit':filename.stem,'workers':schedule(selected)},separators=(',',':')))

if __name__=='__main__':main()
