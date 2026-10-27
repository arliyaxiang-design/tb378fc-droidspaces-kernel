from pathlib import Path
import hashlib
import json
import re
import ssl
import sys
from compat import exported_symbols, layouts

root = Path(__file__).resolve().parents[1]
dist = root / 'dist'
phase = sys.argv[1]
assert phase in ('baseline', 'droidspaces')
stock = json.loads((root / 'config/stock-layouts.json').read_text())
live = layouts((dist / f'{phase}.btf').read_bytes())
layout_errors = {}
for name, original in stock.items():
    candidate = live[name]
    changed = {field: {'stock': offset, 'candidate': candidate['members'].get(field)}
               for field, offset in original['members'].items()
               if not field.startswith('android_kabi_reserved')
               and candidate['members'].get(field) != offset}
    if changed or candidate['size'] != original['size']:
        layout_errors[name] = {'stock_size': original['size'], 'candidate_size': candidate['size'], 'members': changed}
symbols = exported_symbols(dist / f'{phase}.Module.symvers')
imports = json.loads((root / 'config/stock-imports.json').read_text())
vendor_exports = set(json.loads((root / 'config/stock-module-exports.json').read_text()))
missing = sorted(s for s in imports if s not in symbols and s not in vendor_exports)
crc_errors = {name: {'stock': hex(crc), 'candidate': hex(symbols[name])}
              for name, crc in imports.items() if name in symbols and symbols[name] != crc}
baseline_errors = {}
if phase == 'droidspaces':
    baseline = exported_symbols(dist / 'baseline.Module.symvers')
    baseline_errors = {name: {'baseline': hex(crc), 'candidate': hex(symbols[name]) if name in symbols else None}
                       for name, crc in baseline.items() if symbols.get(name) != crc}
    config = (dist / 'droidspaces.config').read_text()
    for feature in ('SYSVIPC', 'POSIX_MQUEUE', 'PID_NS', 'IPC_NS', 'USER_NS', 'DEVTMPFS'):
        assert re.search(rf'^CONFIG_{feature}=y$', config, re.M), feature
    for feature in ('CFS_BANDWIDTH', 'CGROUP_PIDS'):
        assert not re.search(rf'^CONFIG_{feature}=y$', config, re.M), f'Unexpected ABI-breaking option: {feature}'
image = (dist / f'{phase}.Image').read_bytes()
pem = (root / 'config/stock-module-certs.pem').read_text()
certs = re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', pem, re.S)
cert_missing = [hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert)).hexdigest()
                for cert in certs if ssl.PEM_cert_to_DER_cert(cert) not in image]
assert certs
report = {'phase': phase, 'layout_errors': layout_errors, 'stock_import_crc_errors': crc_errors,
          'unresolved_stock_imports': missing, 'changed_or_missing_baseline_exports': baseline_errors,
          'stock_certificates_missing': cert_missing,
          'matching_stock_imports': sum(name in symbols for name in imports),
          'limitations': 'Static checks only. Vendor modules and hardware still require a device boot test.'}
(dist / f'{phase}-compatibility.json').write_text(json.dumps(report, indent=2))
print(json.dumps({k: (len(v) if isinstance(v, (dict, list)) else v) for k, v in report.items()}, indent=2))
assert not any((layout_errors, crc_errors, missing, baseline_errors, cert_missing)), 'Compatibility audit failed; do not flash'
