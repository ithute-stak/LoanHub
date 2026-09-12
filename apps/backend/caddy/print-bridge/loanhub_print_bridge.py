#!/usr/bin/env python3
"""LoanHub local print bridge.
Stores agent credentials in ~/.loanhub-print-bridge/config.json with mode 0600.
Polls queued jobs, downloads authorised PDFs, and prints through lp/lpr.
Never store a user password or primary access token here.
"""
import argparse,json,os,subprocess,time
from pathlib import Path
import requests
CFG=Path.home()/'.loanhub-print-bridge/config.json'
def save(cfg): CFG.parent.mkdir(parents=True,exist_ok=True);CFG.write_text(json.dumps(cfg,indent=2));os.chmod(CFG,0o600)
def configure(args): save({'api_url':args.api_url.rstrip('/'),'agent_id':args.agent_id,'agent_secret':args.agent_secret,'printer':args.printer});print('Configured',CFG)
def printers(): subprocess.run(['lpstat','-p','-d'],check=False)
def run():
 c=json.loads(CFG.read_text());h={'X-Print-Agent-ID':c['agent_id'],'X-Print-Agent-Secret':c['agent_secret']}
 while True:
  try:
   jobs=requests.get(c['api_url']+'/professional/print-agent/jobs',headers=h,timeout=30).json()
   for j in jobs:
    data=requests.get(c['api_url']+f"/professional/print-agent/jobs/{j['id']}/file",headers=h,timeout=60).content
    tmp=Path('/tmp')/f"loanhub-{j['id']}.pdf";tmp.write_bytes(data)
    printer=j.get('printer_name') or c.get('printer');cmd=['lp']+(['-d',printer] if printer else [])+['-n',str(j.get('copies',1)),str(tmp)]
    subprocess.run(cmd,check=True);requests.post(c['api_url']+f"/professional/print-agent/jobs/{j['id']}/complete",headers=h,timeout=30)
  except Exception as e: print('Print bridge:',e)
  time.sleep(5)
p=argparse.ArgumentParser();sp=p.add_subparsers(dest='cmd',required=True);q=sp.add_parser('configure');q.add_argument('--api-url',required=True);q.add_argument('--agent-id',required=True);q.add_argument('--agent-secret',required=True);q.add_argument('--printer');sp.add_parser('printers');sp.add_parser('run');a=p.parse_args();{'configure':lambda:configure(a),'printers':printers,'run':run}[a.cmd]()
