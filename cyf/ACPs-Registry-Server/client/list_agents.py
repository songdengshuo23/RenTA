import json, requests
from demo_common import DEFAULT_BASE_URL, login_with_password

tb = login_with_password(DEFAULT_BASE_URL, 'demo-client', 'demo123')
H = {'Authorization': f'Bearer {tb.access_token}'}
r = requests.get(DEFAULT_BASE_URL + '/agent/client?page_num=1&page_size=50', headers=H)
data = r.json()
items = data.get('items') or data.get('data') or (data if isinstance(data, list) else [])
print(f'total={data.get("total", "?")} page={len(items)}')
for a in items:
    aic = a.get('aic', '')
    name = a.get('name', '')
    status = a.get('approval_status') or a.get('approvalStatus') or a.get('status', '?')
    aid = a.get('id', '')
    acs = a.get('acs') or {}
    if isinstance(acs, str):
        try: acs = json.loads(acs)
        except: acs = {}
    eps = (acs.get('endPoints') or [{}])[0]
    print(f'  id={aid}  {name:18s} aic={aic:50s} status={status:10s} url={eps.get("url","")}')
